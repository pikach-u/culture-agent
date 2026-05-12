"""텔레그램 이벤트 콜백 핸들러."""

import asyncio
import re
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from src.services import agent
from src.services import calendar as calendar_service
from src.services import movie as movie_service
from src.services import nlcal
from src.timeutil import KST

ADD_USAGE = (
    "사용법: /add 제목 | YYYY-MM-DD HH:MM | YYYY-MM-DD HH:MM\n"
    "예: /add 어벤져스 관람 | 2026-05-10 19:00 | 2026-05-10 21:00"
)

NUMBERED_ITEM = re.compile(r"\[\d+\]")
SPLIT_BEFORE_ITEM = re.compile(r"(?=\n\s*\[\d+\])")
TITLE_FROM_ITEM = re.compile(r"\[\d+\]\s*(.+?)\s*[\(（]")
CAPTION_LIMIT = 1024


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "안녕하세요! 저는 culture-agent입니다.\n"
        "영화 추천이 필요하시면 자유롭게 물어봐 주세요.\n"
        "/connect 로 구글 캘린더를 연동하면 빈 시간에 맞춰 추천해드려요.\n"
        "/add 제목 | 시작 | 종료 형식으로 일정을 추가할 수 있어요.\n"
        "/reset 으로 대화 기록을 초기화할 수 있어요.\n"
        "(Stage 8: 박스오피스 데이터 추천)"
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
    chat_id = update.effective_chat.id
    text = update.message.text or ""

    if nlcal.detect_calendar_intent(text):
        if await _try_natural_calendar_add(update, chat_id, text):
            return

    answer = await agent.ask(chat_id, text)

    if len(NUMBERED_ITEM.findall(answer)) >= 2:
        for part in SPLIT_BEFORE_ITEM.split(answer):
            part = part.strip()
            if part:
                await _send_recommendation_part(update, part)
    else:
        await update.message.reply_text(answer)


async def _try_natural_calendar_add(update: Update, chat_id: int, text: str) -> bool:
    """자연어 캘린더 추가 시도. 분기 처리되면 True (응답까지 보냄), 의도 미충족이면 False.

    실패 시 (시간 없음/영화 못 찾음) 사용자에게 안내 후 True 반환 — LLM 호출은 안 함.
    """
    now = datetime.now(KST)
    when = nlcal.parse_when(text, now)
    if when is None:
        await update.message.reply_text(
            "캘린더 추가 의도는 알겠는데 시간을 못 알아들었어요.\n"
            "예: '내일 저녁 7시', '5월 13일 오후 8시'\n"
            f"또는 명시 명령: {ADD_USAGE}"
        )
        return True

    title = _resolve_title_for_calendar(chat_id, text)
    if not title:
        await update.message.reply_text(
            "어떤 영화인지 못 찾았어요. 직전에 영화 추천을 먼저 받거나, "
            f"제목을 직접 적어주세요.\n{ADD_USAGE}"
        )
        return True

    end = when + nlcal.DEFAULT_DURATION
    try:
        link = await asyncio.to_thread(
            calendar_service.add_event, title, when, end
        )
    except RuntimeError as e:
        await update.message.reply_text(str(e))
        return True
    except Exception as e:
        print(f"[handlers] 자연어 add 실패: {type(e).__name__}: {e}")
        await update.message.reply_text(
            "일정 추가 중 오류가 발생했습니다. 다시 시도해주세요."
        )
        return True

    msg = (
        f"일정 추가 완료: {title}\n"
        f"{when.strftime('%Y-%m-%d %H:%M')} ~ {end.strftime('%H:%M')} (자동 2시간)"
    )
    if link:
        msg += f"\n{link}"
    await update.message.reply_text(msg)
    return True


def _resolve_title_for_calendar(chat_id: int, text: str) -> str | None:
    """ordinal → 직전 추천의 [N] / 메시지에 캐시 영화명 포함 / 둘 다 실패 시 None."""
    n = nlcal.extract_ordinal(text)
    if n is not None:
        last = agent.get_last_assistant_content(chat_id)
        if last:
            t = nlcal.extract_title_from_assistant(last, n)
            if t:
                return t
    return movie_service.match_cached_title(text)


async def _send_recommendation_part(update: Update, part: str) -> None:
    """추천 항목 1개 전송. TMDB 포스터 캐시에 영화명 매칭되면 reply_photo, 아니면 reply_text."""
    title_match = TITLE_FROM_ITEM.search(part)
    poster_url = None
    if title_match:
        poster_url = movie_service.get_poster_url(title_match.group(1).strip())

    if poster_url:
        caption = part if len(part) <= CAPTION_LIMIT else part[: CAPTION_LIMIT - 4] + "..."
        try:
            await update.message.reply_photo(photo=poster_url, caption=caption)
            return
        except Exception as e:
            print(f"[handlers] reply_photo 실패: {type(e).__name__}: {e}, reply_text fallback")
    await update.message.reply_text(part)
