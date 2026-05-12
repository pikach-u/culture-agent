# PROGRESS

> 이 파일은 작업 _일지_. 갱신 규칙은 CLAUDE.md 4부 참조.
> 핵심 두 가지: ① 직전 Stage 1개만 자세히, 이전은 결정 기록(7번)으로 압축
> ② 일반 원칙/함정은 여기 말고 CLAUDE.md

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

**UX 비전 메모** (Stage 5+ 적용):

- 추천 결과는 **항목별로 메시지 분리** 전송 (예: 공연 3개 = 메시지 3개). Stage 2의 "4096자 초과 시 자르기"는 그때까지의 임시 처리.

> 작업 원칙은 CLAUDE.md 1부/2부 참조.

---

## 1. 현재 위치

- **Stage 8 ✅ 완료** (KOFIC + TMDB 결합 + 포스터 첨부) + Stage 7+ 자연어 캘린더 임시 확장
- **🎬 2026-05-12 시연 예정 — 코드 동결 상태**
- 모듈화 리팩터 1회 (2026-05-10): `timeutil.py`, `prompts.py` 분리

---

## 2. 마지막 작업 (2026-05-10)

### Stage 8 — KOFIC 박스오피스 + TMDB 메타데이터 결합 + 포스터 첨부

- **의도**: 영화 추천이 모델 학습 컷오프 이후 작품을 모름 + 디테일 환각 위험. 외부 데이터로 "현재 상영작 + 줄거리/평점/포스터"를 주입해 "안다/모른다" 경계 명확화 + 시연 시각 임팩트 확보.
- **구현**:
  - `src/services/movie.py` — `get_box_office_text(user_message) -> str | None` + `get_poster_url(title) -> str | None`. 추천 키워드 정규식 게이팅 → 매칭 시에만 KOFIC 호출. 24h 모듈 레벨 메모리 캐시 (텍스트 + 포스터 dict).
  - **KOFIC + TMDB 결합**: KOFIC list로 영화명 받은 후 TMDB `search/movie?language=ko-KR`을 `ThreadPoolExecutor(max_workers=10)`로 **병렬 호출** (10편 순차 ≈ 10초 → 병렬 ≈ 2.5초). 결과: `N. 영화명 (개봉) — 평점 X / 줄거리 120자` 형식 + 포스터 URL dict.
  - `agent._build_system_prompt()`에서 `asyncio.to_thread`로 sync 호출 감쌈 → 시스템 프롬프트 동적 주입 + hint("list에 있으면 안다고 / 평점·줄거리 활용 / 디테일 모르면 모른다고 / 영화 제목은 list 그대로").
  - `handlers.ai_message`에 `_send_recommendation_part()` 신설: `[N] 제목 (...)`에서 제목 추출 → `movie.get_poster_url(title)` 조회 → 있으면 `reply_photo(photo=URL, caption=part)`, 없거나 텔레그램 거부 시 `reply_text` fallback. caption 1024자 제한 처리.
  - `KOFIC_API_KEY` + `TMDB_API_KEY` config 추가 (둘 다 fallback — 없으면 빈 텍스트/포스터 반환). `requirements.txt`에 `requests==2.32.3` 추가.
- **검증**: 추천 키워드 질문 → KOFIC+TMDB list 주입 ✅ (1629자) / 첫 호출 2.45초 → 두 번째 0.0000초 (캐시 hit) ✅ / 일반 질문 → 네트워크 호출 X ✅ / 1위 영화 포스터 URL 정상 ✅ / TMDB 매칭 실패한 영화(짱구·란12.3 같은 너무 일반 단어/신작) → KOFIC 정보만 표시 fallback ✅.
- **의도된 한계**: TMDB 매칭은 영화명 첫 search 결과 사용 — 동명이인/유사 제목 영화 잘못 매칭 가능. 개봉연도 비교 disambiguate는 미구현 (필요성 발생 시 추가).

### 코드 모듈화 리팩터 (2026-05-10)

- **의도**: 중복 상수 + 긴 프롬프트 텍스트로 `agent.py`가 비대.
- **구현**:
  - `src/timeutil.py` 신규 — `KST`, `WEEKDAYS_KO` 단일 정의. agent/calendar/movie/handlers 4곳에서 import.
  - `src/services/prompts.py` 신규 — `SYSTEM_INSTRUCTION` + `FREE_SLOTS_HINT` + `BOX_OFFICE_HINT`.
  - agent.py 145줄 → 105줄. handlers.py의 어색한 `from src.services.calendar import KST` 의존 제거.
- **검증**: 전 모듈 import 통과.

### Stage 7+ 자연어 캘린더 추가 (2026-05-11, 시연용 임시)

