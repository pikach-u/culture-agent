"""텔레그램 이벤트 콜백 핸들러."""

import asyncio
import re
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from src.services import agent
from src.services import calendar as calendar_service
from src.services.calendar import KST

ADD_USAGE = (
    "사용법: /add 제목 | YYYY-MM-DD HH:MM | YYYY-MM-DD HH:MM\n"
    "예: /add 어벤져스 관람 | 2026-05-10 19:00 | 2026-05-10 21:00"
)

NUMBERED_ITEM = re.compile(r"\[\d+\]")
SPLIT_BEFORE_ITEM = re.compile(r"(?=\n\s*\[\d+\])")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "안녕하세요! 저는 culture-agent입니다.\n"
        "영화 추천이 필요하시면 자유롭게 물어봐 주세요.\n"
        "/connect 로 구글 캘린더를 연동하면 빈 시간에 맞춰 추천해드려요.\n"
        "/add 제목 | 시작 | 종료 형식으로 일정을 추가할 수 있어요.\n"
        "/reset 으로 대화 기록을 초기화할 수 있어요.\n"
        "(Stage 6+7: 캘린더 연동 + 일정 추가)"
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    agent.reset(update.effective_chat.id)
    await update.message.reply_text("대화 기록을 초기화했습니다.")


async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "브라우저가 열립니다. 구글 로그인 후 캘린더 권한에 동의해주세요."
    )
    try:
        await asyncio.to_thread(calendar_service.run_oauth_flow)
    except FileNotFoundError as e:
        print(f"[handlers] /connect — client_secret 없음: {e}")
        await update.message.reply_text(
            "client_secret.json이 없습니다. 관리자에게 문의해주세요."
        )
        return
    except Exception as e:
        print(f"[handlers] /connect 오류: {type(e).__name__}: {e}")
        await update.message.reply_text(
            "캘린더 연동 중 오류가 발생했습니다. 다시 시도해주세요."
        )
        return

    await update.message.reply_text(
        "캘린더 연동 완료! 이제 추천에 빈 시간이 반영됩니다."
    )


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").removeprefix("/add").strip()
    if not text:
        await update.message.reply_text(ADD_USAGE)
        return

    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 3:
        await update.message.reply_text(ADD_USAGE)
        return

    summary, start_str, end_str = parts
    try:
        start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
        end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except ValueError:
        await update.message.reply_text(ADD_USAGE)
        return

    if end_dt <= start_dt:
        await update.message.reply_text("종료 시간은 시작 시간보다 뒤여야 합니다.")
        return

    try:
        link = await asyncio.to_thread(
            calendar_service.add_event, summary, start_dt, end_dt
        )
    except RuntimeError as e:
        await update.message.reply_text(str(e))
        return
    except Exception as e:
        print(f"[handlers] /add 오류: {type(e).__name__}: {e}")
        await update.message.reply_text(
            "일정 추가 중 오류가 발생했습니다. 다시 시도해주세요."
        )
        return

    msg = f"일정 추가 완료: {summary}"
    if link:
        msg += f"\n{link}"
    await update.message.reply_text(msg)


async def ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    answer = await agent.ask(update.effective_chat.id, update.message.text)

    if len(NUMBERED_ITEM.findall(answer)) >= 2:
        for part in SPLIT_BEFORE_ITEM.split(answer):
            part = part.strip()
            if part:
                await update.message.reply_text(part)
    else:
        await update.message.reply_text(answer)
