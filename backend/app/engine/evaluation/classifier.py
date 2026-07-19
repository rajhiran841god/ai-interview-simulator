"""
Pipeline stage 2 & 3 (per reviewer's recommended pipeline shape):
Call ProviderAdapter, parse structured response.

Only place in this module that touches the LLM — routes exclusively
through get_provider(), never the SDK directly.
"""

import json

from app.core.provider_adapter import get_provider

CLASSIFICATION_SYSTEM_PROMPT = """You are evaluating a candidate's answer in a mock interview.

You are given:
- The gap the question was trying to close (evidence_missing)
- The candidate's answer

Classify the answer as exactly one of:
- "substantive": directly and specifically addresses the gap with real detail
- "partial": addresses it somewhat but leaves real ambiguity or lacks specificity
- "deflection": answers a different, easier question instead of the one asked
- "non_answer": doesn't engage with the question at all (e.g. "I don't know", off-topic, refusal)

Distinguish deflection from non_answer carefully: a deflection is a
confident, engaged response to a DIFFERENT question than the one
asked. A non_answer shows no real engagement at all.

If the answer is substantive or partial, extract 1-3 pieces of
evidence: exact quoted substrings from the answer that support or
relate to the competency being evaluated. Only include evidence you
can quote EXACTLY from the answer text — never paraphrase or
summarize as if it were a quote.

Also determine whether this answer appears to CONTRADICT anything
that would typically already be established (you will be told what
prior evidence exists, if any, so you can check for direct conflicts
— e.g. "I led the decision" vs a prior answer saying "my manager made
all decisions").

Provide a confidence_contribution between 0.0 and 1.0 reflecting how
convincingly THIS SPECIFIC ANSWER addressed the gap — not an overall
judgment of the candidate.

Return ONLY valid JSON matching this exact shape, nothing else:
{
  "answer_classification": "substantive|partial|deflection|non_answer",
  "evidence_excerpts": ["exact quoted text from the answer", "..."],
  "contradicts_prior_evidence": true|false,
  "contradiction_explanation": "..." or null,
  "confidence_contribution": 0.0-1.0,
  "reasoning_summary": "brief human-readable explanation"
}
"""


def classify_answer(
    evidence_missing: str, answer_text: str, prior_evidence_excerpts: list[str]
) -> dict:
    """Returns raw dict, NOT yet validated. Caller (service.py) must
    validate confidence range and evidence traceability before trusting
    any value — same discipline as Resume/JD Understanding's
    structurer.py modules."""
    provider = get_provider()
    prior_context = (
        "\n".join(f"- {e}" for e in prior_evidence_excerpts)
        if prior_evidence_excerpts
        else "(no prior evidence recorded for this competency yet)"
    )
    user_message = (
        f"Gap this question targets: {evidence_missing}\n\n"
        f"Prior evidence for this competency:\n{prior_context}\n\n"
        f"Candidate's answer:\n{answer_text}"
    )
    response_text = provider.complete(
        system=CLASSIFICATION_SYSTEM_PROMPT, user=user_message, max_tokens=1500
    )

    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}
