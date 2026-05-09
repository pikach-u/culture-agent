# PROGRESS

문화생활 추천 텔레그램 에이전트 — 진행 일지.

> ⚠️ 시크릿(봇 토큰, API 키 등)은 절대 이 파일에 적지 말 것. 위치만 메모.

---

## 0. 프로젝트 개요

**목표**: 사용자의 캘린더 빈 시간을 분석해 취향 기반 전시/영화/공연을 추천하고,
시간·위치 고려한 일정과 주변 음식점, 예매 링크까지 제안하는 텔레그램 봇.
신규 이벤트 자동 알림 포함.

**환경**:
- 작업 경로: `C:\Users\ziwon\OneDrive\Desktop\claude\culture-agent`
- 플랫폼: Windows 10, PowerShell
- 언어: Python 3.12.3

**작업 원칙** (중요):
- 사용자가 명시한 Stage 범위만 작업한다. 다음 Stage 코드를 미리 만들지 않는다.
- 학습 중심 프로젝트라 한 단계씩 천천히 — "빠른 결과"보다 "한 줄씩 이해" 우선.
- 코드 변경 전에 먼저 무엇을/왜 할지 글로 설명하고 사용자 OK 받는다.

**UX 비전 메모** (Stage 5+ 적용):
- 추천 결과는 **항목별로 메시지 분리** 전송 (예: 공연 3개 = 메시지 3개). Stage 2의 "4096자 초과 시 자르기"는 그때까지의 임시 처리.

---

## 1. 현재 위치

- **Stage 6 + Stage 7 ✅ 완료 → Stage 8 진입 직전**

---

## 2. 마지막 작업 (2026-05-09)

### Stage 2 LLM 교체: Gemini → 로컬 Ollama (Gemma 4 E2B)
- Anthropic 결제 우회로 도입했던 Gemini를 로컬 추론(학습 환경)으로 교체
- ollama 공식 Python SDK 0.6.2 + Ollama 데몬 0.23.1 + `gemma4:e2b` 모델
- 모듈 레벨 `AsyncClient` 싱글톤, `num_ctx=8192`, `num_predict=1024`, `think=False`
- 에러 분기: 빌트인 `ConnectionError` (SDK가 `httpx.ConnectError`를 래핑) / `httpx.TimeoutException` / `ollama.ResponseError` + 광범위 `Exception`
- 시스템 프롬프트 3줄 그대로 보존
- 검증 통과: 한/영 응답, 마크다운 미사용, 데몬 오프 시 친화 메시지, Ctrl+C 정상 종료

### Stage 3 대화 기억 구현
- 사용자별 in-memory `dict[chat_id, list[dict]]`로 직전 10턴(=메시지 20개) 슬라이딩 윈도우 보관
- 시그니처 변경: `agent.ask(chat_id, user_message)` / `agent.reset(chat_id)` 추가
- `/reset` 명령어 추가, `/start` 라벨 `(Stage 3: 대화 기억)` 갱신 + `/reset` 안내 한 줄
- 에러 발생 턴 / 빈 응답은 히스토리에 저장 안 함 (깨끗한 재시도)
- 시스템 프롬프트는 매 호출마다 messages 맨 앞에 새로 주입 (히스토리엔 저장 X)
- 저장은 4000자 컷 *전* 원본 (모델이 자기가 한 말을 정확히 알도록)
- 검증 통과: 멀티턴 이름 기억, `/reset` 초기화, 사용자별 분리, 에러 시 깔끔 복구

### Stage 4 외부 정보 활용 (시간 인지) — function calling 시도 후 context injection으로 피벗
- **의도**: agent가 현재 시간을 알고 답변에 자연스럽게 반영. 장기 비전(시간 키워드 없는 추천 요청에도 시간대 자동 반영)의 토대.
- **시도 1: gemma4:e2b + function calling**: `get_current_time(timezone)` 함수 + `TOOLS_SCHEMA` (ollama `tools=[...]`) + 최대 3턴 turn loop 구현. 모델이 호출은 시도했으나 ollama 측 Gemma 4 chat template에 tool_call 추출 로직 미완성 → 출력이 `content`에 raw 텍스트(`get_current_time{timezone:<|"|>Asia/Seoul<|"|>}`)로 누출. ollama 라이브러리 페이지에서 Gemma 4의 "Tools" 태그 부재가 일치 신호.
- **시도 2: qwen3.5:4b (Tools 태그 모델로 교체)**: 첫 호출은 동작했으나 GitHub Issue #14745 ("qwen3.5 sometimes prints out tool call instead of executing it") 그대로 재현 — stochastic하게 emit/skip. 한국어 품질도 gemma4:e2b 대비 한 단계 하락. 종합 미달.
- **결정: gemma4:e2b 유지 + 컨텍스트 주입으로 피벗**:
  - `_build_system_prompt()`이 매 호출마다 시스템 프롬프트에 KST 현재 시간을 동적 삽입 (`현재 시간 (KST): 2026년 05월 07일 HH시 MM분 (요일)`)
  - 모델은 도구 판단 없이 *항상* 시간을 알고 자연스럽게 답변 → "주말 뭐 할까?" 같은 시간 키워드 없는 질문에도 시간 인식 가능
  - tools 관련 코드 전부 제거 (`TOOLS_SCHEMA`, `_TOOL_REGISTRY`, `_execute_tool`, `get_current_time`, turn loop, `MAX_TOOL_TURNS`)
  - `tzdata` 의존성 제거 — KST 고정이라 `timezone(timedelta(hours=9))` 만으로 충분
  - `/start` 라벨 `(Stage 4: 시간 인지)`
- **트레이드오프**: LA/도쿄 등 다른 시간대 미지원 (한국 기준만). 필요 시 Stage 5+에서 (a) 시차 표 주입 또는 (b) 큰 모델로 tool 재시도. 학습 가치는 오히려 더 큼 — 두 패턴(tool / context injection) trade-off 직접 체감.

