# PROGRESS

> 이 파일은 작업 _일지_. 갱신 규칙은 CLAUDE.md 4부 참조.
> 핵심 두 가지: ① 직전 Stage 1개만 자세히, 이전은 결정 기록(7번)으로 압축
> ② 일반 원칙/함정은 여기 말고 CLAUDE.md

문화생활 추천 텔레그램 에이전트 — 진행 일지.

> ⚠️ 시크릿(봇 토큰, API 키 등)은 절대 이 파일에 적지 말 것. 위치만 메모.

---

## 0. 프로젝트 개요

**목표**: 영화 추천 텔레그램 봇 (Phase 1). 현재 상영작(KOFIC) + OTT(TMDB + RAG)
두 모드 + 캘린더 빈 시간 분석 + 자연어 일정 추가. 공연/전시·신규 이벤트 알림은 Phase 2.

**환경**:

- 플랫폼: Windows 10, PowerShell
- 언어: Python 3.12.3

**Phase 전략** (2026-05-14 결정):

- **Phase 1 (MVP)**: 영화 단일 도메인. 두 모드 — 현재 상영(KOFIC) / OTT(TMDB 300편 + RAG).
  단일 에이전트 + 코드 기반 모드 분기.
- **Phase 2 (안정화 후)**: 멀티 에이전트 리팩터(Router + 전문 에이전트), 공연/전시(Stage 10) 부활, 책 등 추가.

> 작업 원칙은 CLAUDE.md 1부/2부 참조.

---

## 1. 현재 위치

- **Stage 11/12 완료** — 카탈로그 300편 + bge-m3 임베딩 + probe sanity 통과 (사용자 확인).
- **Stage 13 진입** — OTT 모드 분기 + RAG 통합. mode_router/embedding/agent/catalog/prompts/handlers 전부 갱신. 실측 검증 대기.

---

## 2. 마지막 작업 (2026-05-19)

### Stage 13 — OTT 모드 분기 + RAG 통합

**의도**: Stage 12 RAG 인덱스를 봇 응답에 연결. 사용자 메시지의 OTT 키워드로 코드 라우팅 → KOFIC(기본) / OTT(RAG).

**구현**:

- `src/services/mode_router.py` 신규 — `detect_mode()` / `extract_ott_filter()`. OTT 트리거 정규식 + 한국 6대 OTT 플랫폼 매핑.
- `src/services/embedding.py` 확장 — `get_ott_text(query, ott_filter)` LLM list 텍스트 포맷. 필터 시 top_k*2 검색 후 사후 필터.
- `src/services/catalog.py` 확장 — `get_poster_url(title)` 추가 (handlers fallback 체인용).
- `src/services/prompts.py` — `OTT_HINT` 추가 (BOX_OFFICE_HINT와 별도, 의도 기반 선별 + OTT 시청 정보 표시 지침).
- `src/services/agent.py` — `ask()`에서 mode 분기. OTT + 필터 0건 시 LLM 호출 없이 short-circuit "못 찾았어요" 메시지.
- `src/bot/handlers.py` — 포스터 fallback 체인에 `catalog_service.get_poster_url` 추가. /start 안내문구에 OTT 사용 예시 추가.

**설계 선택**:

- 분기 기본값 = KOFIC (사용자 결정 옵션 A). OTT 키워드 명시 없으면 박스오피스로.
- 0건 fallback = "못 찾았어요" 직접 응답 (전체 풀 fallback 안 함 — 잘못된 결과보다 솔직).
- 단순 후처리 필터 — RAG 검색에 OTT 정보는 안 넣고, top_k*2 뽑은 뒤 catalog의 ott_kr로 필터.

**의도된 한계**: 취향 프로파일(Stage 9 재편), 하이브리드 검색(BM25+벡터), 멀티 의도 분해는 후순위.

### Stage 12 — RAG 임베딩 인덱스 (압축)

- bge-m3 1024차원 L2-normalized, numpy + pickle, mtime 비교 신선도.
- 임베딩 입력: `title_ko | 장르 | overview`.
- 5쿼리 probe sanity 통과 (복합 쿼리는 약함 — 카탈로그 300편 풀 한계).

---

### 2026-05-14 결정 — 도메인 좁히기 + RAG 도입

**배경**: Stage 10 v2 보정 후에도 모호 질의("볼만한 거")에 작은 모델(gemma4:e2b)이 다중 도메인 균형 추천 실패. 모델 한계 비중 75% 추정.

**결정**:

