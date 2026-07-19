"""
ProviderAdapter — the ONLY module allowed to import an LLM provider SDK
directly (Milestone 2 Architecture, Section 10 — enforceable rule).

Every other module that needs a model call goes through
get_provider().complete(...), never the Anthropic SDK directly. This
is what keeps Gate #3 (Provider Independence) true in code, not just
on paper.
"""

from abc import ABC, abstractmethod
from functools import lru_cache

import anthropic

from app.core.config import settings


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, max_tokens: int = 4000) -> str:
        """Return raw text completion from the model."""
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int = 4000) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


@lru_cache
def get_provider() -> LLMProvider:
    """
    Single point of contact for LLM access across the whole engine.
    Swapping providers later means changing this function only.
    """
    return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
