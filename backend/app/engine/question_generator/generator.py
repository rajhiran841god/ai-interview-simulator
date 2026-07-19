"""
Generator — the ONLY component in this module that touches
ProviderAdapter, per reviewer's explicit provider-isolation
requirement. Pure LLM call wrapper; no prompt construction, no retry
logic, no grounding logic.
"""

from app.core.provider_adapter import get_provider


def call_generation(system_prompt: str, user_prompt: str) -> str:
    """Returns raw text, or empty string on failure/empty response —
    caller (service.py) decides what empty/failure means for retry
    and fallback behavior. This function does not itself catch
    exceptions from get_provider() — a hard provider failure (e.g.
    network error) propagates up rather than being silently absorbed
    here, consistent with keeping this component minimal."""
    provider = get_provider()
    response = provider.complete(system=system_prompt, user=user_prompt, max_tokens=200)
    return response.strip()
