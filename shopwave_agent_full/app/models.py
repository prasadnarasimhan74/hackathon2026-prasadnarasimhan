import os
from typing import Optional

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()


class LLMUnavailable(Exception):
    pass


def get_llm() -> Optional[ChatAnthropic]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    model_id = os.getenv("ANTHROPIC_MODEL_ID", "claude-sonnet-4-5")
    return ChatAnthropic(
        api_key=api_key,
        model=model_id,
        temperature=0,
        max_tokens=4096,
    )
