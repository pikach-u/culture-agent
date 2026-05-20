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
    setlocation_command,
    start_command,
)
from src.config import TELEGRAM_BOT_TOKEN
from src.services import catalog, embedding


def main() -> None:
    # 봇 폴링 전 카탈로그 신선도 보장 — 1주 stale 또는 부재 시 fetch (첫 기동 ~분 단위).
    catalog.ensure_fresh()
    # 카탈로그 바뀌었으면 RAG 임베딩 재빌드. 첫 빌드 ~분 단위(bge-m3 300회).
    embedding.ensure_built()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("connect", connect_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("setlocation", setlocation_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_message))

    print("Bot 시작 - Ctrl+C로 종료")
    app.run_polling()


if __name__ == "__main__":
    main()
