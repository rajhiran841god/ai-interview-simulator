"""
GroundingBuilder — isolated per reviewer's recommendation. Its only
job: gather REAL evidence excerpts from Evidence Graph for a target
competency. Never invents or summarizes; returns exactly what's
stored, so PromptBuilder can never accidentally receive fabricated
grounding context.
"""

from dataclasses import dataclass

from app.engine.evidence_graph.service import EvidenceGraphService


@dataclass
class GroundingContext:
    evidence_excerpts: list[str]
    has_contradiction: bool


def build_grounding_context(
    evidence_graph: EvidenceGraphService, interview_id: str, competency_id: str
) -> GroundingContext:
    entries = evidence_graph.get_evidence_for_competency(interview_id, competency_id)
    excerpts = [e.evidence_excerpt for e in entries]
    has_contradiction = evidence_graph.has_contradictions(interview_id, competency_id)
    return GroundingContext(
        evidence_excerpts=excerpts, has_contradiction=has_contradiction
    )