- **의도**: 사용자가 "2번째 영화 내일 저녁 7시에 캘린더 기록해줘" 같은 자연어로 일정 추가하면 자동 처리. Stage 7은 `/add` 명시 명령만 채택했으나 시연 친화 위해 자연어 분기 보강. 작은 모델 자연어→구조화는 Stage 4 교훈상 risk → handlers 단에서 정규식 + 직전 추천 컨텍스트로 직접 처리.
- **구현**:
  - `src/services/nlcal.py` 신규 — `detect_calendar_intent` / `parse_when` / `extract_ordinal` / `extract_title_from_assistant`. 의존성 추가 없음 (정규식만).
  - `agent.get_last_assistant_content(chat_id)` + `movie.match_cached_title(text)` 노출 — handlers가 영화 제목 매핑에 사용.
  - `handlers.ai_message` 진입 즉시 의도 감지 분기 → `_try_natural_calendar_add`. 시간 인식 실패/영화 매칭 실패 시 사용자 안내 + 처리 종료(LLM 호출 안 함). 종료시간 = 시작 + 2h default.
  - 시간 파싱 커버: 상대(오늘/내일/모레/글피), 절대(M월 N일, M/N), period(오전/오후/저녁/밤/아침/새벽), 휴리스틱(period 없는 8시 미만은 영화시간 PM 가정). 어미 활용 허용 (`잡아줘`, `넣어줘` 등).
  - 영화 ordinal: `2번째` / `두 번째` / `세 번째`... 한글 1~10 매핑.
- **검증**: 의도 감지 7케이스 ✓ / 시간 파싱 9케이스 ✓ (상대·절대·period·휴리스틱) / ordinal 6케이스 ✓ / 통합 케이스 "2번째 영화 내일 저녁 7시... 캘린더 기록해줘" → 의도/시간/ordinal/제목/종료시간 모두 정확 추출 ✓.
- **의도된 한계 (시연 후 정식화 검토)**: 요일 표현("토요일 저녁") 미지원 / 시간 휴리스틱(7시 → 19시)은 영화 컨텍스트 가정이라 다른 도메인엔 부정확 / 영화 제목 fallback은 KOFIC 캐시 부분일치만 — 모델 추천에 KOFIC 외 영화 있으면 매칭 실패.

> Stage 6+7 작업 내용은 7번 결정 기록 참조.

---

## 3. 다음 세션 첫 작업 (Stage 9: 추천 로직 통합)

### 3-1. 사전 준비

- 별도 외부 API 발급 없음 (Stage 9 범위에 따라 결정).
- 의의: 취향·시간·위치를 묶어 **하나의 추천 응답**으로 — 지금까지 흩어져 있던 캘린더 빈 시간(Stage 6) + KOFIC list(Stage 8) + 모델 지식(Stage 5)을 사용자 맥락에 맞게 결합. 음식점/예매 링크는 외부 데이터 의존 → Stage 10 크롤링과 묶을지 별도 결정.

### 3-2. 환경 셋팅 (변동 없음)

```powershell
cd C:\Users\ziwon\OneDrive\Desktop\claude\culture-agent
.\venv\Scripts\Activate.ps1
python main.py
```

### 3-3. Stage 9 결정 필요 항목 (계획 → 승인 → 구현)

1. **취향 저장 매체**: 대화 기억(Stage 3) 안에 묻기 vs `chat_id`별 명시 프로파일(`{선호 장르, 선호 시간대, ...}` dict). 후자가 추천 일관성 ↑, 단순함 ↓ — 트레이드오프.
2. **저장 영속성**: 메모리 vs SQLite. 시연 친화면 메모리, 장기 사용이면 SQLite (3-4 후속 검토 후보의 "장기 사용자 프로파일"과 동일 결정).
3. **위치 입력**: 사용자가 명시 입력(`/setlocation`) vs 매 추천 시 질문 vs 생략. 시연 단순화 위해 명시 입력 권장.
4. **추천 응답 구조**: 영화 + 시간 + (옵션) 음식점/링크를 한 메시지에 넣기 vs 항목별 분리. Stage 5 분리 패턴 일관성 ↔ 시간/장소 정보가 영화 항목에 묶여야 자연스러움 — 하이브리드 검토.
5. **음식점/예매 링크 범위**: Stage 9에 포함 vs Stage 10(크롤링)으로 미룸. 9에서는 추천 통합만, 10에서 크롤링 결합 권장.

### 3-4. 후속 검토 후보 (Stage 9 또는 그 이후)