1. **도메인을 영화 단일로 좁힘** — 다중 도메인 균형 분기 자체 제거 (문제 회피가 아니라 scope 조정).
2. **RAG 도입 + 카탈로그 확장** — 학습 가치 + OTT 추천 use case 신설.
   - 카탈로그: TMDB 300편 (한국 인기 + 최근 화제작)
   - 임베딩: ollama bge-m3 (한국어 RAG 표준, Stage 2 Ollama 결정 일관성)
   - 벡터 저장: numpy + pickle (300편 규모 충분, 학습 친화. 벡터 DB는 Stage 12 진입 시 결정)
   - OTT 필터: 없음 — 전체 OTT 표시 (여러 OTT 구독 케이스)
3. **모드 분기**: 코드 기반 키워드 정규식 라우팅 — 극장 키워드 → KOFIC, OTT 키워드 → RAG. LLM Router는 작은 모델 한계 재현 risk → 미채택.
4. **테스트 A (블록 순서 swap) → 보류 종료** — 도메인 좁히면 분기 자체가 사라짐.

**Stage 재편**: Stage 11(보강+카탈로그) → 12(RAG 인덱스) → 13(OTT 통합+모드 분기) → 9(취향 프로파일, RAG 위에 활동 임베딩 평균) → 14+(Phase 2 멀티 에이전트·공연 부활). 기존 Stage 11(신규 이벤트 알림) → Stage 15+로 후순위.

### 박스오피스 보강 — KOFIC scrnCnt 실측

**의도**: Stage 11 진입 전 가벼운 보강. KOFIC `searchDailyBoxOfficeList`가 _어제_ 매출 1~10위 → 오늘 상영 보장 X. `scrnCnt` 필드를 LLM 입장에서 보이게.

**실측 결과** (`tmp/probe_kofic_fields.py`):

```
1위 마이클(2026 신작)   scrnCnt=1734  ← 신작 폭발
2~8위 안정권           scrnCnt 253~817
9위 이프 온리(2004)    scrnCnt=223   ← 재상영
10위 탑건 매버릭(2022)  scrnCnt=111   ← 재상영
```

자연 갭 = 250관. 9~10위는 _끝물이 아니라 재개봉/특별 상영_ — 우리 안내 의도와 정확히 일치.

**구현**: `scrnCnt < 250` → `[상영관 N개 — 막내림 가능, 영화관 확인 권장]` 라벨 부착. list 제외 X (LLM이 판단).

- `movie.py:_fetch_and_format()`에 scrnCnt 추가 + 라벨
- `prompts.BOX_OFFICE_HINT`에 "막내림 가능 라벨 영화는 영화관 확인 권장" 한 줄 추가

---

## 3. 다음 세션 첫 작업 (Stage 13 검증 → Stage 9 재편)

### 3-1. 환경 셋팅

```powershell
cd C:\Users\ziwon\OneDrive\Desktop\claude\culture-agent
.\venv\Scripts\Activate.ps1
python main.py
```

### 3-2. Stage 9(재편) 결정 필요 항목 (Stage 13 검증 후)

1. **취향 프로파일 데이터**: 사용자 활동(추천 요청 텍스트 / 캘린더 등록 영화 제목)을 임베딩 평균으로 누적할지, 별도 가중치 정책 둘지.
2. **저장 위치**: chat_id별 numpy 벡터 1024 + 카운트 → 메모리 vs 파일. 멀티 사용자 누출 방지 고민.
3. **추천 반영 방식**: query 임베딩 + 취향 평균 가중합(α) → search. α 디폴트.
4. **새 사용자 / 데이터 부족 케이스**: 활동 < N건이면 취향 미반영.

### 3-3. 후속 검토 후보

**Phase 1 진행 중**:

- TMDB 동명영화 disambiguate (Stage 8 미해결, 카탈로그 구축 시 함께)
- 자연어 캘린더 정식화 (요일 표현 / `dateparser` / 모델 응답에서 제목 추출)
- TMDB 감독·출연진 결합 (`/movie/{id}/credits`)
- 벡터 DB 마이그 (numpy → Chroma 등) — _학습 목적_(인터페이스/검색 알고리즘 비교), 규모 트리거 아님. embedding.search() 인터페이스 좁게 유지해서 교체 단순화.
- OTT 구독 필터 (`/setotts`, 피드백 후 재검토)
- 영화 선택 → 지도 연동 → 주변 상영관 예매 링크. 가능하면 예매 가능 시간도. 난이도 낮은 단계부터 (예: 단순 외부 링크 → 영화관 좌표 매칭 → 실시간 시간표).

