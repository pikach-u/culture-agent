"""다중 소스 통합 fetch. 사이트별 어댑터를 병렬 호출 후 결과 합침.

캐시: 장르별로 (timestamp, list[Performance]) 저장. 24h. Stage 8 movie.py와
동일한 단순 모듈-레벨 dict. 호출 모두 실패 시 stale 캐시 반환(시연 보호).
"""

import concurrent.futures as cf
import time

from . import interpark, yes24
from .base import Performance

_CACHE_TTL = 24 * 3600
_FETCH_TIMEOUT = 15
_cache: dict[str, tuple[float, list[Performance]]] = {}


def _fetch_one(name: str, fn) -> list[Performance]:
    try:
        return fn()
    except Exception as e:
        print(f"[crawler.{name}] fetch error: {type(e).__name__}: {e}")
        return []


def fetch_all(genre_korean: str) -> list[Performance]:
    """장르 한국어("뮤지컬"/"콘서트"/"연극"/"전시")로 모든 소스 병렬 fetch.

    yes24는 GENRE_CODES에 있는 장르만 (없으면 자동 skip). 인터파크는 검색이라
    임의 키워드 OK. 빈 결과 + stale 캐시 있으면 stale 반환.
    """
    now = time.time()
    cached = _cache.get(genre_korean)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    tasks: list[tuple[str, callable]] = [
        ("interpark", lambda: interpark.fetch(genre_korean)),
    ]
    if genre_korean in yes24.GENRE_CODES:
        tasks.append(("yes24", lambda: yes24.fetch(genre_korean)))

    results: list[Performance] = []
    with cf.ThreadPoolExecutor(max_workers=len(tasks)) as ex:
        futures = {ex.submit(_fetch_one, name, fn): name for name, fn in tasks}
        for f in cf.as_completed(futures, timeout=_FETCH_TIMEOUT):
            results.extend(f.result())

    if results:
        _cache[genre_korean] = (now, results)
        return results
    if cached:
        return cached[1]
    return []


def cache_status() -> dict[str, int]:
    """디버깅용: 캐시된 장르별 항목 수."""
    return {g: len(items) for g, (_, items) in _cache.items()}


def iter_cached_items():
    """캐시된 모든 장르의 list[Performance]을 순회. 포스터 조회용."""
    for _, items in _cache.values():
        yield items