- **추천 키워드 게이팅 보완** (Stage 8 이슈 1, 시연 후 처리): 현재 `RECOMMEND_KEYWORDS` 정규식에 `신작|개봉작|영화\s*보|관람|영화관|좋은\s*영화|괜찮은\s*영화` 등 미포함 → 매칭 안 되면 KOFIC/TMDB 미주입. 두 보완: (A) 정규식 망 확장, (B) 후속 메시지 컨텍스트 인지(직전 assistant 응답이 `[N]` 패턴이면 force=True). `get_box_office_text(user_message, force=False)` 시그니처 변경 필요.
- **자연어 캘린더 정식화** (Stage 7+ 임시 구현, 시연 후 검토): 현재 정규식 기반 + 영화 도메인 휴리스틱(7시 → 19시 PM). 정식화 옵션 — (A) 요일 표현(토요일·다음 주) 추가, (B) `dateparser` 라이브러리 도입 검토, (C) 영화 제목 fallback에 모델 추천 응답 전체에서 추출(현재는 KOFIC 캐시만). 시연 임시본 그대로 유지 vs 정식화 결정 필요.
- **TMDB 동명영화 disambiguate**: 현재는 `search/movie` 첫 결과 사용. 개봉연도 비교로 정확도 ↑ 가능. 시연 중 오매칭 발견 시 우선 처리.
- **TMDB 감독/출연진 결합**: `/movie/{id}/credits` 별도 호출 필요. 박스오피스 10편 × 추가 호출이라 캐시 24h 전제 + ThreadPoolExecutor로 병렬화하면 비용 OK. 추천 응답 풍부화.
- **장기 사용자 프로파일 (취향 영구 저장)**: SQLite 도입과 묶음. Stage 9 즈음.
- **취향 기반 박스오피스 재정렬 (Stage 10 이후)**: 현재는 KOFIC 순위 그대로 추천 → 박스오피스 list 안에서 사용자 취향 매칭으로 재정렬. 의존: Stage 10 크롤링(장르/감독/배우 등 메타 보강) + Stage 9 취향 프로파일. 미결정: ① 활동 시그널 — 명시 평가(좋아요/별점) vs implicit(추천 후 캘린더 추가 여부, 재질문 등) ② 취향 변화 대응 — **최신 활동 가중치** (시간 감쇠 exponential decay 또는 최근 N건 슬라이딩 윈도우) ③ 가중치 파라미터 튜닝 시점(데이터 쌓인 후 후속 결정). Stage 9 취향 프로파일 스키마 설계 시 "활동 시각(timestamp)" 필드 미리 포함 검토 — 빼먹으면 나중에 마이그레이션 비용 발생.
- **chat_id별 토큰 분리**: 멀티 사용자 캘린더 데이터 누출 방지 (Stage 7 의도된 한계 해결).
- **크롤링 (전시/공연/뮤지컬)**: API로 부족한 도메인. 인터파크/예스24/미술관. Stage 10.
- **chat_id별 `asyncio.Lock`**: race condition 해결.
- **자동 재시도 (transient 에러)**: backoff retry.
- **멀티모달**: 캡션 달린 사진 처리.
- **다른 시간대 지원**: KST 외.
- **Ollama OOM 영구 대응**: NUM_CTX 8192 → 4096.
- **빈 시간 텍스트 캐싱**: TTL 1~5분 메모리 캐시.

---

## 4. 미해결 이슈

- 없음 (Stage 9 작업 시작 가능).
- Stage 3 알려진 한계 2건 + Stage 7 멀티 사용자 토큰 누출 가능성 + Stage 8 TMDB 동명영화 disambiguate 미구현 + **Stage 8 추천 키워드 게이팅 보완(시연 후)** → 3-4번 후속 검토 후보 참조 (의도적 후순위)

---

## 5. 단계별 체크리스트 (각 Stage 한 줄 정의)

- [x] **Stage A**: Claude Code 텔레그램 채널 연동
- [x] **Stage 0**: 환경 셋업 — venv, 패키지, 폴더 구조, .env 검증
- [x] **Stage 1**: Echo bot — 사용자 메시지 그대로 회신 + `/start` 핸들러
- [x] **Stage 2**: LLM API 연동 — Gemini 2.5 Flash → 로컬 Ollama Gemma 4 E2B 마이그레이션
- [x] **Stage 3**: 대화 기억 — 멀티턴 컨텍스트 (사용자별 in-memory)
- [x] **Stage 4**: 외부 정보 활용 (시간 인지) — function calling 시도 후 한계 확인 → context injection 피벗
- [x] **Stage 5**: 첫 도메인 기능 (영화 추천) — 시스템 프롬프트 도메인/형식 지시 + handlers.py 응답 분리 전송
- [x] **Stage 6**: 캘린더 연동 (읽기) — Google Calendar API freebusy + 시스템 프롬프트 주입
- [x] **Stage 7**: 캘린더 일정 추가 (쓰기) — Stage 6과 통합. SCOPES 확장 + `/add` 명령어 + 환각 방지 가드레일
- [x] **Stage 8**: 외부 영화 데이터 — KOFIC 박스오피스 + TMDB 메타(평점/줄거리/포스터) 병렬 결합 + 24h 캐시 + 텔레그램 reply_photo 첨부.
- [ ] **Stage 9**: 추천 로직 통합 ← **다음** — 취향·시간·위치 통합 + 음식점/예매 링크
- [ ] **Stage 10**: 크롤링 — 영화 외 도메인(전시/공연/뮤지컬) 외부 데이터
- [ ] **Stage 11**: 신규 이벤트 자동 알림 — 백그라운드 job + 푸시

