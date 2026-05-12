"""자연어 캘린더 의도 감지 + 시간/영화 ordinal 파싱 (시연용 임시).

작은 모델로 자연어→구조화는 Stage 4 교훈상 risk → 정규식 직접 + 직전 추천 응답 컨텍스트.
지원 표현은 한정적. 미지원이면 None 반환 → handlers가 fallback 안내.

공개 API:
- detect_calendar_intent(text) -> bool
- parse_when(text, now) -> datetime | None  (KST)
- extract_ordinal(text) -> int | None
- extract_title_from_assistant(content, n) -> str | None
- DEFAULT_DURATION
"""

import re
from datetime import datetime, timedelta

from src.timeutil import KST

DEFAULT_DURATION = timedelta(hours=2)

CAL_INTENT_RE = re.compile(
    r"(?:캘린더|일정).{0,10}(?:추가|기록|넣|잡|등록|예약|입력)"
    r"|(?:추가|기록|넣|잡|등록|예약)[가-힣]{0,2}\s*(?:해|할게|할께|줘|놔)"
)

ORDINAL_NUM_RE = re.compile(r"(\d+)\s*번째")
ORDINAL_KO_MAP = {
    "첫": 1, "한": 1,
    "두": 2,
    "세": 3, "셋": 3,
    "네": 4, "넷": 4,
    "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10,
}
ORDINAL_KO_RE = re.compile(rf"({'|'.join(ORDINAL_KO_MAP)})\s*번째")

DATE_REL_MAP = {"오늘": 0, "내일": 1, "모레": 2, "글피": 3}
DATE_REL_RE = re.compile(rf"({'|'.join(DATE_REL_MAP)})")
DATE_MD_RE = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
DATE_SLASH_RE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)")

PERIOD_RE = re.compile(r"(오전|오후|저녁|밤|아침|새벽|낮)")
PERIOD_PM = {"오후", "저녁", "밤"}
PERIOD_AM = {"오전", "아침", "새벽"}
HOUR_RE = re.compile(r"(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?")

ITEM_TITLE_RE = re.compile(r"\[(\d+)\]\s*(.+?)\s*[\(（]")


def detect_calendar_intent(text: str) -> bool:
    return bool(CAL_INTENT_RE.search(text or ""))


def extract_ordinal(text: str) -> int | None:
    m = ORDINAL_NUM_RE.search(text or "")
    if m:
        return int(m.group(1))
    m = ORDINAL_KO_RE.search(text or "")
    if m:
        return ORDINAL_KO_MAP[m.group(1)]
    return None


def extract_title_from_assistant(content: str, n: int) -> str | None:
    if not content:
        return None
    for n_str, title in ITEM_TITLE_RE.findall(content):
        if int(n_str) == n:
            return title.strip()
    return None


def parse_when(text: str, now: datetime) -> datetime | None:
    """자연어 시간 → KST datetime. 시간 인식 실패 시 None."""
    if not text:
        return None

    h_match = HOUR_RE.search(text)
    if not h_match:
        return None
    hour = int(h_match.group(1))
    minute = int(h_match.group(2)) if h_match.group(2) else 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    period_match = PERIOD_RE.search(text)
    if period_match:
        period = period_match.group(1)
        if period in PERIOD_PM and hour < 12:
            hour += 12
        elif period in PERIOD_AM and hour == 12:
            hour = 0
    elif hour < 8:
        # period 없고 8시 미만이면 영화 시간 휴리스틱으로 PM
        hour += 12

    base_date = _extract_date(text, now)
    if base_date is None:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    return datetime.combine(
        base_date,
        datetime.min.time().replace(hour=hour, minute=minute),
        tzinfo=KST,
    )


def _extract_date(text: str, now: datetime):
    m = DATE_REL_RE.search(text)
    if m:
        return (now + timedelta(days=DATE_REL_MAP[m.group(1)])).date()

    m = DATE_MD_RE.search(text) or DATE_SLASH_RE.search(text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        try:
            d = datetime(now.year, month, day).date()
        except ValueError:
            return None
        if d < now.date():
            try:
                d = d.replace(year=now.year + 1)
            except ValueError:
                return None
        return d
    return None
