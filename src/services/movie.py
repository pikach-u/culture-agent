"""KOFIC 박스오피스 + TMDB 메타데이터 결합 + 24h 캐시 + 포스터 URL 캐시.

공개 API:
- get_box_office_text(user_message) -> str | None
  추천 키워드 매칭 시 KOFIC + TMDB 결합 텍스트 반환. 시스템 프롬프트 주입용.
- get_poster_url(title) -> str | None
  캐시된 영화 제목 → TMDB 포스터 풀 URL. handlers.py가 reply_photo 결정에 사용.

KOFIC: 일별 박스오피스 (어제 기준).
TMDB: KOFIC 영화명으로 search/movie 한국어 호출 → 평점/줄거리/포스터 path.
TMDB 호출은 ThreadPoolExecutor로 병렬화 (10편 순차=~10초 → 병렬=~1초).
"""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import requests

from src.config import KOFIC_API_KEY, TMDB_API_KEY
from src.timeutil import KST

KOFIC_DAILY_URL = (
    "http://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
)
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

KOFIC_TIMEOUT = 10  # KOFIC가 가끔 느림 — 5초는 빈번히 ReadTimeout (2026-05-11 발생).
TMDB_TIMEOUT = 5
CACHE_TTL = timedelta(hours=24)
OVERVIEW_LIMIT = 220  # 시스템 프롬프트 list 항목당 줄거리 표시 길이. 작은 모델이 잘린 list를 그대로 옮기면 caption도 끊겨 보임 → 충분한 길이 + 줄임표.

RECOMMEND_KEYWORDS = re.compile(
    r"추천|볼\s*만한|볼만|재밌는|재미있는|박스오피스|인기|상영중|상영\s*중|뭐\s*볼|영화\s*뭐",
    re.IGNORECASE,
)

_cache_text: str | None = None
_cache_posters: dict[str, str] = {}
_cache_at: datetime | None = None


def get_box_office_text(user_message: str) -> str | None:
    """추천 키워드 매칭 시 KOFIC + TMDB 결합 텍스트 반환. 아니면 None."""
    if not user_message or not RECOMMEND_KEYWORDS.search(user_message):
        return None
    if not KOFIC_API_KEY:
        return None

    cached = _get_cached_text()
    if cached is not None:
        return cached

    text, posters = _fetch_and_format()
    if text is not None:
        _set_cache(text, posters)
        return text

    # 호출 실패 + 만료된 캐시가 남아있으면 stale 반환 — 시연 중 외부 API 장애 보호.
    if _cache_text is not None:
        print("[movie] KOFIC/TMDB 호출 실패 → stale 캐시 반환 (시연 보호)")
        return _cache_text
    return None


def get_poster_url(title: str) -> str | None:
    """캐시된 영화 제목 → TMDB 포스터 풀 URL. 없으면 None."""
    return _cache_posters.get(title)


def match_cached_title(text: str) -> str | None:
    """텍스트 안에 캐시된 박스오피스 영화명이 들어있으면 그 제목 반환.

    handlers의 자연어 캘린더 처리에서 영화 제목 fallback 매칭에 사용.
    """
    if not text:
        return None
    for title in _cache_posters:
        if title and title in text:
            return title
    return None


def _get_cached_text() -> str | None:
    if _cache_text is None or _cache_at is None:
        return None
    if datetime.now(KST) - _cache_at > CACHE_TTL:
        return None
    return _cache_text


def _set_cache(text: str, posters: dict[str, str]) -> None:
    global _cache_text, _cache_posters, _cache_at
    _cache_text = text
    _cache_posters = posters
    _cache_at = datetime.now(KST)


def _fetch_and_format() -> tuple[str | None, dict[str, str]]:
    target_dt = (datetime.now(KST) - timedelta(days=1)).strftime("%Y%m%d")
    try:
        response = requests.get(
            KOFIC_DAILY_URL,
            params={"key": KOFIC_API_KEY, "targetDt": target_dt},
            timeout=KOFIC_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"[movie] KOFIC 요청 실패: {type(e).__name__}: {e}")
        return None, {}
    except ValueError as e:
        print(f"[movie] KOFIC JSON 파싱 실패: {e}")
        return None, {}

    movies = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
    if not movies:
        print(f"[movie] KOFIC 응답에 영화 list 없음 (대상일 {target_dt})")
        return None, {}

    titles = [m.get("movieNm", "") for m in movies]
    if TMDB_API_KEY:
        with ThreadPoolExecutor(max_workers=10) as executor:
            metas = list(executor.map(_tmdb_search, titles))
    else:
        metas = [None] * len(titles)

    if TMDB_API_KEY:
        header = f"현재 한국 박스오피스 순위 (KOFIC 일별 1~10위, 어제 {target_dt} 기준 — TMDB 메타 결합):"
    else:
        header = f"현재 한국 박스오피스 순위 (KOFIC 일별 1~10위, 어제 {target_dt} 기준):"
    lines = [header]
    posters: dict[str, str] = {}
    for m, meta in zip(movies, metas):
        rank = m.get("rank", "?")
        name = m.get("movieNm", "(제목 없음)")
        open_dt = m.get("openDt", "")

        line = f"{rank}. {name} (개봉 {open_dt})"
        if meta:
            overview = (meta.get("overview") or "").strip()
            if overview:
                shown = overview if len(overview) <= OVERVIEW_LIMIT else overview[:OVERVIEW_LIMIT] + "…"
                line += f" / {shown}"
            vote = meta.get("vote_average")
            if vote:
                line += f" [TMDB 평점 {vote:.1f} — 참고용]"
            poster = meta.get("poster_path")
            if poster:
                posters[name] = f"{TMDB_IMAGE_BASE}{poster}"
        lines.append(line)

    return "\n".join(lines), posters


def _tmdb_search(title: str) -> dict | None:
    """TMDB v3 API Key 방식 search/movie 호출. 첫 결과 반환. 실패 시 None."""
    if not title:
        return None
    try:
        r = requests.get(
            TMDB_SEARCH_URL,
            params={"api_key": TMDB_API_KEY, "query": title, "language": "ko-KR"},
            timeout=TMDB_TIMEOUT,
        )
        if not r.ok:
            print(f"[movie] TMDB search 실패 ({title}): HTTP {r.status_code}")
            return None
        results = r.json().get("results", [])
        return results[0] if results else None
    except requests.RequestException as e:
        print(f"[movie] TMDB 요청 실패 ({title}): {type(e).__name__}: {e}")
        return None
    except ValueError as e:
        print(f"[movie] TMDB JSON 파싱 실패 ({title}): {e}")
        return None
