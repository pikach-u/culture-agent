"""LLM 호출 래퍼.

공개 API:
- ask(chat_id, user_message) -> str: 사용자 메시지에 답변. 매 호출마다 현재 KST 시간을 시스템 프롬프트에 주입.
- reset(chat_id): 해당 사용자의 대화 히스토리 삭제.

Provider-agnostic 시그니처. 향후 다른 백엔드로 전환 시 이 파일 내부만 교체.
현재 backend: 로컬 Ollama (gemma4:e2b).
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import ollama

from src.config import OLLAMA_HOST, OLLAMA_MODEL
from src.services import calendar as calendar_service

NUM_CTX = 8192
NUM_PREDICT = 1024
MAX_RESPONSE_CHARS = 4000

HISTORY_TURNS = 10

KST = timezone(timedelta(hours=9))
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]

SYSTEM_INSTRUCTION = (
    "당신은 도움이 되는 한국어 AI 어시스턴트입니다. 영화 추천에 특히 강합니다.\n"
    "기본적으로 한국어로 답변하되, 사용자가 다른 언어로 질문하면 그 언어로 답변하세요.\n"
    "마크다운 문법(**굵게**, ## 제목, - 목록 등)을 사용하지 말고 일반 텍스트로만 답변하세요.\n"
    "\n"
    "캘린더 안내:\n"
    "- 캘린더 일정 추가/수정은 직접 할 수 없습니다. 사용자가 요청하면 '/add 제목 | YYYY-MM-DD HH:MM | YYYY-MM-DD HH:MM' 형식으로 안내만 하세요.\n"
    "- 절대 '일정을 추가했어요' 같은 거짓 응답을 하지 마세요.\n"
    "\n"
    "영화 추천 지침 (추천 요청일 때만 적용):\n"
    "- 사용자가 영화 추천을 요청하거나 '볼만한 영화' 같은 추천성 질문을 하면 2~4편을 아래 형식으로 답하세요. "
    "형식 외 다른 안내 문구는 넣지 마세요.\n"
    "\n"
    "[1] 영화 제목 (개봉연도)\n"
    "설명\n"
    "\n"
    "[2] 영화 제목 (개봉연도)\n"
    "설명\n"
    "\n"
    "- 항목 간에 빈 줄을 넣어 구분하세요.\n"
    "- 확실히 아는 영화만 추천하세요. 모르면 모른다고 답하세요.\n"
    "- 영화 추천이 아닌 모든 질문에는 위 형식을 쓰지 말고 자연스러운 한국어로 답하세요."
)

FALLBACK_MESSAGE = "죄송합니다. 잠시 후 다시 시도해주세요."
CONNECTION_ERROR_MESSAGE = "AI 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요."
MODEL_ERROR_MESSAGE = "AI 모델 로드에 실패했습니다. 잠시 후 다시 시도해주세요."
TIMEOUT_MESSAGE = "응답이 너무 오래 걸려서 중단했습니다. 다시 시도해주세요."

_client = ollama.AsyncClient(host=OLLAMA_HOST)
_history: dict[int, list[dict]] = {}


def reset(chat_id: int) -> None:
    _history.pop(chat_id, None)


async def _build_system_prompt() -> str:
    now = datetime.now(KST)
    weekday = WEEKDAYS_KO[now.weekday()]
    time_str = now.strftime("%Y년 %m월 %d일 %H시 %M분")

    parts = [
        SYSTEM_INSTRUCTION,
        f"현재 시간 (KST): {time_str} ({weekday}요일)",
    ]

    free_slots = await asyncio.to_thread(calendar_service.get_free_slots_text)
    if free_slots:
        parts.append(free_slots)
        parts.append(
            "추천 시 위 빈 시간대를 고려해 자연스럽게 반영하세요. (예: 토요일 저녁 비어있음 → 그 시간에 볼 영화 추천)"
        )

    return "\n".join(parts)


async def ask(chat_id: int, user_message: str) -> str:
    history = _history.get(chat_id, [])
    user_dict = {"role": "user", "content": user_message}
    messages: list[dict] = [
        {"role": "system", "content": await _build_system_prompt()},
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
