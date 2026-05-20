"""Stage 12 RAG 임베딩 인덱스 — bge-m3 + numpy + pickle.

공개 API:
- ensure_built() -> None
  카탈로그가 임베딩보다 새것이거나 임베딩 부재 시 빌드. main.py가 startup에서 호출.
- search(query, top_k=10) -> list[dict]
  쿼리 임베딩 후 cosine top_k 영화 메타 반환 (catalog.get_by_id 거쳐 full meta).
- get_ott_text(query, ott_filter=None, top_k=10) -> str | None
  Stage 13 OTT 모드용 LLM list 텍스트. ott_filter 적용 후 0건이면 None.

설계:
- 임베딩 모델: bge-m3 (한국어 RAG 표준, 1024차원, Stage 2 ollama 일관성).
- 임베딩 입력: title_ko + 장르 + overview 결합 — 제목·장르 시그널 보강.
- 저장: data/movies_embeddings.npy (float32, N×1024 L2-normalized) +
        data/movies_embeddings.pkl (id 리스트, npy의 행 인덱스 → tmdb_id).
- 신선도: 임베딩 npy mtime >= 카탈로그 json mtime이면 fresh.
- 모듈 globals: _vectors, _ids — search 첫 호출 시 lazy load.

Stage 13에서 mode router(극장/OTT)가 search() 호출. Stage 12는 인덱스 + 검색 API까지.
벡터 DB 마이그(Chroma 등)는 후순위 학습 과제 — 인터페이스 좁게 유지해서 교체 쉽게.
"""

import pickle
from datetime import datetime

import numpy as np
import ollama

from src.config import OLLAMA_HOST, PROJECT_ROOT
from src.services import catalog

EMBED_MODEL = "bge-m3"
NPY_PATH = PROJECT_ROOT / "data" / "movies_embeddings.npy"
PKL_PATH = PROJECT_ROOT / "data" / "movies_embeddings.pkl"
CATALOG_PATH = PROJECT_ROOT / "data" / "movies_catalog.json"
OVERVIEW_LIMIT = 220  # Stage 8 movie.py와 동일 — list 항목당 줄거리 표시 길이

_client = ollama.Client(host=OLLAMA_HOST)

_vectors: np.ndarray | None = None  # (N, 1024) L2-normalized
_ids: list[int] | None = None


def ensure_built() -> None:
    """카탈로그가 새것이거나 임베딩 부재 시 빌드. fresh면 무비용 패스.

    봇 startup에서 호출 — 첫 빌드 시 300회 ollama 호출 (~분 단위).
    """
    if _is_fresh():
        print("[embedding] 임베딩 fresh — 빌드 스킵")
        return
    movies = catalog.get_all()
    if not movies:
        print("[embedding] 카탈로그 비어있음 — 빌드 스킵")
        return

    print(f"[embedding] {len(movies)}편 임베딩 빌드 시작 (bge-m3, ~분 단위)...")
    started = datetime.now()
    vectors, ids = _build(movies)
    if vectors is None:
        print("[embedding] 빌드 실패 — 기존 인덱스 유지")
        return
    _save(vectors, ids)
    global _vectors, _ids
    _vectors, _ids = vectors, ids
    elapsed = (datetime.now() - started).total_seconds()
    print(f"[embedding] {len(ids)}편 인덱스 저장 완료 (소요 {elapsed:.1f}s)")


def search(query: str, top_k: int = 10) -> list[dict]:
    """쿼리 임베딩 → cosine top_k 영화 메타. 인덱스 없으면 빈 list."""
    _lazy_load()
    if _vectors is None or _ids is None or len(_ids) == 0:
        return []
    try:
        resp = _client.embed(model=EMBED_MODEL, input=query)
        q = np.array(resp["embeddings"][0], dtype=np.float32)
    except Exception as e:
        print(f"[embedding] 쿼리 임베딩 실패: {type(e).__name__}: {e}")
        return []
    norm = float(np.linalg.norm(q))
    if norm < 1e-9:
        return []
    q /= norm
    sims = _vectors @ q  # 둘 다 L2-normalized → cosine = dot product
    k = min(top_k, len(_ids))
    top_idx = np.argpartition(-sims, k - 1)[:k]
    top_idx = top_idx[np.argsort(-sims[top_idx])]
    results: list[dict] = []
    for i in top_idx:
        m = catalog.get_by_id(_ids[i])
        if m:
            results.append(m)
    return results