### Stage 5 첫 도메인 기능 (영화 추천)
- **의도**: 일반 챗봇 → 도메인 특화 추천 봇으로 첫 진입. 외부 데이터 통합은 Stage 6/7 영역이라 지금은 모델 학습 지식만 사용 (모델 환각 risk 수용).
- **시스템 프롬프트 도메인 지시 추가**: 영화 추천 페르소나 + 응답 형식(`[1] 제목 (연도)\n설명`) + 가드레일 (확실한 것만 추천, 영화 무관 질문엔 일반 답변).
- **응답 분리 전송**: `handlers.py`가 `[N]` 패턴 2개 이상 감지 시 정규식 lookahead로 split → 각 항목을 *별도 `reply_text`* 로 전송. UX 비전(0번)의 "항목별 메시지" 첫 적용. `agent.ask -> str` 시그니처는 그대로 유지 (split은 handlers 책임).
- **시스템 프롬프트 1차 미세조정**: 도입 후 "답변이 심플해졌다"는 관찰 → (a) "특화된" → "특히 강합니다" (페르소나 좁히지 않기) (b) 추천 지침 헤더에 "(추천 요청일 때만 적용)" 명시 (스코프 분리) (c) "한두 줄 설명" → "설명" (길이 제한 제거) (d) "평범한 텍스트" → "자연스러운 한국어" (verbosity 허용). **작은 모델은 instruction을 잘 compartmentalize 못 해서 한 영역의 brevity 지시가 다른 영역으로 새는 현상 직접 체감**.
- **검증 통과**: 분리 전송 정상, 추천 후 후속 질문(멀티턴+추천 컨텍스트) 정상, 데몬 오프 회복, `/reset` 동작.
- **의도된 한계**: 모델 학습 데이터 컷오프 → 최신작 모름 + 디테일 환각 가능. 추천 설명도 모델 자율로 짧음. Stage 6/7에서 외부 데이터 통합으로 해결 예정.

### Stage 6 캘린더 연동 (읽기) — 2026-05-09
- **의도**: 사용자 캘린더 빈 시간을 추천 응답에 자연스럽게 반영. 장기 비전(시간·공간 맥락 추천)의 토대.
- **구현**:
  - `src/services/calendar.py` 신규 — `run_oauth_flow()`, `get_free_slots_text()`, `_load_credentials()`, `_format_free_slots()`, `_subtract_busy()`
  - `src/config.py`에 `CLIENT_SECRET_PATH`, `TOKEN_PATH` 경로 상수 추가 (`PROJECT_ROOT / credentials/`)
  - OAuth: `InstalledAppFlow.run_local_server(port=0)` — 동기 + 블로킹. `connect_command`에서 `asyncio.to_thread`로 감싸 봇 폴링 안 막음.
  - 자동 토큰 refresh: `creds.expired and creds.refresh_token` 분기.
  - freebusy: `service.freebusy().query()`로 향후 7일 busy 슬롯 → working hours 09-23 안에서 inverse → "5/9(토): 19:30-23:00" 형태 텍스트.
  - 시스템 프롬프트 주입: `agent._build_system_prompt()`을 async로 변경 + `await asyncio.to_thread(calendar_service.get_free_slots_text)`. 토큰 없으면 None → 섹션 그냥 빠지고 일반 추천 동작.
- **검증 통과**: `/connect` → 브라우저 OAuth → `token.json` 저장 → 시간 키워드 질문에 빈 시간 자연 반영.

### Stage 7 캘린더 일정 추가 (쓰기) — 2026-05-09 (Stage 6과 통합 진행)
- **의도**: 봇이 "일정 추가했어요" 응답하지만 실제 캘린더엔 안 만들어지는 환각 문제 직접 해결. 사용자 결정: "옵션 A(읽기 마무리)" 대신 "옵션 B(6+7 통합)" — "일정이 실제로 추가됐으면 좋겠어".
- **SCOPES 확장**: `calendar.readonly` → `calendar.events`. 본인 캘린더 이벤트 read+write. 전체 `calendar` scope는 안 씀(캘린더 자체 생성 권한 불필요).
- **`add_event(summary, start_dt, end_dt) -> str`**: `service.events().insert(calendarId="primary", body={...})` → `htmlLink` 반환. `timeZone="Asia/Seoul"` 명시.
- **명령어**: `/add 제목 | YYYY-MM-DD HH:MM | YYYY-MM-DD HH:MM`. 자연어 파싱은 작은 모델 한계(Stage 4 경험)로 명시 명령으로 우회. 파이프 구분 + "종료 ≤ 시작" 검증.
- **시스템 프롬프트 환각 방지 가드레일**: "캘린더 일정 추가/수정은 직접 할 수 없습니다. 사용자가 요청하면 '/add ...' 형식으로 안내만 하세요. 절대 '일정을 추가했어요' 같은 거짓 응답을 하지 마세요." 추가.
- **OAuth 재동의 필요**: SCOPES 변경 → 기존 `token.json` 무효 → 삭제 후 `/connect` 재실행 (사용자 안내 포함).
- **검증 통과**: `/add` 정상 추가 + Google Calendar 웹/앱에서 일정 보임. 자연어 "내일 영화 일정 추가" 요청 시 봇이 거짓 응답 대신 `/add` 사용법 안내 (환각 방지 동작).
- **의도된 한계**: 단일 사용자(`token.json` 1개)라 멀티 사용자 시 캘린더 데이터 누출 위험 → Stage 9+에서 chat_id별 토큰 분리 검토.

### Stage 6/7 진행 중 환경 이슈
- **Ollama OOM**: gemma4:e2b 로드 시 "model requires more system memory (5.4 GiB) than is available (5.2 GiB)". 다른 프로그램 일부 종료로 0.2 GiB 확보하면 해결. 영구 발생 시 `NUM_CTX 8192 → 4096` 검토 (KV 캐시 절반).