---

## 6. Stage별 완료 기준 (DoD) — 최근 Stage만 보존

> 이전 Stage(1~6) DoD는 모두 통과 후 5번 체크리스트로 압축됨.

### 6-1. Stage 7 DoD — ✅ 전부 통과 (2026-05-09)

- [x] SCOPES 변경 후 `token.json` 삭제 → `/connect` 재실행 → 새 권한 동의 화면 확인
- [x] `/add 제목 | YYYY-MM-DD HH:MM | YYYY-MM-DD HH:MM` → "일정 추가 완료" + htmlLink 회신
- [x] Google Calendar 웹/앱에서 추가된 일정 확인
- [x] 잘못된 형식 → 사용법 안내 회신
- [x] 종료 ≤ 시작 → "종료 시간은 시작 시간보다 뒤여야 합니다" 회신
- [x] 자연어 "내일 영화 일정 추가해줘" → 거짓 응답 대신 `/add` 사용법 안내 (환각 방지)
- [x] `/connect` 안 한 상태에서 `/add` → "캘린더 연동이 필요합니다" 회신
- [x] Stage 6 회귀 통과

### 6-2. Stage 8 DoD — ✅ 전부 통과 (2026-05-11, KOFIC + TMDB)

- [x] `KOFIC_API_KEY` 미설정 시 추천 질문 정상 동작 (KOFIC 섹션 빠짐)
- [x] `TMDB_API_KEY` 미설정 시에도 KOFIC만으로 정상 동작 (label "KOFIC", 포스터 첨부 X)
- [x] "영화 추천해줘" → 시스템 프롬프트에 KOFIC + TMDB 결합 list 주입 (1629자)
- [x] 일반 질문 ("안녕") → KOFIC/TMDB 호출 안 됨 (네트워크 X)
- [x] 두 번째 추천 질문 → 캐시 hit (KOFIC/TMDB 재호출 X, 0.0000초)
- [x] KOFIC/TMDB 장애·타임아웃 → fallback (각 None / 영화별 빈 메타 → KOFIC 정보만)
- [x] TMDB 매칭 실패한 영화 → 평점/줄거리 없이 KOFIC 정보만 표시 (검증: 짱구, 란12.3)
- [x] 포스터 URL 캐시 → 1위 영화 정상 URL 반환
- [x] 텔레그램에서 추천 응답 시 항목별 포스터 첨부 (사용자 텔레그램 검증 ✅)
- [x] 줄거리 220자 컷 + "…" + hint → caption 끝까지 자연스럽게 마무리 (사용자 검증 ✅)
- [x] 추천 응답이 KOFIC 1번부터 순서대로 (TMDB 평점 영향 약화 — 헤더/평점 위치/hint 보정 후 사용자 검증 ✅)

---

## 7. 결정 기록

> 일반 원칙(다른 Stage에도 적용되는 함정/교훈)은 CLAUDE.md 3부에 있음. 여기엔 *프로젝트 특정 결정*만.

### Stage 0 (환경 셋업)

- Python 3.12.3, pip + venv (poetry/uv는 MVP에 오버킬), `src/` 폴더 분리(`bot/` ↔ `services/`).

### Stage 1 (Echo bot)

- python-telegram-bot 22.x async (`Application` + `CommandHandler` + `MessageHandler` + `run_polling`).
- `main.py`는 조립만 (config 로드 + 핸들러 등록 + 폴링).
- `src/config.py`에서 `TELEGRAM_BOT_TOKEN` import 시점 fail-fast.
- `/start` 안내에 Stage 라벨 표기.

### Stage 2 (Gemini → Ollama 마이그레이션)

