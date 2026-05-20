# culture-agent

텔레그램 기반 문화생활 추천 에이전트.

## Project Goal

사용자의 캘린더 빈 시간을 분석해 취향에 맞는 전시·영화·공연을 추천하고, 일정·주변 음식점·예매 링크까지 묶어 제안하는 텔레그램 봇. 신규 이벤트는 자동 알림.

**UX 의도**: 추천 결과는 **항목별로 메시지를 분리**해서 보낸다. 예를 들어 공연 3개를 추천하면 한 메시지에 모아쓰지 않고 3개의 메시지로 보낸다 — 모바일 텔레그램에서 카드처럼 훑어보기 좋게 하기 위함.

## Setup

```powershell
# 1. 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경변수 설정
Copy-Item .env.example .env
# .env 파일 열어서 TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY 입력

# 4. 봇 실행
python main.py
```

## Requirements

- Python 3.10+ (권장: 3.12)
- Telegram Bot Token ([BotFather](https://t.me/BotFather)에서 발급)
