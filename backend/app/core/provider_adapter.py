"""
ProviderAdapter — the ONLY module allowed to import an LLM provider SDK
directly (Milestone 2 Architecture, Section 10 — enforceable rule).

Every other module that needs a model call goes through
get_provider().complete(...), never a provider SDK directly. This is
what keeps Gate #3 (Provider Independence) true in code, not just on
paper — and this file is exactly where that pays off: a validation-
only third-party gateway can be swapped in here without touching any
of the 10 engine modules that call get_provider().
"""

from abc import ABC, abstractmethod
from functools import lru_cache

import anthropic
from openai import OpenAI

from app.core.config import settings


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, max_tokens: int = 4000) -> str:
        """Return raw text completion from the model."""
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    """Direct Anthropic SDK — the real path, for a real Anthropic account."""

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


class OpenAICompatibleGatewayProvider(LLMProvider):
    """
    For OpenAI-compatible gateways (e.g. a third-party billing proxy
    like aicredits.in) — VALIDATION USE ONLY, per the explicit decision
    to use this only as a temporary bridge to run the pending live-API
    validation, not as the product's real, ongoing provider. Swap back
    to AnthropicProvider for anything beyond that.
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int = 4000) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content
        return content or ""


@lru_cache
def get_provider() -> LLMProvider:
    """
    Single point of contact for LLM access across the whole engine.
    Swapping providers means changing ONLY this function — no engine
    module ever needs to change.

    Provider selection is controlled by settings.LLM_PROVIDER
    ("anthropic" | "gateway") — defaults to "anthropic", the real path.
    Set LLM_PROVIDER=gateway in your OWN .env (never shared in chat) to
    use the validation-only gateway path instead.
    """
    if settings.LLM_PROVIDER == "gateway":
        return OpenAICompatibleGatewayProvider(
            api_key=settings.GATEWAY_API_KEY,
            base_url=settings.GATEWAY_BASE_URL,
            model=settings.GATEWAY_MODEL,
        )
    return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
