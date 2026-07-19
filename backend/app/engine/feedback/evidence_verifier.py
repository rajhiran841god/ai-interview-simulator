"""
EvidenceVerifier — isolated per reviewer's recommendation. Checks
every evidence_id the LLM claims to have cited against the REAL known
set supplied to it. Any ID not in that set is dropped — defensive,
same "never trust LLM output blindly" discipline as every prior
provider-using module.
"""

from dataclasses import dataclass

from app.engine.feedback.feedback_planner import CompetencyPlan


@dataclass
class VerifiedCitation:
    supporting_evidence_ids: list[str]
    contradictory_evidence_ids: list[str]
    dropped_fabricated_ids: list[str]


def verify_cited_evidence(
    plan: CompetencyPlan, cited_evidence_ids: list[str]
) -> VerifiedCitation:
    real_supporting_ids = {i.evidence_id for i in plan.supporting_items}
    real_contradictory_ids = {i.evidence_id for i in plan.contradictory_items}

    verified_supporting = []
    verified_contradictory = []
    dropped = []

    for eid in cited_evidence_ids:
        if eid in real_supporting_ids:
            verified_supporting.append(eid)
        elif eid in real_contradictory_ids:
            verified_contradictory.append(eid)
        else:
            # Not in the real known set at all — fabricated/hallucinated ID, drop it.
            dropped.append(eid)

    return VerifiedCitation(
        supporting_evidence_ids=verified_supporting,
        contradictory_evidence_ids=verified_contradictory,
        dropped_fabricated_ids=dropped,
    )
