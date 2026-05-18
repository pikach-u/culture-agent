import re

import requests
from bs4 import BeautifulSoup

from .base import Performance
from ._venue_region import extract_region

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA, "Accept-Language": "ko-KR,ko;q=0.9"}
_BASE = "https://ticket.yes24.com"
_GENRE_MAIN = _BASE + "/New/Genre/GenreMain.aspx"
_TIMEOUT = 10
SOURCE = "yes24"

# 메인 페이지 nav에서 추출한 장르 코드. 전시는 인터파크가 풍부해 yes24에선 미포함.
GENRE_CODES: dict[str, tuple[str, str]] = {
    "뮤지컬": ("15457", "009_202_002"),
    "콘서트": ("15456", "009_202_001"),
    "연극": ("15458", "009_202_003"),
}

_RANGE_DATE_RE = re.compile(
    r"(\d{4})[.\s]*(\d{1,2})[.\s]*(\d{1,2})?\.?\s*[~\-–]\s*"
    r"(\d{4})[.\s]*(\d{1,2})[.\s]*(\d{1,2})?\.?"
)
# 종료일이 없는 단일 공연 (예: "2026. 06. 28. YES24 LIVE HALL")
_SINGLE_DATE_RE = re.compile(r"(\d{4})[.\s]+(\d{1,2})[.\s]+(\d{1,2})\.?")
_PERF_PATH_RE = re.compile(r"/Perf/(\d+)")


def _parse_dates(detail: str) -> tuple[str, str, str]:
    """detail 텍스트에서 (start, end, 잔여_텍스트) 추출. 잔여 = 날짜 제거 후 공연장."""
    m = _RANGE_DATE_RE.search(detail)
    if m:
        sy, sm, sd, ey, em, ed = m.groups()
        s = f"{sy}-{sm.zfill(2)}-{sd.zfill(2)}" if sd else f"{sy}-{sm.zfill(2)}"
        e = f"{ey}-{em.zfill(2)}-{ed.zfill(2)}" if ed else f"{ey}-{em.zfill(2)}"
        return (s, e, _RANGE_DATE_RE.sub("", detail).strip(" .,~-–"))
    m = _SINGLE_DATE_RE.search(detail)
    if m:
        sy, sm, sd = m.groups()
        s = f"{sy}-{sm.zfill(2)}-{sd.zfill(2)}"
        return (s, s, _SINGLE_DATE_RE.sub("", detail).strip(" .,~-–"))
    return (detail.strip(), "", "")


def fetch(genre_korean: str) -> list[Performance]:
    """예스24 장르 메인 페이지 HTML에서 공연 카드 추출.

    파싱: `a[href*='/Perf/']` 매칭 → title/img/.m2-kvs-detail(날짜+공연장).
    Selector 변경 risk: 사이트 리뉴얼 시 깨질 수 있음 → 호출부에서 빈 list 허용.
    """
    code = GENRE_CODES.get(genre_korean)
    if not code:
        return []
    genre_num, gcode = code
    r = requests.get(
        _GENRE_MAIN,
        params={"genre": genre_num, "Gcode": gcode},
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    items: list[Performance] = []
    seen: set[str] = set()
    for a in soup.select("a[href*='/Perf/']"):
        href = a.get("href", "")
        m = _PERF_PATH_RE.search(href)
        if not m:
            continue
        goods_code = m.group(1)
        if goods_code in seen:
            continue
        seen.add(goods_code)

        # title 속성이 잘려있는 경우(yes24 일부 카드)가 있어 카드 텍스트 우선
        tit_el = a.select_one(".m2-kvs-tit, .tit_pf")
        title = tit_el.get_text(strip=True) if tit_el else ""
        if not title:
            title = (a.get("title") or "").strip()
        if not title:
            continue

        img = a.select_one("img")
        poster = None
        if img and img.get("src"):
            src = img["src"]
            poster = "https:" + src if src.startswith("//") else src

        detail_el = a.select_one(".m2-kvs-detail")
        detail_text = detail_el.get_text(strip=True) if detail_el else ""
        start_date, end_date, venue = _parse_dates(detail_text)
        region = extract_region(venue) or extract_region(detail_text)

        items.append(Performance(
            source=SOURCE,
            goods_code=goods_code,
            title=title,
            venue=venue,
            region=region,
            start_date=start_date,
            end_date=end_date,
            genre=genre_korean,
            poster_url=poster,
            detail_url=f"{_BASE}{href}" if href.startswith("/") else href,
        ))
    return items
