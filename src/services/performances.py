"""공연/전시 추천 서비스 계층 (Stage 10).

데이터는 crawler/ 하위 어댑터들이 처리. 이 모듈은 사용자 메시지 → 장르 매칭 →
시스템 프롬프트 텍스트 + 포스터 조회를 담당. Stage 8 movie.py와 동일한 패턴.
"""

import re
from datetime import date

from src.services.crawler import registry
from src.services.crawler.base import Performance

_KEYWORD_GENRE: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"뮤지컬"), ["뮤지컬"]),
    (re.compile(r"콘서트"), ["콘서트"]),
    (re.compile(r"전시|미술관|박물관"), ["전시"]),
    (re.compile(r"연극"), ["연극"]),
    (re.compile(r"공연|문화생활|볼\s*만한"), ["뮤지컬", "콘서트", "연극", "전시"]),
]
_PER_GENRE_LIMIT = 3  # Stage 10 v2: 작은 모델 일관성 위해 6 → 3 (시스템 프롬프트 길이 ↓)

_TITLE_NORM_PREFIX = re.compile(r"^(뮤지컬|연극|콘서트|전시)\s*")
_TITLE_NORM_PUNCT = re.compile(r"[\s\-_〈〉《》<>\"'\[\]\(\)（）]")


def _normalize(s: str) -> str:
    """제목·공연장 중복 dedupe용 정규화. 장르 prefix + 특수문자 + 공백 제거 + 소문자."""
    if not s:
        return ""
    s = _TITLE_NORM_PREFIX.sub("", s)
    s = _TITLE_NORM_PUNCT.sub("", s)
    return s.lower()


def _status_label(p: Performance, today: date) -> str | None:
    """진행 상태 라벨. end_date < today면 None (list에서 제외)."""
    try:
        end = date.fromisoformat(p.end_date) if p.end_date else None
    except ValueError:
        end = None
    try:
        start = date.fromisoformat(p.start_date) if p.start_date else None
    except ValueError:
        start = None

    if end and end < today:
        return None
    if start and start > today:
        days = (start - today).days
        return f"{days}일 후 시작"
    return "진행 중"


def detect_genres(user_message: str) -> list[str]:
    matched: list[str] = []
    for pattern, genres in _KEYWORD_GENRE:
        if pattern.search(user_message):
            for g in genres:
                if g not in matched:
                    matched.append(g)
    return matched


def get_performance_text(
    user_message: str, user_region: str | None = None
) -> str | None:
    """추천 키워드 매칭 시 장르별 상위 N건을 시스템 프롬프트 텍스트로 포맷.

    Stage 10 v2 보정:
    - end_date < today 공연 제외 + 진행 상태 라벨 추가
    - 사용자 지역 안정 정렬 우선
    - title+venue normalize 키로 dedupe (interpark/yes24 같은 공연 중복 방지)
    - per genre top 3 (시스템 프롬프트 길이 ↓ → 작은 모델 일관성 ↑)
    """
    genres = detect_genres(user_message)
    if not genres:
        return None

    today = date.today()
    sections: list[str] = []
    seen: set[tuple[str, str]] = set()

    for g in genres:
        items = registry.fetch_all(g)
        if not items:
            continue

        active: list[tuple[Performance, str]] = []
        for p in items:
            status = _status_label(p, today)
            if status is None:
                continue
            active.append((p, status))

        ordered = sorted(
            active,
            key=lambda ps: 0 if (user_region and ps[0].region == user_region) else 1,
        )

        unique: list[tuple[Performance, str]] = []
        for p, status in ordered:
            key = (_normalize(p.title), _normalize(p.venue))
            if key in seen:
                continue
            seen.add(key)
            unique.append((p, status))

        if not unique:
            continue

        lines = [f"\n### {g}"]
        for i, (p, status) in enumerate(unique[:_PER_GENRE_LIMIT], 1):
            region_tag = f" [{p.region}]" if p.region else ""
            rating_tag = f" ★{p.rating:.1f}" if p.rating else ""
            lines.append(
                f"{i}. {p.title} — {p.venue}{region_tag} "
                f"({p.start_date}~{p.end_date}){rating_tag} [{p.source}] ({status})"
            )
        sections.append("\n".join(lines))

    return "\n".join(sections) if sections else None


def get_poster_url(title: str) -> str | None:
    """LLM 응답의 제목(괄호 앞)으로 캐시에서 포스터 URL 조회.

    제목이 list 항목 제목을 포함(substring)하면 매칭. movie.get_poster_url 다음
    fallback으로 handlers에서 호출.
    """
    if not title:
        return None
    for items in registry.iter_cached_items():
        for p in items:
            if p.poster_url and p.title and p.title in title:
                return p.poster_url
    return None
