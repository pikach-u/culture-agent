"""환경변수 로딩. 다른 모듈은 여기서만 설정값을 가져온다."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "").strip() or "http://localhost:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip() or "gemma4:e2b"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN이 비어있습니다. .env 파일을 확인하세요."
    )
