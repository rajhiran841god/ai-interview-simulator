"""
Generator — the ONLY component in this module touching ProviderAdapter,
per reviewer's provider-isolation requirement. Turns a CompetencyPlan
into prose, asking the LLM to cite which evidence_ids it drew on.
"""

import json

from app.core.provider_adapter import get_provider
from app.engine.feedback.feedback_planner import CompetencyPlan

SYSTEM_PROMPT = """You write qualitative interview feedback for a candidate, based ONLY
on the evidence provided. You must never invent evidence or claims
not present in what's given to you.

You will be given a competency, a list of supporting evidence items,
a list of contradictory evidence items (if any), and whether evidence
is insufficient.

If insufficient_evidence is true, your summary must plainly say there
wasn't enough discussion of this area to give meaningful feedback —
do not invent an assessment.

If there are contradictory items, address the inconsistency directly
and professionally.

For every claim you make, cite which evidence_id(s) from the supplied
list support it.

Return ONLY valid JSON:
{
  "summary_text": "...",
  "cited_evidence_ids": ["...", "..."]
}
"""


def call_feedback_generation(plan: CompetencyPlan) -> dict:
    """Returns raw dict, NOT yet verified. Caller (service.py via
    EvidenceVerifier) must check every cited_evidence_id against the
    real known set before trusting it."""
    if plan.insufficient_evidence:
        user_prompt = (
            f"Competency: {plan.competency_id}\n"
            f"insufficient_evidence: true\n"
            f"No evidence was collected for this competency."
        )
    else:
        supporting_json = [
            {"evidence_id": i.evidence_id, "excerpt": i.evidence_excerpt}
            for i in plan.supporting_items
        ]
        contradictory_json = [
            {"evidence_id": i.evidence_id, "excerpt": i.evidence_excerpt}
            for i in plan.contradictory_items
        ]
        user_prompt = (
            f"Competency: {plan.competency_id}\n"
            f"Supporting evidence: {json.dumps(supporting_json)}\n"
            f"Contradictory evidence: {json.dumps(contradictory_json)}\n"
            f"has_unresolved_contradiction: {plan.has_unresolved_contradiction}"
        )

    provider = get_provider()
    response_text = provider.complete(
        system=SYSTEM_PROMPT, user=user_prompt, max_tokens=400
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
