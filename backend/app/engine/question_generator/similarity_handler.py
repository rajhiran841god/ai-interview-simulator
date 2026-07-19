"""
SimilarityHandler — isolated per reviewer's recommendation. Owns the
bounded retry/fallback policy: attempt generation, check similarity
against recent history, retry ONCE if too similar, then fall back to
a deterministic template. Never loops beyond one retry.
"""

from dataclasses import dataclass
from typing import Callable, Literal

from app.engine.conversation_memory.service import ConversationMemoryService
from app.engine.question_generator.prompt_builder import SYSTEM_PROMPT

GenerationMethod = Literal["llm", "fallback_template"]


@dataclass
class GenerationOutcome:
    question_text: str
    generation_method: GenerationMethod
    provider_call_count: int


def generate_with_retry(
    conversation_memory: ConversationMemoryService,
    interview_id: str,
    user_prompt: str,
    call_generation_fn: Callable[[str, str], str],
    fallback_text: str,
) -> GenerationOutcome:
    provider_call_count = 0

    for attempt in range(2):  # one initial attempt + exactly one retry
        try:
            text = call_generation_fn(SYSTEM_PROMPT, user_prompt)
        except Exception:
            text = ""
        provider_call_count += 1

        if not text:
            continue  # generation failed outright — try again if we have an attempt left

        if not conversation_memory.has_asked_similar(interview_id, text):
            return GenerationOutcome(
                question_text=text,
                generation_method="llm",
                provider_call_count=provider_call_count,
            )
        # too similar — loop will retry once, per the "for attempt in range(2)" bound

    # Both attempts exhausted (failed generation, or both too similar) — fallback.
    return GenerationOutcome(
        question_text=fallback_text,
        generation_method="fallback_template",
        provider_call_count=provider_call_count,
    )
