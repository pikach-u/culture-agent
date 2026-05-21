"""LLM 호출 래퍼.

공개 API:
- ask(chat_id, user_message) -> str: 사용자 메시지에 답변. 매 호출마다 현재 KST 시간을 시스템 프롬프트에 주입.
- reset(chat_id): 해당 사용자의 대화 히스토리 삭제.

Provider-agnostic 시그니처. 향후 다른 백엔드로 전환 시 이 파일 내부만 교체.
현재 backend: 로컬 Ollama (gemma4:e2b).
"""

import asyncio
from datetime import datetime

import httpx
import ollama

from src.config import OLLAMA_HOST, OLLAMA_MODEL
from src.services import calendar as calendar_service
from src.services import embedding
from src.services import mode_router
from src.services import movie as movie_service
from src.services import performances as performances_service
from src.services import user_profile
from src.services.prompts import (
    BOX_OFFICE_HINT,
    FREE_SLOTS_HINT,
    OTT_HINT,
    PERFORMANCE_HINT,
    SYSTEM_INSTRUCTION,
)
from src.timeutil import KST, WEEKDAYS_KO

NUM_CTX = 8192
NUM_PREDICT = 1024
MAX_RESPONSE_CHARS = 4000

HISTORY_TURNS = 10

FALLBACK_MESSAGE = "죄송합니다. 잠시 후 다시 시도해주세요."
CONNECTION_ERROR_MESSAGE = "AI 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요."
MODEL_ERROR_MESSAGE = "AI 모델 로드에 실패했습니다. 잠시 후 다시 시도해주세요."
TIMEOUT_MESSAGE = "응답이 너무 오래 걸려서 중단했습니다. 다시 시도해주세요."

_client = ollama.AsyncClient(host=OLLAMA_HOST)
_history: dict[int, list[dict]] = {}
_last_mode: dict[int, str] = {}  # Stage 13.1 — 멀티턴 모드 sticky


def reset(chat_id: int) -> None:
    _history.pop(chat_id, None)
    _last_mode.pop(chat_id, None)


def get_last_assistant_content(chat_id: int) -> str | None:
    """해당 사용자의 가장 최근 assistant 응답 텍스트. 없으면 None.

    handlers의 자연어 캘린더 처리 — '2번째 영화' 같은 ordinal을 직전 추천 응답의
    [N] 항목과 매칭하기 위한 노출.
    """
    history = _history.get(chat_id, [])
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            return msg.get("content", "")
    return None


async def _build_system_prompt(
    chat_id: int,
    user_message: str = "",
    ott_text: str | None = None,
) -> str:
    now = datetime.now(KST)
    weekday = WEEKDAYS_KO[now.weekday()]
    time_str = now.strftime("%Y년 %m월 %d일 %H시 %M분")

    parts = [
        SYSTEM_INSTRUCTION,
        f"현재 시간 (KST): {time_str} ({weekday}요일)",
    ]

    user_region = user_profile.get_region(chat_id)
    if user_region:
        parts.append(f"사용자 지역: {user_region}")

    free_slots = await asyncio.to_thread(calendar_service.get_free_slots_text)
    if free_slots:
        parts.append(free_slots)
        parts.append(FREE_SLOTS_HINT)

    # Stage 13 모드 분기 — OTT 모드면 RAG list 주입, 아니면 기존 KOFIC 경로.
    if ott_text:
        parts.append(ott_text)
        parts.append(OTT_HINT)
    else:
        box_office = await asyncio.to_thread(movie_service.get_box_office_text, user_message)
        if box_office:
            parts.append(box_office)
            parts.append(BOX_OFFICE_HINT)

    # Phase 2까지 dormant — 도메인 좁히기 결정(2026-05-14)에 따라 공연/전시 컨텍스트 주입 차단.
    # Phase 2 진입 시 아래 6줄 주석 해제. import + performances_service.get_poster_url(handlers)는 무비용 유지.
    # performance = await asyncio.to_thread(
    #     performances_service.get_performance_text, user_message, user_region
    # )
    # if performance:
    #     parts.append(performance)
    #     parts.append(PERFORMANCE_HINT)

    return "\n".join(parts)


async def ask(chat_id: int, user_message: str) -> str:
    # Stage 13.1 모드 결정: 명시 키워드 → sticky → 기본 KOFIC.
    explicit = mode_router.detect_mode(user_message)
    if explicit is not None:
        mode = explicit
    else:
        mode = _last_mode.get(chat_id, "kofic")

    # Stage 13 OTT 분기 — 0건이면 LLM 호출 없이 short-circuit.
    ott_text: str | None = None
    if mode == "ott":
        ott_filter = mode_router.extract_ott_filter(user_message)
        recent_first = mode_router.detect_temporal(user_message)
        ott_text = await asyncio.to_thread(
            embedding.get_ott_text,
            user_message,
            ott_filter or None,
            10,
            recent_first,
        )
        if ott_text is None and ott_filter:
            _last_mode[chat_id] = mode
            label = ", ".join(ott_filter)
            return f"'{label}'에서 사용자 요청에 맞는 영화를 찾지 못했어요. 다른 키워드로 시도해보세요."

    _last_mode[chat_id] = mode

    history = _history.get(chat_id, [])
    user_dict = {"role": "user", "content": user_message}
    messages: list[dict] = [
        {"role": "system", "content": await _build_system_prompt(chat_id, user_message, ott_text)},
        *history,
        user_dict,
    ]

    try:
        response = await _client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            think=False,
            options={
                "num_ctx": NUM_CTX,
                "num_predict": NUM_PREDICT,
            },
        )
    except ConnectionError as e:
        print(f"[agent] Ollama connection error: {e}")
        return CONNECTION_ERROR_MESSAGE
    except httpx.TimeoutException as e:
        print(f"[agent] Ollama timeout: {type(e).__name__}: {e}")
        return TIMEOUT_MESSAGE
    except ollama.ResponseError as e:
        print(f"[agent] Ollama ResponseError: status={getattr(e, 'status_code', '?')} message={e}")
        return MODEL_ERROR_MESSAGE
    except Exception as e:
        print(f"[agent] Unexpected error: {type(e).__name__}: {e}")
        return FALLBACK_MESSAGE

    text = (response.message.content or "").strip()
    if not text:
        return FALLBACK_MESSAGE

    new_messages = [user_dict, {"role": "assistant", "content": text}]
    _save_history(chat_id, history, new_messages)

    if len(text) > MAX_RESPONSE_CHARS:
        text = text[:MAX_RESPONSE_CHARS] + "..."
    return text


def _save_history(chat_id: int, old_history: list[dict], new_messages: list[dict]) -> None:
    combined = old_history + new_messages
    user_indices = [i for i, m in enumerate(combined) if m.get("role") == "user"]
    if len(user_indices) > HISTORY_TURNS:
        cut_at = user_indices[-HISTORY_TURNS]
        combined = combined[cut_at:]
    _history[chat_id] = combined
