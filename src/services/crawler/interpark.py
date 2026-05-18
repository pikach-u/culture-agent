import json
import re
from typing import Any

import requests

from .base import Performance
from ._venue_region import extract_region

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA, "Accept-Language": "ko-KR,ko;q=0.9"}
_SEARCH_URL = "https://tickets.interpark.com/contents/search"
_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
_TIMEOUT = 10
SOURCE = "interpark"


def _to_iso_date(yyyymmdd: str) -> str:
    if len(yyyymmdd) == 8 and yyyymmdd.isdigit():
        return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
    return yyyymmdd


def _parse_rating(bbs_average: str | None) -> float | None:
    # "509|4.90" -> 4.90 (count|score 형식)
    if not bbs_average or "|" not in bbs_average:
        return None
    try:
        return float(bbs_average.split("|")[1])
    except (ValueError, IndexError):
        return None


def _doc_to_performance(doc: dict[str, Any]) -> Performance:
    goods_code = doc.get("goodsCode", "")
    venue = doc.get("placeName", "")
    return Performance(
        source=SOURCE,
        goods_code=goods_code,
        title=doc.get("goodsName", ""),
        venue=venue,
        region=extract_region(venue),
        start_date=_to_iso_date(doc.get("startDate", "")),
        end_date=_to_iso_date(doc.get("endDate", "")),
        genre=doc.get("category", ""),
        poster_url=doc.get("imagePath") or None,
        detail_url=(
            f"https://tickets.interpark.com/goods/{goods_code}" if goods_code else ""
        ),
        rating=_parse_rating(doc.get("bbsAverage")),
    )


def fetch(keyword: str) -> list[Performance]:
    """검색 페이지 SSR HTML에서 NEXT_DATA prefetch된 docs(최대 20건) 추출.

    검색 API(`/search/ticket`)는 직접 호출 시 404. 대신 검색 페이지가 SSR로
    docs를 NEXT_DATA의 SWR fallback에 embed해두므로 HTML 한 번 fetch로 충분.
    """
    r = requests.get(
        _SEARCH_URL,
        params={"keyword": keyword},
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    m = _NEXT_DATA_RE.search(r.text)
    if not m:
        return []
    data = json.loads(m.group(1))
    fallback = data.get("props", {}).get("pageProps", {}).get("fallback", {})
    for k, v in fallback.items():
        if "/search/ticket" in k and isinstance(v, list) and v:
            docs = v[0].get("docs", [])
            return [_doc_to_performance(d) for d in docs]
    return []