### Stage 3 알려진 한계 (Stage 6+에서 검토, Stage 4~5 진행 중에도 변동 없음)
- **동일 chat_id 동시 메시지 race condition**: `_history`는 일반 dict이고 `ask()`는 async. `asyncio.Lock` per chat_id 5줄 추가로 해결 가능. 단일 사용자 학습 환경에선 재현 어려워 후순위.
- **사진/스티커 등 비텍스트 메시지**: `filters.TEXT & ~filters.COMMAND` 필터가 막아줘서 `update.message.text`는 항상 채워져 있음. 캡션 달린 사진도 현재는 무시됨. 멀티모달 / 캡션 처리 정책은 Stage 6+에서 결정.

---

## 3. 다음 세션 첫 작업 (Stage 8: 외부 영화 데이터)

### 3-1. 사전 준비
- **KOFIC API 키 발급** (영화진흥위원회 OpenAPI) — 박스오피스/현재 상영작 list. 회원가입 후 무료 발급.
- **TMDB API 키 발급** — 영화 메타데이터(줄거리/포스터/평점). themoviedb.org 회원가입 후 무료 발급.
- 의의: 영화 추천이 모델 학습 지식만으로는 컷오프 이후 작품 모름 + 디테일 환각 가능. 외부 데이터로 "현재 상영작 + 신뢰 가능한 메타데이터"를 추천 응답 시점에 주입.

### 3-2. 환경 셋팅 (변동 없음)
```powershell
cd C:\Users\ziwon\OneDrive\Desktop\claude\culture-agent
.\venv\Scripts\Activate.ps1
python main.py
```

### 3-3. Stage 8 결정 필요 항목 (계획 → 승인 → 구현)
1. **데이터 소스 결합 방식**: KOFIC(상영작 list) + TMDB(메타) 결합 vs TMDB만 사용. KOFIC + TMDB가 한국 시점 정확.
2. **호출 시점**: 매 메시지마다 vs 추천 키워드 감지 시만. 후자가 효율 (대부분 메시지는 추천 아님).
3. **추천 키워드 감지**: 모델한테 분기 시키기 vs 정규식/키워드 매칭. Stage 4 경험상 작은 모델 신뢰 어려움 → 정규식 권장.
4. **캐싱 전략**: 박스오피스는 일 1회 갱신 → 메모리 dict + TTL 24h. TMDB 메타는 영화 ID별 캐시.
5. **데이터 활용 형식**: 시스템 프롬프트 주입(현재 상영작 list 형태) vs tool 호출. Stage 4 경험상 주입 권장.
6. **API 키 저장**: `.env`의 `KOFIC_API_KEY`, `TMDB_API_KEY`. 영화 추천 시에만 필요하므로 fail-fast 안 함 (없으면 모델 지식만으로 fallback).

> ⚠️ 1단계 (계획) 건너뛰고 바로 코드 짜지 말 것. 본 프로젝트의 작업 원칙(0번).

### 3-4. 후속 검토 후보 (Stage 8 또는 그 이후)
- **장기 사용자 프로파일 (취향 영구 저장)**: SQLite 도입과 묶음. Stage 9 즈음.
- **chat_id별 토큰 분리**: 멀티 사용자 캘린더 데이터 누출 방지 (Stage 7 의도된 한계 해결).
- **크롤링 (전시/공연/뮤지컬)**: API로 부족한 도메인. 인터파크/예스24/미술관 공식 사이트. Stage 10.
- **chat_id별 `asyncio.Lock`**: race condition 해결.
- **자동 재시도 (transient 에러)**: backoff retry.
- **멀티모달**: 캡션 달린 사진 처리.
- **다른 시간대 지원**: KST 외 시간대.
- **Ollama OOM 영구 대응**: NUM_CTX 8192 → 4096 검토.
- **빈 시간 텍스트 캐싱**: 매 메시지마다 freebusy API 호출은 부담. TTL 1~5분 메모리 캐시.

---

## 4. 미해결 이슈

- 없음 (Stage 8 작업 시작 가능)
- Stage 3 알려진 한계 2건 + Stage 7 멀티 사용자 토큰 누출 가능성은 위 2번 섹션 참조 — 의도적으로 후순위 처리

---

## 5. 단계별 체크리스트 (각 Stage 한 줄 정의)

- [x] **Stage A**: Claude Code 텔레그램 채널 연동 (개발자 ↔ Claude 통신용)
- [x] **Stage 0**: 환경 셋업 — venv, 패키지, 폴더 구조, .env 검증
- [x] **Stage 1**: Echo bot — 사용자 메시지를 그대로 되돌려주는 최소 봇 + `/start` 핸들러
- [x] **Stage 2**: LLM API 연동 — Gemini 2.5 Flash → 로컬 Ollama Gemma 4 E2B 마이그레이션 완료
- [x] **Stage 3**: 대화 기억 — 멀티턴 컨텍스트 유지 (사용자별 in-memory)
- [x] **Stage 4**: 외부 정보 활용 (시간 인지) — function calling 시도 후 모델 한계 확인 → context injection 패턴으로 피벗 (KST 시간 시스템 프롬프트 주입)
- [x] **Stage 5**: 첫 도메인 기능 (영화 추천) — 시스템 프롬프트로 도메인/형식 지시 + handlers.py 응답 분리 전송. 외부 데이터/장기 프로파일은 Stage 6+로 미룸
- [x] **Stage 6**: 캘린더 연동 (읽기) — Google Calendar API freebusy로 빈 시간 분석 + 시스템 프롬프트 주입. OAuth `/connect`로 토큰 관리.
- [x] **Stage 7**: 캘린더 일정 추가 (쓰기) — Stage 6과 통합 진행. SCOPES 확장(`calendar.events`) + `/add 제목 | 시작 | 종료` 명령어. 시스템 프롬프트 환각 방지 가드레일.
- [ ] **Stage 8**: 외부 영화 데이터 ← **다음** — KOFIC(현재 상영작) + TMDB(메타데이터) 결합. 추천 환각 해결.
- [ ] **Stage 9**: 추천 로직 통합 — 취향·시간·위치 통합 + 음식점/예매 링크
- [ ] **Stage 10**: 크롤링 — 영화 외 도메인(전시/공연/뮤지컬) 외부 데이터 (인터파크/예스24/미술관 등 여러 사이트)
- [ ] **Stage 11**: 신규 이벤트 자동 알림 — 백그라운드 job + 푸시

