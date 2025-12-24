"""LLM連携レイヤー

strands-agentsとLiteLLMを使用したLLM連携機能を提供します。
"""

from nyao.integrations.llm.agent_base import NyaoAgent
from nyao.integrations.llm.caller import LLMCaller
from nyao.integrations.llm.prompts import (
    RESPONSE_GENERATION_PROMPT_TEMPLATE,
    SHOULD_RESPOND_PROMPT_TEMPLATE,
    PromptManager,
)

__all__ = [
    "NyaoAgent",
    "PromptManager",
    "LLMCaller",
    "SHOULD_RESPOND_PROMPT_TEMPLATE",
    "RESPONSE_GENERATION_PROMPT_TEMPLATE",
]
