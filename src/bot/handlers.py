"""텔레그램 이벤트 콜백 핸들러."""

from telegram import Update
from telegram.ext import ContextTypes


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "안녕하세요! 저는 culture-agent입니다.\n"
        "메시지를 보내주시면 그대로 되돌려 드립니다.\n"
        "(Stage 1: echo bot)"
    )


async def echo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)