---

## 6. Stage 1 완료 기준 (DoD) — ✅ 전부 통과 (2026-05-06)

- [x] `python main.py`로 봇 프로세스 시작
- [x] 텔레그램에서 봇에 임의의 텍스트 전송 → 동일 텍스트 회신 (한글/멀티라인 포함)
- [x] `/start` 명령어 → 안내 메시지 회신
- [x] `Ctrl+C`로 정상 종료 (예외 트레이스백 없이)
- [x] 봇 핸들러 코드는 `src/bot/`에, 환경 로딩은 `src/config.py`에 분리

## 6-2. Stage 2 완료 기준 (DoD) — ✅ 전부 통과

- 초기 (Gemini, 2026-05-06): 한/영 응답, 마크다운 미사용, API 503/429 친화 회신, Ctrl+C 정상 종료, 코드 분리
- 마이그레이션 (Ollama, 2026-05-07): `/start` 라벨 `(Stage 2: Gemma 4 E2B local)`, 데몬 오프 연결 에러 친화 메시지, 시스템 프롬프트 3줄 보존

## 6-3. Stage 3 완료 기준 (DoD) — ✅ 전부 통과 (2026-05-07)

- [x] `python main.py`로 봇 시작 (Stage 2 동작 유지)
- [x] `/start` 안내 갱신 — `(Stage 3: 대화 기억)` 라벨 + `/reset` 안내 포함
- [x] 같은 chat_id에서 멀티턴 컨텍스트 유지 ("내 이름은 X" → "이름 뭐였지?" → 정답)
- [x] `/reset` 명령어 → 안내 회신 + 해당 chat_id의 history만 초기화
- [x] `/reset` 직후 동일 질문 → 모름 (초기화 동작)
- [x] 사용자 A/B 동시 사용 시 기억 분리
- [x] 11턴 이상 길게 대화 후 가장 오래된 턴은 잊음 (슬라이딩 윈도우 동작)
- [x] Ollama 에러 발생 턴은 history에 저장 안 됨 (깨끗한 재시도)
- [x] 봇 재시작 시 history 초기화 (의도된 in-memory 동작)

## 6-4. Stage 4 완료 기준 (DoD) — ✅ 전부 통과 (2026-05-07)

- [x] `python main.py`로 봇 시작 (Stage 3 동작 유지)
- [x] `/start` 라벨 `(Stage 4: 시간 인지)`
- [x] "지금 몇 시야?" → 정확한 KST 시간 응답 (도구 호출 없이 시스템 프롬프트로)
- [x] "오늘 무슨 요일이야?" → 정확한 요일
- [x] 시간 키워드 *없는* 질문에도 답변에 시간 인식 자연스럽게 반영 (장기 비전 정렬 확인)
- [x] 멀티턴 기억 (Stage 3 회귀 통과)
- [x] `/reset` 동작 (Stage 3 회귀 통과)
- [x] Ollama 데몬 끄기 → 친화 메시지 (Stage 2~3 회귀 통과)
- [x] gemma4:e2b 한국어 품질 유지 (qwen3.5:4b 시도 → 한국어 하락 확인 후 복귀)

## 6-5. Stage 5 완료 기준 (DoD) — ✅ 전부 통과 (2026-05-07)

- [x] `/start` 라벨 `(Stage 5: 영화 추천)`
- [x] "영화 추천해줘" → 2~4편이 *각각 별도 메시지* 로 옴 (텔레그램 카드처럼)
- [x] 추천 후 후속 질문 ("방금 첫 번째 영화 더 알려줘") → 멀티턴 컨텍스트 유지 + 형식 깨지지 않은 일반 답변
- [x] 영화 무관 질문 ("안녕", "지금 몇 시?") → 일반 답변 + 추천 형식 안 끌어옴
- [x] `/reset` 동작 (Stage 3 회귀)
- [x] Ollama 데몬 끄기 → 친화 메시지 (Stage 2~3 회귀)
- [x] 시간 인지 + 추천 결합 ("오늘 저녁 영화") — 시간 키워드 자연스러운 반영 관찰됨
- [x] 시스템 프롬프트 미세조정으로 도메인 외 일반 대화 verbosity 회복

## 6-6. Stage 6 완료 기준 (DoD) — ✅ 전부 통과 (2026-05-09)

- [x] `python main.py`로 봇 시작 (Stage 5 동작 유지)
- [x] `/start` 라벨 `(Stage 6+7: 캘린더 연동 + 일정 추가)`
- [x] `/connect` → 브라우저 OAuth → "캘린더 연동 완료!" 회신 + `credentials/token.json` 생성
- [x] 캘린더에 일정 추가 후 "내일 저녁 영화 추천" → 응답이 그 시간 피해서 추천
- [x] `token.json` 없는 상태에서 일반 추천 정상 동작 (빈 시간 섹션 그냥 빠짐)
- [x] OAuth 동의 화면에서 "확인되지 않은 앱" 경고 → "고급" 클릭 후 통과 가능
- [x] Stage 5 회귀 통과 (영화 추천 분리 전송, `/reset`, Ollama 데몬 끄기 친화 메시지)

## 6-7. Stage 7 완료 기준 (DoD) — ✅ 전부 통과 (2026-05-09)

- [x] SCOPES 변경 후 `token.json` 삭제 → `/connect` 재실행 → 새 권한 동의 화면에 "이벤트 만들기/수정" 권한 표시
- [x] `/add 제목 | YYYY-MM-DD HH:MM | YYYY-MM-DD HH:MM` → 봇이 "일정 추가 완료: 제목\n[link]" 회신
- [x] Google Calendar 웹/앱에서 추가된 일정 확인 가능
- [x] 잘못된 형식(파이프 빠짐, 날짜 형식 틀림) → 사용법 안내 회신
- [x] 종료 ≤ 시작 → "종료 시간은 시작 시간보다 뒤여야 합니다" 회신
- [x] 자연어 "내일 영화 일정 추가해줘" → 봇이 거짓 응답 대신 `/add` 사용법 안내 (환각 방지)
- [x] `/connect` 안 한 상태에서 `/add` → "캘린더 연동이 필요합니다" 회신
- [x] Stage 6 회귀 통과 (빈 시간 반영 추천)

