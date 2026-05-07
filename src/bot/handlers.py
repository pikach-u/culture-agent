"""텔레그램 이벤트 콜백 핸들러."""

from telegram import Update
from telegram.ext import ContextTypes

from src.services import agent


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "안녕하세요! 저는 culture-agent입니다.\n"
        "메시지를 보내주시면 AI가 답변해 드립니다.\n"
        "/reset 으로 대화 기록을 초기화할 수 있어요.\n"
        "(Stage 4: 시간 인지)"
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    agent.reset(update.effective_chat.id)
    await update.message.reply_text("대화 기록을 초기화했습니다.")


async def ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    answer = await agent.ask(update.effective_chat.id, update.message.text)
    await update.message.reply_text(answer)
