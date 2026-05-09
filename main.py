"""culture-agent 진입점. config 로드 → 핸들러 등록 → 폴링 시작."""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.bot.handlers import (
    add_command,
    ai_message,
    connect_command,
    reset_command,
    start_command,
)
from src.config import TELEGRAM_BOT_TOKEN


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("connect", connect_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_message))

    print("Bot 시작 - Ctrl+C로 종료")
    app.run_polling()


if __name__ == "__main__":
    main()
