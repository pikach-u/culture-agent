"""Stage 13 모드 분기 — OTT 키워드 감지 + 사용자 명시 플랫폼 추출.

공개 API:
- detect_mode(text) -> "ott" | "kofic" | None
  명시적 OTT 키워드면 "ott", 명시적 KOFIC(극장) 키워드면 "kofic", 둘 다 없으면 None.
  None인 경우 agent.py가 chat_id별 sticky 또는 기본값으로 결정.
- extract_ott_filter(text) -> list[str]
  사용자가 명시한 OTT 플랫폼 이름들 (catalog의 ott_kr 매칭에 사용).
- detect_temporal(text) -> bool
  "최신/신작/최근/요즘" 등 시간 키워드 감지. embedding 결과를 year 내림차순 재정렬 신호.

설계:
- 단일 책임: 키워드 정규식만. 분기 결정·임베딩 호출은 agent.py.
- TMDB watch/providers의 provider_name과 매칭 가능한 한국어 표기 사용.
- 키워드 풀은 보수적으로 시작 — 사용자 피드백으로 확장.
- Stage 13.1: 명시 키워드 없으면 None 반환 → agent.py에서 sticky 처리.
"""

import re

# OTT 모드 트리거 (광의) — list에 하나라도 잡히면 RAG 분기
OTT_TRIGGER = re.compile(
    r"넷플릭스|넷플|디즈니플러스|디즈니\+|디플|"
    r"왓챠|티빙|쿠팡플레이|쿠플|애플TV|애플\s*티비|"
    r"웨이브|wavve|OTT|스트리밍|집에서"
)

# KOFIC 강제 트리거 — 사용자가 극장을 명시한 경우
KOFIC_TRIGGER = re.compile(r"극장|상영중|상영\s*중|영화관|박스오피스|개봉관")

# 시간 키워드 — embedding 결과 year 내림차순 재정렬 신호
TEMPORAL_TRIGGER = re.compile(
    r"최신|신작|새로\s*나온|새로\s*개봉|요즘|올해|이번\s*달|최근|"
    r"이번\s*주\s*개봉|새\s*나온"
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


def detect_mode(text: str) -> str | None:
    """OTT 키워드면 'ott', 극장 명시면 'kofic', 둘 다 없으면 None (agent가 sticky 처리)."""
    if not text:
        return None
    if OTT_TRIGGER.search(text):
        return "ott"
    if KOFIC_TRIGGER.search(text):
        return "kofic"
    return None


def detect_temporal(text: str) -> bool:
    """'최신/신작/요즘' 등 시간 키워드. OTT 모드 결과 year 내림차순 재정렬용."""
    return bool(text) and bool(TEMPORAL_TRIGGER.search(text))


def extract_ott_filter(text: str) -> list[str]:
    """사용자 메시지에서 명시된 OTT 플랫폼 추출. 일반 OTT 키워드만 있으면 빈 list."""
    if not text:
        return []
    return [name for name, pat in _PLATFORMS if pat.search(text)]
