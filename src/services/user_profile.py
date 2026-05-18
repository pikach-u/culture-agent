"""사용자 메타 in-memory 저장 (Stage 10 신규).

현재는 region(광역시·도)만. Stage 9 취향 프로파일 도입 시 SQLite 영속화 +
선호 장르/활동 timestamp 등으로 확장 예정 — PROGRESS 3-4 후속 검토 후보 참조.
"""

_data: dict[int, dict[str, str]] = {}


def set_region(chat_id: int, region: str) -> None:
    _data.setdefault(chat_id, {})["region"] = region


def get_region(chat_id: int) -> str | None:
    return _data.get(chat_id, {}).get("region")