**Phase 2로 미룸**: 공연/전시 부활(Stage 10 코드 보존 + 후속 검토 후보 일체), 멀티 에이전트 리팩터, 책 등 도메인 추가.

**상시 후순위**: chat_id별 토큰 분리(멀티 사용자 누출 방지), chat_id별 `asyncio.Lock`, 자동 재시도, 멀티모달, 다른 시간대 지원, Ollama OOM 영구 대응, 빈 시간 캐싱.

---

## 4. 미해결 이슈

- 없음 (Stage 11 진입 가능).
- Stage 3 알려진 한계 2건 + Stage 7 멀티 사용자 토큰 누출 + Stage 8 TMDB 동명영화 disambiguate → 3-3번 참조 (의도적 후순위).

---

## 5. 단계별 체크리스트

- [x] **Stage A**: Claude Code 텔레그램 채널 연동
- [x] **Stage 0**: 환경 셋업
- [x] **Stage 1**: Echo bot
- [x] **Stage 2**: LLM API — Gemini → Ollama Gemma 4 E2B
- [x] **Stage 3**: 대화 기억 (멀티턴)
- [x] **Stage 4**: 외부 정보 활용 (context injection)
- [x] **Stage 5**: 영화 추천 (도메인/형식 지시)
- [x] **Stage 6**: 캘린더 읽기 (freebusy)
- [x] **Stage 7**: 캘린더 쓰기 (`/add` + 자연어 의도)
- [x] **Stage 8**: KOFIC + TMDB 병렬 + 포스터 첨부
- [x] **Stage 10**: 공연/전시 크롤링 — _Phase 2 부활 예정 (dormant)_
- [x] **Stage 11**: 박스오피스 scrnCnt 보강 + TMDB 카탈로그 300편 + OTT 가용성
- [x] **Stage 12**: RAG 임베딩 인덱스 (bge-m3 + numpy + pickle)
- [ ] **Stage 13 ← 검증**: OTT 추천 통합 + 모드 분기 + 자연어 RAG 쿼리
- [ ] **Stage 9** (재편): 취향 프로파일 — RAG 위에 활동 임베딩 평균. Stage 13 이후.
- [ ] **Stage 14+** (Phase 2): 멀티 에이전트, 공연 부활, 책 추가
- [ ] **Stage 15+**: 신규 이벤트 자동 알림

---

## 6. Stage별 완료 기준 (DoD) — 최근 Stage만 보존

> 이전 Stage DoD는 통과 후 5번 체크리스트로 압축됨.

### Stage 13 DoD — OTT 모드 분기 + RAG 통합

- [ ] "볼만한 영화" → KOFIC 박스오피스 list로 응답 (기존 동작 유지, 회귀 X)
- [ ] "넷플릭스에 SF 있어?" → OTT 분기, 추천 list 안의 영화가 모두 넷플릭스에 시청 가능
- [ ] "OTT에 뭐 볼만해" → OTT 분기, 필터 없음, RAG top_k 결과 그대로
- [ ] "디플에서 호러" → 매칭 0건 시 "'Disney Plus'에서 사용자 요청에 맞는 영화를 찾지 못했어요" 안내
- [ ] OTT 모드 응답에 포스터 정상 첨부 (catalog fallback)
- [ ] OTT 추천 항목에 시청 가능 OTT 한 줄 표시 ("시청: 넷플릭스, 디즈니+")
- [ ] /start 안내문구에 OTT 사용 예시 노출
- [ ] 회귀: Stage 7 캘린더 / Stage 8 박스오피스 / Stage 11 카탈로그 / Stage 12 임베딩 정상

---

## 7. 결정 기록

> 일반 원칙은 CLAUDE.md 3부. 여기엔 *프로젝트 특정 결정*만.

### Stage 0~7 (압축)

