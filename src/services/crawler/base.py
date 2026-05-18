from dataclasses import dataclass


@dataclass
class Performance:
    source: str           # "interpark" / "yes24" / ...
    goods_code: str       # 소스별 식별자
    title: str
    venue: str            # 공연장명
    region: str | None    # "서울" / "부산" / ... 추출 실패 시 None
    start_date: str       # ISO "YYYY-MM-DD" (파싱 실패 시 원본 그대로)
    end_date: str
    genre: str            # "뮤지컬" / "콘서트" / "전시" / ...
    poster_url: str | None
    detail_url: str
    rating: float | None = None
