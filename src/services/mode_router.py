"""Stage 13 모드 분기 — OTT 키워드 감지 + 사용자 명시 플랫폼 추출.

공개 API:
- detect_mode(text) -> "ott" | "kofic"
  사용자 메시지에 OTT 키워드가 있으면 "ott", 없으면 기본값 "kofic".
- extract_ott_filter(text) -> list[str]
  사용자가 명시한 OTT 플랫폼 이름들 (catalog의 ott_kr 매칭에 사용).
  빈 list면 필터 없음.

설계:
- 단일 책임: 키워드 정규식만. 분기 결정·임베딩 호출은 agent.py.
- TMDB watch/providers의 provider_name과 매칭 가능한 한국어 표기 사용.
- 키워드 풀은 보수적으로 시작 — 사용자 피드백으로 확장.
"""

import re

# OTT 모드 트리거 (광의) — list에 하나라도 잡히면 RAG 분기
OTT_TRIGGER = re.compile(
    r"넷플릭스|넷플|디즈니플러스|디즈니\+|디플|"
    r"왓챠|티빙|쿠팡플레이|쿠플|애플TV|애플\s*티비|"
    r"웨이브|wavve|OTT|스트리밍|집에서"
)

# 플랫폼 필터 — 그룹별 한 row, ott_kr 비교용 표준명(TMDB provider_name 매칭)
_PLATFORMS = [
    ("Netflix", re.compile(r"넷플릭스|넷플")),
    ("Disney Plus", re.compile(r"디즈니플러스|디즈니\+|디플")),
    ("Watcha", re.compile(r"왓챠")),
    ("TVING", re.compile(r"티빙")),
    ("Coupang Play", re.compile(r"쿠팡플레이|쿠플")),
    ("Apple TV Plus", re.compile(r"애플TV|애플\s*티비")),
    ("Wavve", re.compile(r"웨이브|wavve", re.IGNORECASE)),
]


def detect_mode(text: str) -> str:
    """OTT 키워드 있으면 'ott', 없으면 기본 'kofic'."""
    if text and OTT_TRIGGER.search(text):
        return "ott"
    return "kofic"


def extract_ott_filter(text: str) -> list[str]:
    """사용자 메시지에서 명시된 OTT 플랫폼 추출. 일반 OTT 키워드만 있으면 빈 list."""
    if not text:
        return []
    return [name for name, pat in _PLATFORMS if pat.search(text)]
