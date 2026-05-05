"""LLM 호출 래퍼. 공개 함수는 ask(user_message) -> str 한 개.

Provider-agnostic 시그니처. 향후 Anthropic 등으로 전환 시 이 파일 내부만 교체.
현재 backend: Google Gemini (gemini-2.5-flash).
"""

from google import genai
from google.genai import errors, types

from src.config import GEMINI_API_KEY

MODEL_ID = "gemini-2.5-flash"
MAX_OUTPUT_TOKENS = 1024
MAX_RESPONSE_CHARS = 4000

SYSTEM_INSTRUCTION = (
    "당신은 도움이 되는 AI 어시스턴트입니다.\n"
    "기본적으로 한국어로 답변하되, 사용자가 다른 언어로 질문하면 그 언어로 답변하세요.\n"
    "마크다운 문법(**굵게**, ## 제목, - 목록 등)을 사용하지 말고 일반 텍스트로만 답변하세요."
)

FALLBACK_MESSAGE = "죄송합니다. 잠시 후 다시 시도해주세요."

_client = genai.Client(api_key=GEMINI_API_KEY)
_config = types.GenerateContentConfig(
    system_instruction=SYSTEM_INSTRUCTION,
    max_output_tokens=MAX_OUTPUT_TOKENS,
)


async def ask(user_message: str) -> str:
    try:
        response = await _client.aio.models.generate_content(
            model=MODEL_ID,
            contents=user_message,
            config=_config,
        )
    except errors.APIError as e:
        print(f"[agent] Gemini APIError: code={getattr(e, 'code', '?')} message={e}")
        return FALLBACK_MESSAGE
    except Exception as e:
        print(f"[agent] Unexpected error: {type(e).__name__}: {e}")
        return FALLBACK_MESSAGE

    text = (response.text or "").strip()
    if not text:
        return FALLBACK_MESSAGE
    if len(text) > MAX_RESPONSE_CHARS:
        text = text[:MAX_RESPONSE_CHARS] + "..."
    return text