def get_ott_text(
    query: str,
    ott_filter: list[str] | None = None,
    top_k: int = 10,
) -> str | None:
    """Stage 13 OTT 모드 — RAG top_k → LLM list 텍스트.

    ott_filter 있으면 사후 처리(top_k*2 검색 → 필터 → top_k 컷). 0건이면 None.
    """
    initial_k = top_k * 2 if ott_filter else top_k
    results = search(query, top_k=initial_k)
    if ott_filter:
        results = [m for m in results if _has_any_ott(m, ott_filter)]
        results = results[:top_k]
    if not results:
        return None

    if ott_filter:
        header = f"[OTT 추천 후보 — {', '.join(ott_filter)} 매칭, 의미 유사도 순]"
    else:
        header = "[OTT 추천 후보 — 의미 유사도 순]"
    lines = [header]
    for i, m in enumerate(results, 1):
        title = m.get("title_ko") or m.get("title_en") or "(제목 없음)"
        year = m.get("year") or "?"
        genres = ", ".join(m.get("genres") or [])
        overview = (m.get("overview") or "").strip()
        if len(overview) > OVERVIEW_LIMIT:
            overview = overview[:OVERVIEW_LIMIT] + "…"
        vote = m.get("vote_average")
        otts = m.get("ott_kr") or []

        line = f"{i}. {title} ({year})"
        if genres:
            line += f" / 장르: {genres}"
        if overview:
            line += f" / {overview}"
        if vote:
            line += f" [TMDB 평점 {vote:.1f} — 참고용]"
        line += f" / 시청: {', '.join(otts) if otts else '한국 OTT 미공개'}"
        lines.append(line)
    return "\n".join(lines)


def _has_any_ott(movie: dict, ott_filter: list[str]) -> bool:
    """ott_kr에 ott_filter의 플랫폼이 하나라도 있으면 True. 대소문자 무시."""
    otts_lower = {o.lower() for o in (movie.get("ott_kr") or [])}
    return any(p.lower() in otts_lower for p in ott_filter)


def _is_fresh() -> bool:
    if not (NPY_PATH.exists() and PKL_PATH.exists() and CATALOG_PATH.exists()):
        return False
    return NPY_PATH.stat().st_mtime >= CATALOG_PATH.stat().st_mtime


def _build(movies: list[dict]) -> tuple[np.ndarray | None, list[int]]:
    vectors: list[np.ndarray] = []
    ids: list[int] = []
    for i, m in enumerate(movies):
        text = _text_for(m)
        try:
            resp = _client.embed(model=EMBED_MODEL, input=text)
            v = np.array(resp["embeddings"][0], dtype=np.float32)
        except Exception as e:
            print(f"[embedding] id={m.get('id')} {m.get('title_ko')} 실패: {type(e).__name__}: {e}")
            continue
        norm = float(np.linalg.norm(v))
        if norm < 1e-9:
            continue
        v /= norm
        vectors.append(v)
        ids.append(m["id"])
        if (i + 1) % 50 == 0:
            print(f"[embedding] 진행: {i+1}/{len(movies)}")
    if not vectors:
        return None, []
    return np.stack(vectors), ids


def _text_for(m: dict) -> str:
    """임베딩 입력 — 제목 + 장르 + 줄거리. 빈 필드는 자동 누락."""
    parts = [m.get("title_ko", "")]
    genres = m.get("genres") or []
    if genres:
        parts.append("장르: " + ", ".join(genres))
    overview = (m.get("overview") or "").strip()
    if overview:
        parts.append(overview)
    return " | ".join(p for p in parts if p)


def _save(vectors: np.ndarray, ids: list[int]) -> None:
    NPY_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.save(NPY_PATH, vectors)
    with PKL_PATH.open("wb") as f:
        pickle.dump(ids, f)


def _lazy_load() -> None:
    global _vectors, _ids
    if _vectors is not None and _ids is not None:
        return
    if not (NPY_PATH.exists() and PKL_PATH.exists()):
        return
    try:
        _vectors = np.load(NPY_PATH)
        with PKL_PATH.open("rb") as f:
            _ids = pickle.load(f)
    except Exception as e:
        print(f"[embedding] 인덱스 로드 실패: {type(e).__name__}: {e}")
        _vectors = None
        _ids = None
