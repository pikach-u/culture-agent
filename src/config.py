"""환경변수 로딩. 다른 모듈은 여기서만 설정값을 가져온다."""

import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN이 비어있습니다. .env 파일을 확인하세요."
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY가 비어있습니다. .env 파일을 확인하세요."
    )
