"""시간 관련 공통 상수. KST와 한글 요일 표기를 한 곳에서 관리."""

from datetime import timedelta, timezone

KST = timezone(timedelta(hours=9))
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
