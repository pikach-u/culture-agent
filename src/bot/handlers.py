"""텔레그램 이벤트 콜백 핸들러."""

import re

from telegram import Update
from telegram.ext import ContextTypes

from src.services import agent

NUMBERED_ITEM = re.compile(r"\[\d+\]")
SPLIT_BEFORE_ITEM = re.compile(r"(?=\n\s*\[\d+\])")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "안녕하세요! 저는 culture-agent입니다.\n"
        "영화 추천이 필요하시면 자유롭게 물어봐 주세요.\n"
        "/reset 으로 대화 기록을 초기화할 수 있어요.\n"
        "(Stage 5: 영화 추천)"
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    agent.reset(update.effective_chat.id)
    await update.message.reply_text("대화 기록을 초기화했습니다.")


async def ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    answer = await agent.ask(update.effective_chat.id, update.message.text)

    if len(NUMBERED_ITEM.findall(answer)) >= 2:
        for part in SPLIT_BEFORE_ITEM.split(answer):
            part = part.strip()
            if part:
                await update.message.reply_text(part)
    else:
        await update.message.reply_text(answer)