---

## 7. 결정 기록

### Stage 0
- **Python 3.12.3 채택** — 최신 안정 라인. 3.13도 후보였으나 일부 패키지 휠 호환성 리스크 회피.
- **패키지 매니저: pip + venv** — poetry/uv는 MVP 단계에 오버킬. 표준 도구로 시작.
- **폴더 구조: `src/` 분리 패턴** — 외부 통신(`bot/`)과 내부 로직(`services/`) 구분. 추후 Discord/웹 등 다른 채널로 확장 시 `services/` 재사용.
- **환경 검증 스크립트로서의 `main.py`** — 단순 `print` 대신 실제 `import` + `.env` 로딩까지 검증. Stage 1에서 echo bot 진입점으로 갈아엎음.

### Stage 1
- **python-telegram-bot 22.x async 패턴** — `Application.builder()` + `CommandHandler` + `MessageHandler` + `run_polling()`. `run_polling`이 SIGINT/SIGTERM 자동 처리해서 별도 try/except 불필요.
- **`main.py`는 "조립" 역할만** — config 로드 + 핸들러 등록 + 폴링 시작. 비즈니스 로직 0줄.
- **`src/config.py`에서 fail-fast** — `TELEGRAM_BOT_TOKEN`이 비어있으면 import 시점에 즉시 `RuntimeError`. 봇 시작했다가 첫 메시지에서 망가지는 것보다 조기 발견이 낫다.
- **핸들러는 별도 모듈** — `src/bot/handlers.py`. Stage 2에서 `echo_message`만 LLM 호출로 교체.
- **`/start` 안내 메시지에 Stage 라벨** — `(Stage N: ...)` 표기로 어떤 단계 봇인지 즉시 식별.

### Stage 2 (초기, Gemini)
- **LLM Provider: Google Gemini 채택 (Anthropic 결제 보류 우회)** — Anthropic API 결제가 즉시 불가하여 무료 티어 Gemini 2.5 Flash로 진행.
- **`agent.ask(user_message: str) -> str` provider-agnostic 시그니처** — 파일명도 `agent.py`. Provider 교체 시 handler/main.py 무수정.
- **google-genai SDK + async client (`client.aio`)** — 구 `google-generativeai`는 deprecated.
- **시스템 프롬프트 3줄**: ① generic AI 어시스턴트 ② 한국어 우선 + 사용자 언어 따라감 ③ 마크다운 사용 금지 (텔레그램 기본 메시지 마크다운 자동 렌더링 X)
- **에러 처리: `errors.APIError` + 광범위 `Exception` 캐치 → fallback 회신** — 봇 절대 죽지 않음. 503/429 자연 검증 통과.
- **`max_output_tokens=1024` 학습용 default** — 비용 통제 + 짧은 응답 학습.
- **`finish_reason` 미처리 (의도된 trade-off)** — Stage 2 단순화. 한 번 짧게 끊긴 사례 발견했으나 일회성 판단. 재발 시 보강.

### Stage 2-bis (Ollama 마이그레이션, 2026-05-07)
- **Provider 전환: Gemini → 로컬 Ollama Gemma 4 E2B** — 학습 환경 강화 + 외부 의존(quota/네트워크) 제거. Anthropic 결제 가능해지면 다시 Claude로 갈 수 있음 (`agent.py` 내부만 교체).
- **클라이언트: ollama 공식 Python SDK 0.6.2** — httpx 직접 호출/OpenAI 호환 엔드포인트는 학습 차원에서 배제. 공식 SDK 끝까지 사용.
- **`AsyncClient` 모듈 레벨 싱글톤** — 함수 호출마다 클라이언트 생성 X.
- **호출 옵션**: `num_ctx=8192` (Stage 3 멀티턴 대비), `num_predict=1024` (Stage 2 max_output_tokens 유지), `think=False` (E2B 권장 + Stage 2 단순화 유지)
- **메시지 구성**: `messages=[{system}, {user}]` — Gemma 4는 system role 네이티브 지원. 시스템 프롬프트 3줄 그대로 보존.
- **에러 분기 (SDK 동작 확인 후 적용)**:
  - 빌트인 `ConnectionError` — SDK가 `httpx.ConnectError`를 잡아 `raise ConnectionError("Failed to connect to Ollama...")`로 래핑하므로 빌트인을 잡아야 함
  - `httpx.TimeoutException` — SDK 미래핑, 직접 import해서 잡음 (httpx는 ollama의 transitive dep)
  - `ollama.ResponseError` — 데몬이 에러 status 반환 시 (모델 없음/로드 실패 포함)
  - `Exception` — 마지막 안전망
- **Config fail-fast 정책**: `TELEGRAM_BOT_TOKEN`만 fail-fast 유지. `OLLAMA_HOST`/`OLLAMA_MODEL`은 비면 기본값(`http://localhost:11434`, `gemma4:e2b`) fallback.
- **에러 메시지 톤**: 시스템 프롬프트와 fallback이 존댓말이라 신규 에러 메시지(연결/모델/타임아웃)도 존댓말로 통일.