- 초기: Google Gemini 2.5 Flash (Anthropic 결제 보류 우회). `agent.ask()` provider-agnostic 시그니처.
- 마이그레이션(2026-05-07): 로컬 Ollama Gemma 4 E2B — 학습 환경 강화 + 외부 의존 제거.
- ollama 공식 SDK 0.6.2 + `AsyncClient` 모듈 레벨 싱글톤.
- 호출 옵션: `num_ctx=8192`, `num_predict=1024`, `think=False` (E2B 권장).
- 시스템 프롬프트 3줄 보존: ① generic AI 어시스턴트 ② 한국어 우선 ③ 마크다운 사용 금지.
- 에러 분기: 빌트인 `ConnectionError` (SDK가 httpx 래핑) / `httpx.TimeoutException` / `ollama.ResponseError` / `Exception`.
- Config fail-fast: `TELEGRAM_BOT_TOKEN`만. `OLLAMA_HOST`/`OLLAMA_MODEL`은 fallback.

### Stage 3 (대화 기억)

- in-memory `dict[chat_id, list[dict]]` (봇 재시작 시 초기화). SQLite는 후순위.
- 슬라이딩 윈도우 10턴 (= 메시지 20개) — 8K 컨텍스트 한도 내.
- 시그니처: `ask(chat_id, user_message)` + `reset(chat_id)` 추가.
- `/reset` 명령어, 시스템 프롬프트는 히스토리 저장 안 함, 에러/빈 응답 턴은 저장 안 함 (깨끗한 재시도).
- 저장은 4000자 컷 _전_ 원본 (모델이 자기 발화 정확히 기억).

### Stage 4 (시간 인지 — function calling 시도 → context injection 피벗)

- **목표 재정의**: 원래 PROGRESS는 "function calling 구조"였지만 결과는 _"외부 정보 LLM 주입 패턴 학습"_ 으로 일반화. function calling은 한 가지 구현, context injection은 다른 한 가지 — 케이스에 따라 선택.
- **function calling 시도 → 작은 모델 + ollama 통합 한계** (CLAUDE.md 3부에 일반화):
  - gemma4:e2b: 호출 시도는 했으나 ollama Gemma 4 chat template 미완성 → raw text 누출.
  - qwen3.5:4b ("Tools" 태그 있음): GitHub Issue #14745 재현 (stochastic emit). 한국어 품질도 하락.
- **컨텍스트 주입 채택**: `_build_system_prompt()`이 매 호출마다 KST 시간을 동적 삽입. 모델 판단 불필요 → stochasticity 0. 시간 키워드 없는 질문도 자연스러운 시간 인식.
- 모델: gemma4:e2b 복귀 (한국어 품질). tools 코드/registry/turn loop 제거.
- 시간대: KST 고정 (`timezone(timedelta(hours=9))`). `tzdata` 의존성 제거.
- 한계: 다른 시간대 미지원 (필요 시 시차 표 주입 또는 큰 모델 + tool 재시도).

### Stage 5 (영화 추천)

- **범위 좁히기**: 추천 워크플로우만 먼저. 프로파일/외부 데이터는 Stage 6+.
- 첫 도메인: 영화 (모델 학습 데이터 풍부 → 외부 API 없이 동작 검증 가능).
- 데이터 소스: 모델 지식 (환각 risk 수용. Stage 8에서 외부 데이터로 보강).
- 추천 트리거: 자유 대화 (시스템 프롬프트로 모델 분기). `/recommend` 명시 명령 안 만듦 — Stage 4 패턴 일관성.
- 응답 형식: `[N] 제목 (연도)\n설명` + handlers.py 정규식 분리 (`[\d+\]` 2개 이상). agent.ask `-> str` 시그니처 변경 없음.
- 시스템 프롬프트 1차→2차 미세조정 (CLAUDE.md 3부 함정으로 일반화): "특화된"→"특히 강합니다", "(추천 요청일 때만 적용)" 헤더, "한두 줄"→제거, "평범한"→"자연스러운".

### Stage 6 (캘린더 읽기, 2026-05-09)

- 결정 항목 6개 모두 권장값 진행: API=OAuth, 플로우=`InstalledAppFlow.run_local_server` (데스크톱 앱), 토큰=평문 `credentials/token.json`, 데이터 활용=시스템 프롬프트 주입, 권한=`calendar.readonly` (Stage 7에서 확장), 조회 범위=7일.
- 데스크톱 앱 OAuth 클라이언트 타입 (redirect URI 자동 처리, 학습 단순).
- OAuth 동기 + 블로킹 → `asyncio.to_thread`로 감싸 봇 폴링 안 막음.
- `freebusy.query()` 사용 (events.list보다 깔끔 — busy만 받아 inverse).
- Working hours 09:00-23:00 KST 고정, 1시간 미만 슬롯 필터.
- `agent._build_system_prompt()` async화 (freebusy sync + 네트워크 I/O를 to_thread).
- 캐싱 안 함 (매번 freebusy 호출, 학습용 단순 — 후속 검토 후보).

