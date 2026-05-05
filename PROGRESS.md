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

- **Stage 1 ✅ 완료 → Stage 2 진입 직전**

---

## 2. 마지막 작업 (2026-05-06)

- Stage 1 Echo bot 구현 및 검증 완료
- 검증된 항목 (DoD 전부 통과):
  - `python main.py`로 봇 시작 → "Bot 시작 - Ctrl+C로 종료" 출력
  - `/start` → 안내 메시지 회신
  - 텍스트(한글/멀티라인 포함) → 동일 텍스트 회신
  - `Ctrl+C` → 트레이스백 없이 정상 종료
  - 코드 분리: 핸들러 `src/bot/handlers.py`, 환경 로딩 `src/config.py`

---

## 3. 다음 세션 첫 작업

### 3-1. 사전 준비 (Anthropic 콘솔)
1. [console.anthropic.com](https://console.anthropic.com) 로그인 → API Keys → 새 키 발급
2. 발급된 키 복사 (형식: `sk-ant-...`)
3. 결제 정보 등록 필요 (소액 prepay로 시작 권장)

### 3-2. 환경 셋팅 (PowerShell에서)
```powershell
cd C:\Users\ziwon\OneDrive\Desktop\claude\culture-agent
.\venv\Scripts\Activate.ps1            # 새 터미널마다 필요 — 프롬프트에 (venv) 붙는지 확인 필수
code .env                               # ANTHROPIC_API_KEY= 한 줄 추가하고 키 붙여넣기
code .env.example                       # ANTHROPIC_API_KEY= (값 없이) 추가해서 템플릿 갱신
```

### 3-3. Stage 2 결정 사항 (확정됨)

| 항목 | 결정 |
|------|------|
| 모델 | `claude-opus-4-7` (Opus 4.7) — 학습 단계라 품질 우선 |
| SDK 패키지 | `anthropic==0.98.1` (async 클라이언트 사용 — handlers가 async라 자연스러움) |
| 봇 정체성 | Generic AI 어시스턴트 (페르소나는 Stage 5에서 부여) |
| 응답 언어 | 한국어 우선 + 사용자 언어 따라감 (시스템 프롬프트로 지시) |
| 턴 구조 | 단일 턴 (멀티턴은 Stage 3) |
| 파일명 | `src/services/agent.py` (Stage 4+ 도구·추천 확장 대비) |
| `max_tokens` | 1024 |
| Streaming | 비사용 |
| 4096자 초과 처리 | 4000자에서 자르고 "..." 추가 (임시) |
| 에러 메시지 | "죄송합니다. 잠시 후 다시 시도해주세요." 류 사용자 친화체 (트레이스백 노출 X) |
| 타임아웃/재시도 | SDK default |
| `/start` 안내 라벨 | `(Stage 2: Claude AI)` |

### 3-4. Stage 2 작업 절차 (계획 → 승인 → 구현)
1. **계획 단계**: 위 결정사항 기반으로 파일별 변경 계획 글로 설명
2. **승인 단계**: 사용자 OK
3. **구현 단계**: 승인된 계획대로 코드 작성
4. **검증 단계**: 텔레그램에서 봇에게 질문 → Claude 답변 회신 확인 (DoD 6-2 항목)

> ⚠️ 1단계 건너뛰고 바로 코드 짜지 말 것. 이게 본 프로젝트의 작업 원칙(0번).

---

## 4. 미해결 이슈

- Anthropic API 키 미발급 → Stage 2 시작 전 [console.anthropic.com](https://console.anthropic.com)에서 발급 필요

---

## 5. 단계별 체크리스트 (각 Stage 한 줄 정의)

- [x] **Stage A**: Claude Code 텔레그램 채널 연동 (개발자 ↔ Claude 통신용)
- [x] **Stage 0**: 환경 셋업 — venv, 패키지, 폴더 구조, .env 검증
- [x] **Stage 1**: Echo bot — 사용자 메시지를 그대로 되돌려주는 최소 봇 + `/start` 핸들러
- [ ] **Stage 2**: Claude API 연동 ← **다음** — echo 대신 Claude가 답변
- [ ] **Stage 3**: 대화 기억 — 멀티턴 컨텍스트 유지 (사용자별)
- [ ] **Stage 4**: 도구 추가 — Claude tool use로 외부 함수 호출 구조
- [ ] **Stage 5**: 첫 도메인 기능 — 예: "오늘 서울 전시 추천해줘" 류 단순 추천
- [ ] **Stage 6**: 캘린더 연동 — Google Calendar API로 빈 시간 분석
- [ ] **Stage 7**: 추천 로직 — 취향·시간·위치 통합 추천 + 음식점/예매 링크

---

## 6. Stage 1 완료 기준 (DoD) — ✅ 전부 통과 (2026-05-06)

- [x] `python main.py`로 봇 프로세스 시작
- [x] 텔레그램에서 봇에 임의의 텍스트 전송 → 동일 텍스트 회신 (한글/멀티라인 포함)
- [x] `/start` 명령어 → 안내 메시지 회신
- [x] `Ctrl+C`로 정상 종료 (예외 트레이스백 없이)
- [x] 봇 핸들러 코드는 `src/bot/`에, 환경 로딩은 `src/config.py`에 분리

## 6-2. Stage 2 완료 기준 (DoD) — 확정

- [ ] `python main.py`로 봇 프로세스 시작 (Stage 1 동작 유지)
- [ ] 텔레그램에서 봇에 질문 전송 → `claude-opus-4-7` 호출 → 자연어 답변 회신
- [ ] 한국어 질문엔 한국어, 영어 질문엔 영어로 답변
- [ ] `/start` 안내 메시지 갱신 — `(Stage 2: Claude AI)` 라벨 포함
- [ ] API 호출 실패(키 만료/네트워크/rate limit 등) 시 사용자에게 친절한 한 줄 메시지 회신, 봇 프로세스는 죽지 않음
- [ ] Claude 호출 로직은 `src/services/agent.py`에 분리, `handlers.py`는 호출만
- [ ] 응답이 4000자 초과 시 자르고 "..." 추가

---

## 7. 결정 기록

### Stage 0
- **Python 3.12.3 채택** — 최신 안정 라인. 3.13도 후보였으나 일부 패키지 휠 호환성 리스크 회피.
- **패키지 매니저: pip + venv** — poetry/uv는 MVP 단계에 오버킬. 표준 도구로 시작.
- **폴더 구조: `src/` 분리 패턴** — 외부 통신(`bot/`)과 내부 로직(`services/`) 구분. 추후 Discord/웹 등 다른 채널로 확장 시 `services/` 재사용.
- **환경 검증 스크립트로서의 `main.py`** — 단순 `print` 대신 실제 `import` + `.env` 로딩까지 검증. Stage 1에서 echo bot 진입점으로 갈아엎을 예정.

### Stage 1
- **python-telegram-bot 22.x async 패턴** — `Application.builder()` + `CommandHandler` + `MessageHandler` + `run_polling()`. `run_polling`이 SIGINT/SIGTERM 자동 처리해서 별도 try/except 불필요.
- **`main.py`는 "조립" 역할만** — config 로드 + 핸들러 등록 + 폴링 시작. 비즈니스 로직 0줄. Stage 2에서 핸들러 내용물만 바꾸면 main.py는 그대로.
- **`src/config.py`에서 fail-fast** — `TELEGRAM_BOT_TOKEN`이 비어있으면 import 시점에 즉시 `RuntimeError`. 봇 시작했다가 첫 메시지에서 망가지는 것보다 조기 발견이 낫다.
- **핸들러는 별도 모듈** — `src/bot/handlers.py`. Stage 2에서 `echo_message`만 Claude 호출로 교체하면 됨. main.py 무수정.
- **`/start` 안내 메시지에 Stage 라벨** — "(Stage 1: echo bot)" 표기로 어떤 단계 봇인지 즉시 식별 가능. Stage 2부터는 라벨 갱신.

---

## 8. 현재 코드 상태

**채워진 파일:**
- `main.py` — 봇 진입점 (Application 빌드 + 핸들러 등록 + `run_polling`)
- `src/config.py` — `TELEGRAM_BOT_TOKEN` 로딩 + fail-fast 검증
- `src/bot/handlers.py` — `start_command`, `echo_message` (Stage 2에서 `echo_message` 교체 예정)
- `requirements.txt`, `.gitignore`, `.env`, `.env.example`
- `README.md` — 프로젝트 개요 + Setup 명령어 + Requirements

**의도적으로 빈 stub:**
- `src/__init__.py` — 패키지 마커
- `src/bot/__init__.py` — 패키지 마커 (re-export 필요해지면 그때)
- `src/services/__init__.py` — Stage 2에서 Claude 호출 래퍼 추가 예정

**시크릿 파일 위치** (값은 절대 여기 적지 않음):
- 봇 토큰: `.env`의 `TELEGRAM_BOT_TOKEN`
- (Stage 2 추가 예정) Anthropic API 키: `.env`의 `ANTHROPIC_API_KEY`

---

## 9. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `Activate.ps1 ... 실행할 수 없습니다` | PowerShell 실행 정책 | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `ModuleNotFoundError: telegram` | venv 미활성화 (시스템 Python으로 실행됨) | `.\venv\Scripts\Activate.ps1` 후 재실행 |
| 한글/이모지 출력 깨짐 (`UnicodeEncodeError: cp949`) | Windows 콘솔 기본 인코딩 | 진입점 `.py` 상단에 `sys.stdout.reconfigure(encoding="utf-8")` |
| `.env`의 한글 주석 깨짐 | 메모장 ANSI 저장 | VS Code 등 UTF-8 에디터로 재저장 |
| 봇이 응답 안 함 | 토큰 오타 / 봇 미실행 | `python main.py`로 토큰 길이 확인, 프로세스 살아있는지 확인 |

---

## 10. 발견한 함정 (나중에 CLAUDE.md로 옮길 후보)

- 모든 진입점 `.py`에 `sys.stdout.reconfigure(encoding="utf-8")` 필요 (Windows)
- venv 활성화는 새 터미널마다 필요 — **프롬프트 앞에 `(venv)` 붙는지 매번 확인 습관화**. `ModuleNotFoundError: telegram` 류 에러 나면 venv 미활성화 의심 1순위 (Stage 1 검증 중 실제로 발생)
- `.env` 편집은 UTF-8 에디터 사용 (VS Code 권장)
- python-dotenv는 `KEY = "value"` 형태(공백 + 큰따옴표)도 자동으로 파싱 — 토큰 길이만 검증하면 됨
- 같은 봇 토큰으로 인스턴스 2개 동시 실행 시 `Conflict: terminated by other getUpdates request` 에러. 새로 띄우기 전에 기존 프로세스 종료 확인 (`Get-Process python`)