### Stage 3
- **대화 기억은 단기(메시지 컨텍스트)와 장기(사용자 프로파일)가 별개** — Stage 3은 단기만. 장기 취향 프로파일은 Stage 5쯤 SQLite + 추출 로직과 함께 도입 (추천 기능이 나오면서 자연스럽게).
- **저장 방식: in-memory `dict[int, list[dict]]`** — 봇 재시작 시 초기화. 학습 단계엔 충분. SQLite는 Stage 5+.
- **기억 길이: 최근 10턴 (= 메시지 20개) 슬라이딩 윈도우** — 8K 컨텍스트 한도 + 학습용 안전선.
- **시그니처 변경: `ask(chat_id: int, user_message: str) -> str`** — Stage 2까진 chat_id 없이 단일 턴이었지만 Stage 3 진입했으니 변경 OK. 별도 함수(`ask_with_memory`)로 안 나눔.
- **`/reset` 명령어 추가** — 사용자가 직접 컨텍스트 초기화. 안내 메시지: "대화 기록을 초기화했습니다."
- **시스템 프롬프트는 히스토리에 저장 안 함** — 매 호출마다 messages 맨 앞에 새로 주입. 프롬프트 변경 시 다음 호출부터 즉시 반영.
- **에러/빈 응답 턴은 히스토리에 저장 안 함** — 사용자가 같은 메시지로 재시도 시 "user: foo" + "assistant: 죄송합니다" 패턴이 모델 컨텍스트에 끼지 않음.
- **저장은 4000자 컷팅 전 원본** — 모델이 자기가 한 말을 정확히 알도록. 사용자가 본 것과 모델이 기억하는 것이 다를 수 있는 4000자 초과 케이스는 작은 모델이라 거의 안 발생.
- **알려진 한계 의도적 후순위 처리**: race condition (asyncio.Lock 미도입), 캡션 사진 처리 (Stage 5+ 멀티모달과 함께)

### Stage 4 (시간 인지, 2026-05-07)
- **목표 재정의**: 원래 PROGRESS는 "function calling으로 외부 함수 호출 구조"였음. 실제 결과는 **"외부 정보를 LLM에 주입하는 패턴 학습"** 으로 일반화됨 — function calling은 한 가지 구현, context injection은 다른 한 가지. 케이스에 따라 선택.
- **function calling 시도 → 작은 모델 + ollama 통합 한계 확인**:
  - gemma4:e2b: 모델이 호출 시도는 했으나 ollama 측 Gemma 4 chat template에 tool_call 추출 로직 미완성 → 출력이 `content`로 raw 텍스트 누출 (`get_current_time{timezone:<|"|>...<|"|>}`). ollama 라이브러리에 Gemma 4 "Tools" 태그 부재가 신호였음.
  - qwen3.5:4b ("Tools" 태그 있음): GitHub Issue #14745 그대로 재현 — stochastic emit. 한국어 품질도 gemma4 대비 하락.
  - 결론: 작은 모델 + ollama tool integration은 2026-05 시점 *불안정*. 학습 흐름이 자꾸 끊기는 비용 > 학습 가치.
- **컨텍스트 주입 채택**:
  - `_build_system_prompt()`이 매 호출마다 KST 현재 시간을 시스템 프롬프트에 동적 삽입.
  - 모델 판단 불필요 → stochasticity 없음. 모든 모델에서 동작.
  - 시간 키워드 없는 질문("주말 뭐 할까?")에도 자연스러운 시간 인식 가능 → 장기 비전(추천 봇)과 자연스럽게 일치.
- **모델: gemma4:e2b 복귀** — 한국어 자연스러움 우선. tools 통합 못 쓰는 약점은 컨텍스트 주입으로 우회.
- **시간대: KST 고정** — `timezone(timedelta(hours=9))`. 한국 DST 없으니 IANA 불필요. `tzdata` 제거 (사용자가 명시적으로 의존성 최소화 선호).
- **`agent.ask()` 시그니처: `(chat_id, user_message)` 그대로 유지** — Stage 3과 동일.
- **`get_current_time` 함수도 제거** — 시간 주입은 `_build_system_prompt()`에 직접 구현. tool 다시 도입 시 함수 부활 또는 새 도구로 가능.
- **알려진 한계 (Stage 5+에서 검토)**: 다른 시간대 미지원, race condition (Stage 3 한계 그대로), 멀티모달.

### Stage 5 (영화 추천, 2026-05-07)
- **범위 좁히기 — 옵션 A 선택**: "추천 + 단순 프로파일 + 자동 추출" 셋 동시 진행하면 디버깅 영역이 너무 넓어짐. 추천 워크플로우만 먼저. 프로파일은 Stage 6+로.
- **첫 도메인: 영화** — 모델 학습 데이터 풍부 → 외부 API 없이 동작 검증 가능. 책/전시/공연은 시의성 중요해서 외부 데이터 단계와 묶임.
- **데이터 소스: 모델 지식 (a)** — 환각 risk 수용. Stage 6/7에서 외부 데이터로 보강. 학습 단계에선 *워크플로우* 검증이 핵심.
- **추천 트리거: 자유 대화 (시스템 프롬프트로 모델이 알아서 분기)** — Stage 4의 "도구 판단 대신 컨텍스트로 모델이 알게 함" 패턴 일관성 유지. `/recommend` 같은 명시 명령어 안 만듦.
- **응답 형식: `[N] 제목 (연도)\n설명`** — 모델에 형식 강제 + handlers.py에서 정규식으로 분리. agent.ask 시그니처 (`-> str`) 변경 없이 split을 handlers 책임으로 둠 (관심사 분리). split 트리거: `[\d+\]` 패턴 *2개 이상*일 때만.
- **모델: gemma4:e2b 그대로** — Stage 4에서 검증된 한국어 품질 유지.
- **시스템 프롬프트 1차 → 2차 미세조정**:
  - 1차: "특화된" 페르소나 + "한두 줄 설명" + "평범한 텍스트로 답하세요"
  - 사용자 관찰: 영화 무관 일반 대화의 답변이 심플해짐
  - 진단: 작은 모델은 instruction을 영역별로 잘 분리 못 함. 한 영역의 brevity/persona 지시가 다른 영역으로 누출.
  - 2차 (적용): 페르소나 다시 넓힘 ("도움이 되는 ... 영화 추천에 특히 강합니다") + 추천 지침 헤더에 스코프 명시("추천 요청일 때만 적용") + "한두 줄" 제거 + "평범한" → "자연스러운"
  - **학습 포인트로 기록**: 시스템 프롬프트 작성 시 "어휘 선택 + 스코프 명시"가 작은 모델에서 결정적.

### Stage 6 (캘린더 연동, 2026-05-09)