### Stage 7 (캘린더 쓰기, 2026-05-09, Stage 6 통합 진행)

- **사용자 결정 — 옵션 B**: 권장은 옵션 A(읽기로 마무리)였으나 사용자가 "일정이 실제로 추가됐으면 좋겠어"로 6+7 통합 선택.
- **SCOPES 함정**: `calendar.events` + `calendar.readonly` 둘 다 명시 필요. events scope만으로는 freebusy → `403 insufficientPermissions` (CLAUDE.md 3부에 일반화).
- `/add 제목 | YYYY-MM-DD HH:MM | YYYY-MM-DD HH:MM` 명시 명령 (자연어 파싱 미채택 — Stage 4 교훈).
- `add_event(summary, start_dt, end_dt) -> str` (htmlLink 반환). `timeZone="Asia/Seoul"` 명시.
- 시스템 프롬프트 환각 방지 가드레일 (negative instruction): "절대 '추가했어요' 거짓 응답 금지" — 작은 모델에 효과적.
- 종료 ≤ 시작 검증, OAuth 재동의 필수 안내.
- 단일 사용자 가정 유지 (Stage 9+에서 chat_id별 분리).

### Stage 8 KOFIC + TMDB (2026-05-10 KOFIC, 2026-05-11 TMDB 추가 채택)

- **TMDB 채택 경위**: 초기에는 KOFIC만으로 시작 → 사용자가 "TMDB도 받아올게" 결정 (시연 시각 임팩트 + 줄거리·평점 풍부화 가치). 미채택 → 채택 전환은 PROGRESS와 메모리에 기록.
- **결정 항목 권장값 진행**: 결합=KOFIC+TMDB, 호출=추천 키워드 감지 시만, 감지=정규식(Stage 4 교훈), 캐싱=메모리 dict 24h(텍스트+포스터 dict 둘 다), 활용=시스템 프롬프트 주입(Stage 4 교훈) + reply_photo 분기, API 키=`.env` 둘 다 fallback (없어도 graceful degrade).
- **TMDB 호출 병렬화**: `ThreadPoolExecutor(max_workers=10)`로 10편 동시 search/movie 호출 → 순차 ≈10초 → 병렬 ≈2.5초. requests는 sync라 ThreadPool 적합. 시연 친화 응답 속도 우선.
- **추천 키워드 정규식** (`RECOMMEND_KEYWORDS`): `추천|볼\s*만한|볼만|재밌는|재미있는|박스오피스|인기|상영중|상영\s*중|뭐\s*볼|영화\s*뭐`.
- **시스템 프롬프트 hint** (긍정/부정 명령 섞기 — CLAUDE.md 3부 패턴 확장): "list에 있으면 안다고 + 평점/줄거리 활용 + 디테일 모르면 모른다고 + **영화 제목은 list 그대로**". 마지막 한 줄은 `handlers`의 포스터 매칭 정확도 확보용.
- **포스터 매칭 흐름**: LLM 응답의 `[N] 제목 (...)` → `TITLE_FROM_ITEM` 정규식 추출 → `movie.get_poster_url(title)` dict 조회 → 매칭 시 `reply_photo(URL, caption=part)`, 미매칭/실패 시 `reply_text` fallback. caption 1024자 제한 처리.
- **TMDB 매칭은 첫 결과 단순 채택**: 동명/유사 영화 disambiguate 미구현 (3-4 후속 검토). 매칭 실패한 영화(짱구·란12.3 등 너무 일반 단어/신작)는 KOFIC 정보만 표시 — 충분한 graceful degrade.
- **줄거리 컷 = 220자 + "…"** (2026-05-11 사용자 피드백 후 보정): 초기 120자 컷이 너무 짧아 작은 모델이 잘린 list를 그대로 옮김 → caption 끊겨 보임. 220자로 늘리고 잘린 자리에 "…" 명시 + hint에 "list의 줄거리에 '…'가 있으면 잘린 것이므로 그대로 옮기지 말고 자기 한국어 한 줄로 마무리하세요" 추가 → 모델이 잘림을 인지하고 자기 표현으로 마무리하도록 유도.
- **추천 순위 = KOFIC 그대로, 평점은 참고용 약화** (2026-05-11 사용자 피드백 후 보정): 모델이 TMDB 평점 높은 영화(헤일메리 8.2 등)를 KOFIC 1위보다 우선 추천하는 현상 발견. 원인=가설 2(평점이 영화명 옆 강조 위치라 모델이 우선순위 신호로 해석). 보정: ① 헤더 "현재 박스오피스 (KOFIC + TMDB)" → **"현재 한국 박스오피스 순위 (KOFIC 일별 1~10위, 어제 N 기준 — TMDB 메타 결합)"** ② 평점 표기 위치를 영화명 옆 `— 평점 X.X` → 줄 끝 대괄호 `[TMDB 평점 X.X — 참고용]`로 약화 ③ hint에 "list 순서를 그대로 따라 1번부터 순서대로 우선 추천 / TMDB 평점은 참고용… 추천 순위 결정에 사용하지 마세요(글로벌 평점이라 한국 관객 인기와 다름)" 명시. 사용자 검증 OK.
- **모듈 레벨 globals 캐시** (`_cache_text`, `_cache_posters`, `_cache_at`): 박스오피스는 사용자별 다르지 않음 → 단일 캐시. 클래스 안 씀 (CLAUDE.md 1부 2번 단순함 우선).
- **시연 보호 보강** (2026-05-11, 시연 중 KOFIC ReadTimeout 발생 후): ① `KOFIC_TIMEOUT` 5 → 10초 (KOFIC가 가끔 느림) ② 호출 실패 시 24h 만료된 stale 캐시라도 반환 — 시연 중 외부 API 장애 발생해도 직전 데이터로 응답. fail-fast 안 함. 검증: 만료 + 호출 실패 시뮬레이션에서 이전 캐시 반환 ✅, 캐시도 없고 호출도 실패면 None ✅.

