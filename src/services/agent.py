"""LLM 호출 래퍼.

공개 API:
- ask(chat_id, user_message) -> str: 사용자 메시지에 답변. 매 호출마다 현재 KST 시간을 시스템 프롬프트에 주입.
- reset(chat_id): 해당 사용자의 대화 히스토리 삭제.

Provider-agnostic 시그니처. 향후 다른 백엔드로 전환 시 이 파일 내부만 교체.
현재 backend: 로컬 Ollama (gemma4:e2b).
"""

from datetime import datetime, timedelta, timezone

import httpx
import ollama

from src.config import OLLAMA_HOST, OLLAMA_MODEL

NUM_CTX = 8192
NUM_PREDICT = 1024
MAX_RESPONSE_CHARS = 4000

HISTORY_TURNS = 10

KST = timezone(timedelta(hours=9))
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]

SYSTEM_INSTRUCTION = (
    "당신은 도움이 되는 AI 어시스턴트입니다.\n"
    "기본적으로 한국어로 답변하되, 사용자가 다른 언어로 질문하면 그 언어로 답변하세요.\n"
    "마크다운 문법(**굵게**, ## 제목, - 목록 등)을 사용하지 말고 일반 텍스트로만 답변하세요."
)

FALLBACK_MESSAGE = "죄송합니다. 잠시 후 다시 시도해주세요."
CONNECTION_ERROR_MESSAGE = "AI 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요."
MODEL_ERROR_MESSAGE = "AI 모델 로드에 실패했습니다. 잠시 후 다시 시도해주세요."
TIMEOUT_MESSAGE = "응답이 너무 오래 걸려서 중단했습니다. 다시 시도해주세요."

_client = ollama.AsyncClient(host=OLLAMA_HOST)
_history: dict[int, list[dict]] = {}


def reset(chat_id: int) -> None:
    _history.pop(chat_id, None)


def _build_system_prompt() -> str:
    now = datetime.now(KST)
    weekday = WEEKDAYS_KO[now.weekday()]
    time_str = now.strftime("%Y년 %m월 %d일 %H시 %M분")
    return f"{SYSTEM_INSTRUCTION}\n현재 시간 (KST): {time_str} ({weekday}요일)"


async def ask(chat_id: int, user_message: str) -> str:
    history = _history.get(chat_id, [])
    user_dict = {"role": "user", "content": user_message}
    messages: list[dict] = [
        {"role": "system", "content": _build_system_prompt()},
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