- **권장값 결정 모두 그대로 진행**: API=OAuth, OAuth 플로우=`InstalledAppFlow.run_local_server` (데스크톱 앱 + 자동 콜백), 토큰=평문 `credentials/token.json`, 데이터 활용=시스템 프롬프트 주입, 권한=`calendar.readonly`(Stage 7에서 확장), 조회 범위=7일.
- **데스크톱 앱 OAuth 클라이언트 타입 채택** — 웹 애플리케이션 vs 데스크톱 중 데스크톱이 redirect URI 자동 처리. 학습 단순.
- **OAuth는 동기 + 블로킹 → `asyncio.to_thread`로 감싸기** — 봇 폴링 멈춤 방지. python-telegram-bot async 흐름과 google-auth-oauthlib 동기 함수 결합 패턴.
- **`freebusy.query()` 사용** — busy 슬롯만 받아서 inverse(=working hours - busy)로 free 슬롯 계산. `events.list`보다 깔끔.
- **Working hours 09:00-23:00 KST 고정** — 사용자 설정 가능하게 안 함(학습 default). 1시간 미만 슬롯은 필터링.
- **시스템 프롬프트 주입 방식**: 시간(Stage 4) + 빈 시간(Stage 6)을 한 시스템 프롬프트에 합쳐 매 호출마다 동적 생성. 캐싱 안 함(매번 freebusy API 호출). 학습용 단순. 캐싱은 후속 검토 후보.
- **`get_free_slots_text()` 반환 None vs 빈 문자열**: token 없으면 None → 섹션 자체 생략. 빈 시간 0개여도 "- 빈 시간 없음" 한 줄은 있어서 이때만 섹션 포함.
- **`_load_credentials()`에서 자동 refresh + 저장**: expired + refresh_token 있으면 refresh + token.json 덮어쓰기. 사용자 재인증 불필요.
- **`agent._build_system_prompt()` async화**: freebusy 호출이 sync + 네트워크 I/O. `asyncio.to_thread`로 감싸 봇 폴링 안 막음. 호출 체인 ask → \_build\_system\_prompt 모두 async.

### Stage 7 (캘린더 일정 추가, 2026-05-09, Stage 6과 통합 진행)

- **사용자 결정 — 옵션 B 채택**: 원래 권장은 옵션 A(읽기로 마무리, 쓰기는 후속). 사용자가 "일정이 실제로 추가됐으면 좋겠어"라며 6+7 통합 선택. 디버깅 영역 넓어지는 trade-off 인지하고 진행.
- **SCOPES: `calendar.events` + `calendar.readonly` 둘 다 명시** — 본인 캘린더 이벤트 read+write + freebusy 조회. 전체 `calendar` scope 안 씀(캘린더 자체 생성 권한 불필요).
  - **함정 (실측 후 정정)**: `calendar.events`는 events.list/insert만 커버. `freebusy.query`는 `calendar.readonly` (또는 신규 `calendar.events.freebusy`) 권한이 별도 필요. 첫 시도에서 events만 명시 → freebusy 호출 시 `403 insufficientPermissions` 발생 → 두 scope 동시 명시로 해결.
- **`/add` 명시 명령어 채택** (자연어 파싱 안 함):
  - Stage 4에서 작은 모델 + tool 통합 한계 직접 체감. 자연어 → 일정 파라미터 추출은 같은 함정.
  - 명시 형식 `/add 제목 | YYYY-MM-DD HH:MM | YYYY-MM-DD HH:MM`이 안정성 압도적.
  - 사용자가 자연어로 시도하면 봇이 거짓 응답하는 환각 risk → 시스템 프롬프트 가드레일로 차단.
- **시스템 프롬프트 환각 방지 가드레일**: "캘린더 일정 추가/수정은 직접 할 수 없습니다... 절대 '일정을 추가했어요' 같은 거짓 응답을 하지 마세요." 추가. 작은 모델은 instruction을 영역별로 잘 분리 못 한다는 Stage 5 학습 포인트 기반 — 명시적 negative instruction으로 환각 차단.
- **`add_event` 시그니처: `(summary, start_dt, end_dt) -> str`**: htmlLink 반환. 향후 description, location 추가 시 시그니처 확장 OK.
- **`timeZone="Asia/Seoul"` 명시**: ISO 형식에 offset 들어가지만 `timeZone` 필드도 같이 줘서 Google API가 일관되게 해석.
- **종료 ≤ 시작 검증** — 기본 robustness. Google API가 거절하기 전에 짧은 메시지로 사용자 안내.
- **OAuth 재동의 필수**: SCOPES 변경 시 기존 token.json 무효. 사용자 안내 시 `Remove-Item credentials\token.json` + `/connect` 재실행 명시.
- **단일 사용자 가정 유지**: token.json 1개 → 멀티 사용자 시 다른 사람이 봇과 대화하면 본인 캘린더 데이터/추가 권한 누출 가능. Stage 9+에서 chat_id별 분리 검토.

---

## 8. 현재 코드 상태

**채워진 파일:**
- `main.py` — 봇 진입점 (`Application` 빌드 + `/start`, `/reset`, `/connect`, `/add`, 텍스트 핸들러 등록 + `run_polling`)
- `src/config.py` — `TELEGRAM_BOT_TOKEN` fail-fast + `OLLAMA_HOST`/`OLLAMA_MODEL` fallback + Stage 6에서 `CLIENT_SECRET_PATH`/`TOKEN_PATH` 경로 상수 추가
- `src/bot/handlers.py` — `start_command`, `reset_command`, `connect_command`, `add_command`, `ai_message`. Stage 5에서 `[N]` 패턴 분리, Stage 6에서 `/connect` (asyncio.to_thread로 OAuth 감쌈), Stage 7에서 `/add` (파이프 구분 파싱 + add_event 호출).
- `src/services/agent.py` — Ollama AsyncClient 래퍼. `ask(chat_id, user_message)` + `reset(chat_id)`. 사용자별 history dict + 턴 슬라이딩 윈도우. `_build_system_prompt()`이 매 호출마다 KST 현재 시간 + (캘린더 연동 시) 빈 시간을 시스템 프롬프트에 동적 삽입. Stage 7에서 환각 방지 가드레일 추가. async 호출 체인.
- `src/services/calendar.py` (Stage 6+7 신규) — Google Calendar OAuth + freebusy + add_event. `run_oauth_flow()`, `get_free_slots_text()`, `add_event()` 공개. `_load_credentials()` 자동 refresh.
- `requirements.txt` (python-telegram-bot, python-dotenv, ollama, google-api-python-client, google-auth-oauthlib — `tzdata`는 Stage 4에서 제거)
- `.gitignore` (Stage 6에서 `credentials/` 폴더 추가), `.env`, `.env.example`
- `README.md` — 프로젝트 개요 + UX 의도 (Setup 섹션의 Anthropic 언급은 Stage 4 진입 전후 정리 후보)