### 모듈화 리팩터 (2026-05-10, Stage 외)

- KST/WEEKDAYS_KO 4중복 → `src/timeutil.py` 단일 정의.
- `SYSTEM_INSTRUCTION` + 두 hint → `src/services/prompts.py`. 프롬프트 튜닝 시 한 파일만 수정.
- agent.py 145→105줄. handlers.py의 `from src.services.calendar import KST` 어색한 의존 제거.

---

## 8. 현재 코드 상태

**채워진 파일:**

- `main.py` — 봇 진입점 (`Application` 빌드 + `/start`, `/reset`, `/connect`, `/add`, 텍스트 핸들러 등록 + `run_polling`)
- `src/config.py` — `TELEGRAM_BOT_TOKEN` fail-fast + `OLLAMA_HOST`/`OLLAMA_MODEL` fallback + `CLIENT_SECRET_PATH`/`TOKEN_PATH` + `KOFIC_API_KEY` + `TMDB_API_KEY` (Stage 8, 둘 다 fallback)
- `src/timeutil.py` (모듈화 리팩터 신규) — `KST`, `WEEKDAYS_KO` 단일 정의. agent/calendar/movie/handlers 4곳에서 import.
- `src/bot/handlers.py` — `start_command`, `reset_command`, `connect_command`, `add_command`, `ai_message`, `_send_recommendation_part`, `_try_natural_calendar_add`, `_resolve_title_for_calendar`. `[N]` 패턴 분리(Stage 5), `/connect`(asyncio.to_thread, Stage 6), `/add`(파이프 파싱 + add_event, Stage 7), 추천 항목별 포스터 reply_photo 분기 + caption 1024자 제한 (Stage 8), `ai_message` 진입 즉시 자연어 캘린더 의도 분기 → 시간/ordinal/영화 자동 추출 → add_event (Stage 7+ 자연어 확장).
- `src/services/agent.py` — Ollama AsyncClient 래퍼. `ask(chat_id, user_message)` + `reset(chat_id)` + `get_last_assistant_content(chat_id)` (Stage 7+ 자연어 캘린더용). 사용자별 history dict + 슬라이딩 윈도우. `_build_system_prompt()` 매 호출마다 KST 시간 + (캘린더 연동 시) 빈 시간 + (추천 키워드 매칭 시) KOFIC list 동적 주입. `SYSTEM_INSTRUCTION` + 두 hint는 `prompts.py`에서 import.
- `src/services/calendar.py` (Stage 6+7 신규) — Google Calendar OAuth + freebusy + add_event. `run_oauth_flow()`, `get_free_slots_text()`, `add_event()` 공개. `_load_credentials()` 자동 refresh.
- `src/services/movie.py` (Stage 8) — KOFIC 박스오피스 + TMDB 메타(평점/줄거리/포스터) 병렬 결합 + 추천 키워드 정규식 게이팅 + 24h 메모리 캐시(텍스트 + 포스터 dict). `get_box_office_text(user_message) -> str | None`, `get_poster_url(title) -> str | None`, `match_cached_title(text) -> str | None` (Stage 7+ 자연어 캘린더용) 공개. ThreadPoolExecutor 10병렬로 TMDB 호출 시간 ~2.5초.
- `src/services/prompts.py` (모듈화 리팩터 신규) — `SYSTEM_INSTRUCTION` + `FREE_SLOTS_HINT` + `BOX_OFFICE_HINT`. 프롬프트 튜닝은 이 파일만.
- `src/services/nlcal.py` (Stage 7+ 자연어 캘린더 신규) — 정규식 기반 의도 감지 + 시간 파싱 + ordinal 추출 + assistant 응답에서 [N] 영화 제목 추출. `detect_calendar_intent`, `parse_when`, `extract_ordinal`, `extract_title_from_assistant` 공개. `DEFAULT_DURATION = 2h`. 라이브러리 의존성 추가 없음.
- `requirements.txt` (python-telegram-bot, python-dotenv, ollama, google-api-python-client, google-auth-oauthlib, **requests** ← Stage 8)
- `.gitignore` (`credentials/` 포함), `.env`, `.env.example`
- `README.md` — 프로젝트 개요 + UX 의도

