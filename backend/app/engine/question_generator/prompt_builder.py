"""
PromptBuilder — isolated per reviewer's recommendation. Assembles the
system/user prompt from a ReasoningDecision + GroundingContext. Knows
nothing about ProviderAdapter or retries — pure prompt construction,
so prompt engineering stays isolated from orchestration.
"""

from app.engine.question_generator.grounding_builder import GroundingContext
from app.engine.reasoning.schema import ReasoningDecision

SYSTEM_PROMPT = """You are conducting a mock interview. Generate ONE natural-language
interview question based on the structured context provided.

CRITICAL RULE: If grounding evidence is provided (prior things the
candidate said), you may reference or paraphrase it naturally, but
NEVER invent or add any claim about what the candidate said that isn't
in the provided evidence. If no grounding evidence is provided, ask an
open question about the competency without referencing anything
specific.

Return ONLY the question text itself, nothing else — no preamble, no
quotes, no explanation."""


def build_prompt(decision: ReasoningDecision, grounding: GroundingContext) -> str:
    lines = [
        f"Competency being assessed: {decision.target_competency_id}",
        f"Strategy: {decision.decision_strategy}",
        f"What's missing: {decision.evidence_missing}",
        f"Why this question: {decision.reason_for_asking}",
    ]

    if grounding.evidence_excerpts:
        lines.append(
            "\nWhat the candidate has said so far about this competency (use only this, verbatim in spirit):"
        )
        for excerpt in grounding.evidence_excerpts:
            lines.append(f'- "{excerpt}"')
    else:
        lines.append(
            "\nNo prior evidence for this competency yet — this opens the topic."
        )

    if grounding.has_contradiction:
        lines.append(
            "\nNote: the candidate's answers contain a contradiction for this competency. "
            "The question should surface this directly but professionally."
        )

    return "\n".join(lines)