- **Stage 0~1**: Python 3.12.3, pip + venv, `src/` 분리. python-telegram-bot 22.x async, `TELEGRAM_BOT_TOKEN` import 시점 fail-fast.
- **Stage 2**: Gemini 2.5 Flash → Ollama Gemma 4 E2B(2026-05-07). `num_ctx=8192`, `num_predict=1024`, `think=False`. 시스템 프롬프트 3줄(generic AI / 한국어 / 마크다운 금지).
- **Stage 3**: in-memory `dict[chat_id, list[dict]]` + 슬라이딩 윈도우 10턴. `/reset`. 저장은 4000자 컷 _전_ 원본.
- **Stage 4**: function calling 시도(gemma4:e2b chat template 미완성, qwen3.5:4b stochastic emit) → **context injection 피벗**. `_build_system_prompt()`이 매 호출마다 KST 시간 동적 삽입.
- **Stage 5**: 추천 워크플로우만. 시스템 프롬프트 도메인/형식 지시 + `[N] 제목` 정규식 분리. `/recommend` 명시 명령 안 만듦.
- **Stage 6~7**: OAuth `InstalledAppFlow.run_local_server`, SCOPES `calendar.events` + `calendar.readonly` 둘 다 필수(events만으로는 freebusy → 403). `freebusy.query()`, `asyncio.to_thread`로 sync 감쌈. `/add 제목 | start | end` 명시 명령. 환각 방지 가드레일.

### Stage 8 — KOFIC + TMDB (2026-05-10~11)

- 결합: KOFIC + TMDB 병렬(`ThreadPoolExecutor(max_workers=10)`, ~10s → ~2.5s).
- 추천 키워드 정규식: `추천|볼\s*만한|볼만|재밌는|박스오피스|인기|상영중|뭐\s*볼|영화\s*뭐`.
- **추천 순위 = KOFIC 그대로**: 모델이 TMDB 평점 높은 영화 우선 추천 → 평점을 줄 끝 `[TMDB 평점 X.X — 참고용]`로 약화 + hint에 "list 순서 그대로, TMDB 평점은 추천 순위에 사용 금지" 명시.
- **줄거리 220자 + "…"**: 초기 120자 → 작은 모델이 잘린 list 그대로 옮김 → 220자 + "잘림 인지하면 자기 한국어로 마무리" hint.
- **시연 보호**: KOFIC timeout 5→10s + stale 캐시 fallback.
- 모듈 레벨 globals 캐시 (`_cache_text`, `_cache_posters`, `_cache_at`).
- 모듈화 리팩터: KST → `src/timeutil.py`, 프롬프트 → `src/services/prompts.py`.
- **박스오피스 scrnCnt 보강** (2026-05-18): `LOW_SCRN_THRESHOLD=250` 실측 자연 갭 기반. 미만이면 `[상영관 N개 — 막내림 가능, 영화관 확인 권장]` 라벨 부착 + BOX_OFFICE_HINT에 영화관 확인 권장 안내. KOFIC = 어제 매출이라 오늘 상영 보장 X → LLM 입장에서 신호화.

### Stage 10 — 크롤링 (2026-05-12, dormant)

- 어댑터 패턴(인터파크 NEXT_DATA + 예스24 BS4 + registry 병렬/24h 캐시) + venue→region 매핑 + `/setlocation` + v2 보정(dedup·status_label·`_PER_GENRE_LIMIT=3`). 모호 질의 진단으로 모델 한계 75% 추정 → **도메인 좁히기로 해결**(위 2번). Phase 2까지 dormant.

### Stage 11 — TMDB 300편 카탈로그 (2026-05-19)

- 소스: popular 5p + top_rated 5p + discover KR 5년 5p → dedup, 부족분 top_rated 추가 페이지(MAX 15p) 보충. TARGET_SIZE=300.
- OTT: `/movie/{id}/watch/providers` 4 worker 병렬, KR flatrate만 저장.
- 캐시: `data/movies_catalog.json` + `fetched_at` 메타, 1주 TTL.
- 장르: `/genre/movie/list` 한국어 매핑 1회 캐시.
- Stage 8 `movie.py` (KOFIC 10편)와 독립 — 박스오피스용은 별도 모듈 유지.

### Stage 12 — RAG 임베딩 인덱스 (2026-05-19)

- 임베딩 모델: ollama bge-m3 (1024차원, L2-normalized → cosine = dot).
- 입력 텍스트: `title_ko | 장르 | overview` 결합.
- 저장: `data/movies_embeddings.npy` + `.pkl` (id 매핑). 1024×300 ≈ 1.2MB.
- 신선도: 임베딩 npy mtime vs 카탈로그 json mtime 비교.
- 인터페이스(`ensure_built` / `search`) 좁게 유지 — 추후 벡터 DB 학습 마이그 시 교체 단순화.

### Stage 13 — OTT 모드 분기 + RAG 통합 (2026-05-19)