**의도적으로 빈 stub:**

- `src/__init__.py`, `src/bot/__init__.py`, `src/services/__init__.py` — 패키지 마커

**시크릿 파일 위치** (값은 절대 여기 적지 않음):

- 봇 토큰: `.env`의 `TELEGRAM_BOT_TOKEN`
- Google OAuth 클라이언트: `credentials/client_secret.json` (gitignored)
- Google OAuth 토큰: `credentials/token.json` (gitignored, `/connect` 시 자동 생성)
- KOFIC API 키 (Stage 8): `.env`의 `KOFIC_API_KEY`
- TMDB API 키 (Stage 8): `.env`의 `TMDB_API_KEY`

---

## 9. 트러블슈팅

| 증상                                                | 원인                                    | 해결                                                                    |
| --------------------------------------------------- | --------------------------------------- | ----------------------------------------------------------------------- |
| `Activate.ps1 ... 실행할 수 없습니다`               | PowerShell 실행 정책                    | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`  |
| `ModuleNotFoundError: telegram`                     | venv 미활성화                           | `.\venv\Scripts\Activate.ps1` 후 재실행                                 |
| 한글/이모지 출력 깨짐 (`UnicodeEncodeError: cp949`) | Windows 콘솔 인코딩                     | 진입점 `.py` 상단 `sys.stdout.reconfigure(encoding="utf-8")`            |
| `python -c "..."` 인라인 한글 깨짐                  | 인라인은 `.py`의 reconfigure 안 거침    | `$env:PYTHONIOENCODING='utf-8'; python -c "..."`                        |
| `.env` 한글 주석 깨짐                               | 메모장 ANSI 저장                        | UTF-8 에디터(VS Code)로 재저장                                          |
| 봇이 응답 안 함                                     | 토큰 오타 / 봇 미실행                   | 토큰 확인, `Get-Process python` 확인                                    |
| `Conflict: terminated by other getUpdates request`  | 같은 봇 토큰으로 인스턴스 2개 동시 실행 | 기존 프로세스 종료 후 재실행                                            |
| 봇이 "AI 서비스에 연결할 수 없습니다"               | Ollama 데몬 미실행                      | 시작 메뉴/`ollama serve`, 트레이 확인                                   |
| 봇이 "AI 모델 로드에 실패했습니다"                  | 모델 없음 / 로드 실패                   | `ollama list`, `ollama pull gemma4:e2b`                                 |
| Ollama "model requires more memory"                 | OS RAM 부족                             | 다른 프로그램 종료 (보통 0.2~1 GiB 확보), 또는 NUM_CTX 8192→4096        |
| `/connect` 시 "확인되지 않은 앱" 경고               | OAuth 동의 화면 미검증 (테스트 모드)    | "고급" → "안전하지 않은 페이지로 이동". 테스트 사용자에 본인 Gmail 등록 |
| `/add` 시 `403 insufficientPermissions`             | SCOPES 변경 후 기존 token.json 재사용   | `Remove-Item credentials\token.json` 후 `/connect` 재실행               |
| `/connect` 시 브라우저 안 열림 / 콜백 멈춤          | 방화벽 차단 또는 기본 브라우저 미지정   | Windows 방화벽 알림 허용, 기본 브라우저 설정 확인                       |
| `[movie] KOFIC 요청 실패: ReadTimeout`              | KOFIC 서버 일시 지연 / 우리 timeout 짧음 | timeout 10s + stale 캐시 fallback 적용됨(2026-05-11). 봇은 정상 응답 — 시연 보호 동작 |
