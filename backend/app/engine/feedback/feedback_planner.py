"""
FeedbackPlanner — isolated per reviewer's recommendation, and the
extra stage beyond Module 9's pattern. Decides WHAT belongs in the
report (structure, evidence sets, contradiction flags) BEFORE any LLM
call — so the LLM's job narrows to prose quality, not deciding what
counts as a strength or a gap. Fully deterministic, independently
testable without any provider mocking.
"""

from dataclasses import dataclass

from app.engine.feedback.evidence_collector import CollectedEvidence
from app.shared.types import Emphasis


@dataclass
class CompetencyPlan:
    competency_id: str
    emphasis: Emphasis
    supporting_items: list  # CollectedEvidenceItem, relation == "supports"
    contradictory_items: list  # CollectedEvidenceItem, relation == "contradicts"
    has_unresolved_contradiction: bool
    insufficient_evidence: bool


def plan_competency_feedback(
    collected: CollectedEvidence, emphasis: Emphasis
) -> CompetencyPlan:
    supporting = [item for item in collected.items if item.relation == "supports"]
    contradictory = [item for item in collected.items if item.relation == "contradicts"]

    return CompetencyPlan(
        competency_id=collected.competency_id,
        emphasis=emphasis,
        supporting_items=supporting,
        contradictory_items=contradictory,
        has_unresolved_contradiction=len(contradictory) > 0,
        insufficient_evidence=len(collected.items) == 0,
    )