**의도적으로 빈 stub:**
- `src/__init__.py`, `src/bot/__init__.py`, `src/services/__init__.py` — 패키지 마커

**시크릿 파일 위치** (값은 절대 여기 적지 않음):
- 봇 토큰: `.env`의 `TELEGRAM_BOT_TOKEN`
- (Ollama는 키 없음 — 로컬 데몬)
- Google OAuth 클라이언트: `credentials/client_secret.json` (gitignored)
- Google OAuth 토큰: `credentials/token.json` (gitignored, `/connect` 시 자동 생성)

---

## 9. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `Activate.ps1 ... 실행할 수 없습니다` | PowerShell 실행 정책 | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `ModuleNotFoundError: telegram` | venv 미활성화 (시스템 Python으로 실행됨) | `.\venv\Scripts\Activate.ps1` 후 재실행 |
| 한글/이모지 출력 깨짐 (`UnicodeEncodeError: cp949`) | Windows 콘솔 기본 인코딩 | 진입점 `.py` 상단에 `sys.stdout.reconfigure(encoding="utf-8")` |
| `python -c "..."` 인라인 한글 깨짐 | 인라인은 `.py`의 reconfigure 안 거침 | `$env:PYTHONIOENCODING='utf-8'; python -c "..."` |
| `.env`의 한글 주석 깨짐 | 메모장 ANSI 저장 | VS Code 등 UTF-8 에디터로 재저장 |
| 봇이 응답 안 함 | 토큰 오타 / 봇 미실행 | 토큰 확인, `Get-Process python`으로 봇 살아있는지 확인 |
| `Conflict: terminated by other getUpdates request` | 같은 봇 토큰으로 인스턴스 2개 동시 실행 | 새로 띄우기 전 기존 프로세스 종료 |
| 봇이 "AI 서비스에 연결할 수 없습니다" 회신 | Ollama 데몬 미실행 | 시작 메뉴에서 Ollama 실행 또는 `ollama serve`. 트레이 아이콘 확인 |
| 봇이 "AI 모델 로드에 실패했습니다" 회신 | `OLLAMA_MODEL` 모델 없음 / 로드 실패 | `ollama list`로 설치된 모델 확인, `ollama pull gemma4:e2b` 재실행 |
| Ollama "model requires more system memory (X) than is available (Y)" | OS RAM 부족 | 다른 프로그램 일부 종료 (보통 Chrome 탭/Discord 등으로 0.2~1 GiB 확보), Ollama 재시작, 또는 `NUM_CTX 8192 → 4096` (KV 캐시 절반) |
| `/connect` 시 "확인되지 않은 앱" 경고 | OAuth 동의 화면 미검증 (테스트 모드) | "고급" → "안전하지 않은 페이지로 이동" 클릭. 테스트 사용자에 본인 Gmail 등록되어 있어야 함 |
| `/add` 시 `403 insufficientPermissions` | SCOPES 변경 후 기존 token.json 재사용 중 | `Remove-Item credentials\token.json` 후 `/connect` 재실행 (재동의) |
| `/connect` 시 브라우저 안 열림 / 콜백 멈춤 | 방화벽 차단 또는 기본 브라우저 미지정 | Windows 방화벽 알림 허용, 기본 브라우저 설정 확인 |
| (Stage 2 Gemini 시절) `503 UNAVAILABLE` / `429 RESOURCE_EXHAUSTED` | Stage 2-bis Ollama 전환 후 미발생 | 참고 보존 |

---

## 10. 발견한 함정 (나중에 CLAUDE.md로 옮길 후보)

- 모든 진입점 `.py`에 `sys.stdout.reconfigure(encoding="utf-8")` 필요 (Windows)
- venv 활성화는 새 터미널마다 필요 — **프롬프트 앞에 `(venv)` 붙는지 매번 확인 습관화**. `ModuleNotFoundError: telegram` 류 에러 나면 venv 미활성화 의심 1순위.
- `.env` 편집은 UTF-8 에디터 사용 (VS Code 권장)
- python-dotenv는 `KEY = "value"` (공백+큰따옴표) 형태도 자동 파싱.
- 같은 봇 토큰으로 인스턴스 2개 동시 실행 시 `Conflict` — 기존 프로세스 종료 후 띄우기.
- **Ollama 데몬과 Python SDK는 별개 버전** — 데몬은 `0.23.x` 라인, `pip install ollama`는 `0.6.x` 라인. 둘 다 활성 상태여야 동작.
- **Ollama 데몬은 두 프로세스로 돔** — `ollama app.exe` (트레이 UI) + `ollama.exe` (서버). 끄려면 둘 다 종료. PowerShell: `Stop-Process -Name "ollama","ollama app" -Force`.
- **python-telegram-bot의 `filters.TEXT`** — `message.text`가 truthy일 때만 매치. 캡션 달린 사진은 `message.caption`이라 통과 못 함 (의도적 동작). 멀티모달 도입 시 정책 재검토.
- **async + 모듈 레벨 가변 dict는 race 가능** — 학습 단계 트레이드오프. chat_id별 `asyncio.Lock`으로 5줄에 해결 가능 (Stage 4+ 후보).
