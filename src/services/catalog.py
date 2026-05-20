"""TMDB 영화 카탈로그 — Stage 12 RAG 임베딩의 데이터 원천.

공개 API:
- ensure_fresh() -> None
  카탈로그 1주 stale 또는 부재 시 fetch + 저장. main.py가 봇 startup에서 호출.
- get_all() -> list[dict]
  전체 카탈로그 (Stage 12 임베딩이 사용 예정).
- get_by_id(tmdb_id) -> dict | None
  단일 영화 조회.

설계:
- 소스 조합: popular 5p (100편) + top_rated 5p (100편) + discover KR 최근 5년 5p (100편) → dedup
  부족분은 top_rated 추가 페이지로 보충. TARGET_SIZE=300.
- OTT 가용성: `/movie/{id}/watch/providers` 4-worker 병렬. 한국 flatrate만 (구독으로 시청 가능).
- 캐시: data/movies_catalog.json + fetched_at 메타. 1주 TTL.
- TMDB rate limit 40 req/10s. 4 worker는 안전.

Stage 8 movie.py는 KOFIC 10편 박스오피스 전용 — 본 모듈과 독립.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import requests

from src.config import PROJECT_ROOT, TMDB_API_KEY
from src.timeutil import KST

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_TIMEOUT = 10
CATALOG_PATH = PROJECT_ROOT / "data" / "movies_catalog.json"
CATALOG_TTL = timedelta(days=7)
TARGET_SIZE = 300
PAGES_PER_SOURCE = 5  # 20편 × 5페이지 = 100편 (소스당)
MAX_TOP_RATED_BOOST_PAGE = 15  # 부족분 보충 시 top_rated 최대 페이지

_genre_map: dict[int, str] | None = None


def ensure_fresh() -> None:
    """캐시가 1주 이상 오래됐거나 없으면 fetch + 저장. fresh면 무비용 패스.

    봇 startup에서 호출 — 첫 기동 시 ~1분 소요(300 OTT 호출), 이후 1주 동안 즉시 패스.
    """
    if not TMDB_API_KEY:
        print("[catalog] TMDB_API_KEY 미설정 — fetch 스킵")
        return
    if _is_fresh():
        payload = _load_payload()
        count = payload.get("count", "?") if payload else "?"
        print(f"[catalog] 캐시 fresh ({count}편) — fetch 스킵")
        return

    print("[catalog] fetch 시작 (TMDB 호출 ~몇 분 소요)...")
    started = datetime.now(KST)
    movies = _fetch_catalog()
    if not movies:
        print("[catalog] fetch 실패 — 기존 캐시 유지")
        return
    _attach_ott(movies)
    _save(movies)
    elapsed = (datetime.now(KST) - started).total_seconds()
    ott_count = sum(1 for m in movies if m["ott_kr"])
    print(
        f"[catalog] {len(movies)}편 저장 완료 (소요 {elapsed:.1f}s, OTT 채워진 비율 "
        f"{ott_count}/{len(movies)} = {ott_count*100//len(movies)}%)"
    )


def get_all() -> list[dict]:
    payload = _load_payload()
    return payload["movies"] if payload else []


def get_by_id(tmdb_id: int) -> dict | None:
    for m in get_all():
        if m.get("id") == tmdb_id:
            return m
    return None


def get_poster_url(title: str) -> str | None:
    """카탈로그 제목(한·영) 매칭 → TMDB 포스터 풀 URL. Stage 13 OTT 추천의 handlers fallback."""
    for m in get_all():
        if title in (m.get("title_ko"), m.get("title_en")):
            path = m.get("poster_path")
            if path:
                return f"{TMDB_IMAGE_BASE}{path}"
            return None
    return None


def _is_fresh() -> bool:
    payload = _load_payload()
    if not payload:
        return False
    try:
        fetched = datetime.fromisoformat(payload["fetched_at"])
    except (KeyError, ValueError):
        return False
    return datetime.now(KST) - fetched < CATALOG_TTL


def _load_payload() -> dict | None:
    if not CATALOG_PATH.exists():
        return None
    try:
        with CATALOG_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[catalog] 로드 실패: {type(e).__name__}: {e}")
        return None


def _save(movies: list[dict]) -> None:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(KST).isoformat(),
        "count": len(movies),
        "movies": movies,
    }
    with CATALOG_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _fetch_catalog() -> list[dict]:
    """3개 소스 fetch → dedup → 부족분 보충. id 키 dict로 dedup, insertion order 보존."""
    _ensure_genre_map()
    seen: dict[int, dict] = {}

    # 1. popular (글로벌 인기, 한국 사용자 노출 높음)
    for page in range(1, PAGES_PER_SOURCE + 1):
        for m in _fetch_list("/movie/popular", page):
            seen.setdefault(m["id"], _normalize(m))

    # 2. top_rated (시대 평가 검증)
    for page in range(1, PAGES_PER_SOURCE + 1):
        for m in _fetch_list("/movie/top_rated", page):
            seen.setdefault(m["id"], _normalize(m))

    # 3. discover 한국 영화 최근 5년 (국내 영화 보충)
    cutoff = (datetime.now(KST) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
    discover_params = {
        "with_origin_country": "KR",
        "primary_release_date.gte": cutoff,
        "sort_by": "popularity.desc",
    }
    for page in range(1, PAGES_PER_SOURCE + 1):
        for m in _fetch_list("/discover/movie", page, extra_params=discover_params):
            seen.setdefault(m["id"], _normalize(m))

    # 4. 부족분 → top_rated 추가 페이지로 보충
    if len(seen) < TARGET_SIZE:
        print(f"[catalog] dedup 후 {len(seen)}편 — top_rated 추가 페이지로 보충")
        page = PAGES_PER_SOURCE + 1
        while len(seen) < TARGET_SIZE and page <= MAX_TOP_RATED_BOOST_PAGE:
            added = 0
            for m in _fetch_list("/movie/top_rated", page):
                if m["id"] not in seen:
                    seen[m["id"]] = _normalize(m)
                    added += 1
            if added == 0:  # 페이지에 신규 0건 — TMDB 끝 도달
                break
            page += 1

    movies = list(seen.values())[:TARGET_SIZE]
    print(f"[catalog] fetch 결과: {len(movies)}편 (dedup 전 raw 호출 ≈ {PAGES_PER_SOURCE*3*20}편)")
    return movies


def _fetch_list(path: str, page: int, extra_params: dict | None = None) -> list[dict]:
    params: dict = {"api_key": TMDB_API_KEY, "language": "ko-KR", "page": page}
    if extra_params:
        params.update(extra_params)
    try:
        r = requests.get(f"{TMDB_BASE}{path}", params=params, timeout=TMDB_TIMEOUT)
        r.raise_for_status()
        return r.json().get("results", [])
    except (requests.RequestException, ValueError) as e:
        print(f"[catalog] {path} page={page} 실패: {type(e).__name__}: {e}")
        return []


def _normalize(m: dict) -> dict:
    """TMDB raw → 카탈로그 형식. OTT는 별도 단계에서 attach."""
    release = m.get("release_date") or ""
    year = int(release[:4]) if len(release) >= 4 and release[:4].isdigit() else None
    genre_ids = m.get("genre_ids", [])
    genres = [_genre_map.get(gid) for gid in genre_ids] if _genre_map else []
    genres = [g for g in genres if g]
    return {
        "id": m["id"],
        "title_ko": m.get("title", ""),
        "title_en": m.get("original_title", ""),
        "year": year,
        "genres": genres,
        "overview": (m.get("overview") or "").strip(),
        "vote_average": m.get("vote_average"),
        "poster_path": m.get("poster_path"),
        "ott_kr": [],
    }


def _ensure_genre_map() -> None:
    """장르 ID → 한국어 이름 매핑. list API가 genre_ids만 주므로 별도 호출 필요."""
    global _genre_map
    if _genre_map is not None:
        return
    try:
        r = requests.get(
            f"{TMDB_BASE}/genre/movie/list",
            params={"api_key": TMDB_API_KEY, "language": "ko-KR"},
            timeout=TMDB_TIMEOUT,
        )
        r.raise_for_status()
        _genre_map = {g["id"]: g["name"] for g in r.json().get("genres", [])}
        print(f"[catalog] 장르맵 로드: {len(_genre_map)}개")
    except (requests.RequestException, ValueError) as e:
        print(f"[catalog] 장르맵 fetch 실패: {type(e).__name__}: {e}")
        _genre_map = {}


def _attach_ott(movies: list[dict]) -> None:
    """각 영화에 OTT KR flatrate 추가 (in-place). 4 worker 병렬."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(_fetch_ott_for, [m["id"] for m in movies]))
    for m, ott in zip(movies, results):
        m["ott_kr"] = ott


def _fetch_ott_for(movie_id: int) -> list[str]:
    """단일 영화의 한국 flatrate provider 이름 list. 실패/없음 시 빈 list."""
    try:
        r = requests.get(
            f"{TMDB_BASE}/movie/{movie_id}/watch/providers",
            params={"api_key": TMDB_API_KEY},
            timeout=TMDB_TIMEOUT,
        )
        r.raise_for_status()
        kr = r.json().get("results", {}).get("KR", {})
        flatrate = kr.get("flatrate", [])
        return [p.get("provider_name", "") for p in flatrate if p.get("provider_name")]
    except (requests.RequestException, ValueError) as e:
        print(f"[catalog] OTT fetch 실패 id={movie_id}: {type(e).__name__}: {e}")
        return []
