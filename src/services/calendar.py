"""Google Calendar OAuth + freebusy 조회 + 빈 시간 슬롯 텍스트 변환 + 일정 추가.

공개 API:
- run_oauth_flow(): InstalledAppFlow로 브라우저 OAuth → token.json 저장. 동기 + 블로킹.
- get_free_slots_text() -> str | None: 향후 N일의 빈 시간을 텍스트로 반환. 토큰 없으면 None.
- add_event(summary, start_dt, end_dt) -> str: primary 캘린더에 이벤트 생성. htmlLink 반환.
"""

from datetime import datetime, time, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.config import CLIENT_SECRET_PATH, TOKEN_PATH

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]
KST = timezone(timedelta(hours=9))
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]

DAYS_AHEAD = 7
WORK_START_HOUR = 9
WORK_END_HOUR = 23
MIN_SLOT_MINUTES = 60


def run_oauth_flow() -> None:
    """OAuth 플로우 실행. 브라우저 띄우고 로컬 콜백 대기. token.json 저장."""
    if not CLIENT_SECRET_PATH.exists():
        raise FileNotFoundError(
            f"client_secret.json이 없습니다: {CLIENT_SECRET_PATH}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH), SCOPES
    )
    creds = flow.run_local_server(port=0)

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")


def _load_credentials() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def get_free_slots_text() -> str | None:
    creds = _load_credentials()
    if creds is None:
        return None

    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        now = datetime.now(KST)
        end = now + timedelta(days=DAYS_AHEAD)

        body = {
            "timeMin": now.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": "Asia/Seoul",
            "items": [{"id": "primary"}],
        }
        result = service.freebusy().query(body=body).execute()
        busy_raw = result["calendars"]["primary"].get("busy", [])
    except Exception as e:
        print(f"[calendar] freebusy query 실패: {type(e).__name__}: {e}")
        return None

    busy_intervals = [
        (
            datetime.fromisoformat(b["start"]).astimezone(KST),
            datetime.fromisoformat(b["end"]).astimezone(KST),
        )
        for b in busy_raw
    ]

    return _format_free_slots(now, end, busy_intervals)


def _format_free_slots(
    now: datetime,
    end: datetime,
    busy_intervals: list[tuple[datetime, datetime]],
) -> str:
    lines = ["향후 7일 빈 시간 (KST, working hours 09-23):"]

    current_day = now.date()
    last_day = end.date()
    while current_day <= last_day:
        day_start = datetime.combine(
            current_day, time(WORK_START_HOUR, 0), tzinfo=KST
        )
        day_end = datetime.combine(
            current_day, time(WORK_END_HOUR, 0), tzinfo=KST
        )
        if current_day == now.date():
            day_start = max(day_start, now)

        free = _subtract_busy(day_start, day_end, busy_intervals)
        slot_strs = [
            f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')}"
            for s, e in free
            if (e - s).total_seconds() >= MIN_SLOT_MINUTES * 60
        ]
        if slot_strs:
            weekday = WEEKDAYS_KO[current_day.weekday()]
            lines.append(
                f"- {current_day.month}/{current_day.day}({weekday}): {', '.join(slot_strs)}"
            )

        current_day += timedelta(days=1)

    if len(lines) == 1:
        lines.append("- 빈 시간 없음")
    return "\n".join(lines)


def add_event(summary: str, start_dt: datetime, end_dt: datetime) -> str:
    """primary 캘린더에 이벤트 생성. 생성된 이벤트의 htmlLink 반환."""
    creds = _load_credentials()
    if creds is None:
        raise RuntimeError("캘린더 연동이 필요합니다. /connect 먼저 실행해주세요.")

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    body = {
        "summary": summary,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Seoul"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Seoul"},
    }
    event = service.events().insert(calendarId="primary", body=body).execute()
    return event.get("htmlLink", "")


def _subtract_busy(
    start: datetime,
    end: datetime,
    busy: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    if start >= end:
        return []

    relevant = sorted(
        [(b_s, b_e) for b_s, b_e in busy if b_e > start and b_s < end]
    )

    free = []
    cursor = start
    for b_s, b_e in relevant:
        if b_s > cursor:
            free.append((cursor, min(b_s, end)))
        cursor = max(cursor, b_e)
        if cursor >= end:
            break
    if cursor < end:
        free.append((cursor, end))

    return free