- 모드 분기: 코드 기반 키워드 정규식(`mode_router.py`). LLM Router는 작은 모델 한계 재현 risk → 미채택.
- 기본값: OTT 키워드 없으면 KOFIC (사용자 결정, 옵션 A).
- OTT 필터: 사후 처리 — `search(top_k*2)` → catalog의 ott_kr로 필터 → top_k 컷.
- 0건 처리: 사용자가 OTT 명시했는데 매칭 0건이면 LLM 호출 없이 직접 "못 찾았어요" (전체 풀 fallback 안 함).
- `OTT_HINT` 별도 hint — `BOX_OFFICE_HINT`와 분리 유지 (학습 단계 명확성 우선, 공통화는 패턴 굳어진 후).
- 포스터: `catalog.get_poster_url` handlers fallback 체인에 추가 (movie → catalog → performances).

---

## 8. 현재 코드 상태

**Phase 1 활성**:

- `main.py`, `src/config.py`, `src/timeutil.py`
- `src/bot/handlers.py` — 명령어 + `ai_message` + 추천 분리/포스터/자연어 캘린더
- `src/services/agent.py` — Ollama AsyncClient + `_build_system_prompt(chat_id, user_message)`
- `src/services/calendar.py` (Stage 6+7), `src/services/movie.py` (Stage 8), `src/services/nlcal.py` (Stage 7+)
- `src/services/catalog.py` (Stage 11), `src/services/embedding.py` (Stage 12), `src/services/mode_router.py` (Stage 13)
- `src/services/user_profile.py` — chat_id별 in-memory 메타
- `src/services/prompts.py` — `SYSTEM_INSTRUCTION` + `FREE_SLOTS_HINT` + `BOX_OFFICE_HINT` + `OTT_HINT` + `PERFORMANCE_HINT`

**Phase 2까지 dormant** (코드 보존, 호출 비활성화 예정):

- `src/services/performances.py`, `src/services/crawler/` 패키지 일체

**시크릿 위치** (값은 절대 여기 적지 않음):

- `.env`: `TELEGRAM_BOT_TOKEN`, `KOFIC_API_KEY`, `TMDB_API_KEY`
- `credentials/`: `client_secret.json`, `token.json` (gitignored)

---

## 9. 트러블슈팅

| 증상                                                | 원인                                  | 해결                                                                    |
| --------------------------------------------------- | ------------------------------------- | ----------------------------------------------------------------------- |
| `Activate.ps1 ... 실행할 수 없습니다`               | PowerShell 실행 정책                  | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`  |
| `ModuleNotFoundError: telegram`                     | venv 미활성화                         | `.\venv\Scripts\Activate.ps1` 후 재실행                                 |
| 한글/이모지 출력 깨짐 (`UnicodeEncodeError: cp949`) | Windows 콘솔 인코딩                   | 진입점 `.py` 상단 `sys.stdout.reconfigure(encoding="utf-8")`            |
| `python -c "..."` 인라인 한글 깨짐                  | 인라인은 `.py`의 reconfigure 안 거침  | `$env:PYTHONIOENCODING='utf-8'; python -c "..."`                        |
| `.env` 한글 주석 깨짐                               | 메모장 ANSI 저장                      | UTF-8 에디터(VS Code)로 재저장                                          |
| 봇이 응답 안 함                                     | 토큰 오타 / 봇 미실행                 | 토큰 확인, `Get-Process python` 확인                                    |
| `Conflict: terminated by other getUpdates request`  | 같은 봇 토큰 인스턴스 2개 동시 실행   | 기존 프로세스 종료 후 재실행                                            |
| 봇이 "AI 서비스에 연결할 수 없습니다"               | Ollama 데몬 미실행                    | 시작 메뉴/`ollama serve`, 트레이 확인                                   |
| 봇이 "AI 모델 로드에 실패했습니다"                  | 모델 없음 / 로드 실패                 | `ollama list`, `ollama pull gemma4:e2b`                                 |
| Ollama "model requires more memory"                 | OS RAM 부족                           | 다른 프로그램 종료, 또는 NUM_CTX 8192→4096                              |
| `/connect` 시 "확인되지 않은 앱" 경고               | OAuth 동의 화면 미검증 (테스트 모드)  | "고급" → "안전하지 않은 페이지로 이동". 테스트 사용자에 본인 Gmail 등록 |
| `/add` 시 `403 insufficientPermissions`             | SCOPES 변경 후 기존 token.json 재사용 | `Remove-Item credentials\token.json` 후 `/connect` 재실행               |
| `[movie] KOFIC 요청 실패: ReadTimeout`              | KOFIC 서버 일시 지연                  | timeout 10s + stale 캐시 fallback 적용됨                                |
