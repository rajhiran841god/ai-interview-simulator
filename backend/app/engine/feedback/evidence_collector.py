"""
EvidenceCollector — isolated per reviewer's recommendation. Gathers
REAL evidence from Evidence Graph and enriches with real question
context from Conversation Memory. Never invents anything; returns
exactly what's stored.
"""

from dataclasses import dataclass

from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.conversation_memory.service import ConversationMemoryService


@dataclass
class CollectedEvidenceItem:
    evidence_id: str
    evidence_excerpt: str
    relation: str
    question_text: str  # real text from Conversation Memory, via the evidence's turn_id


@dataclass
class CollectedEvidence:
    competency_id: str
    items: list[CollectedEvidenceItem]


def collect_evidence(
    evidence_graph: EvidenceGraphService,
    conversation_memory: ConversationMemoryService,
    interview_id: str,
    competency_id: str,
) -> CollectedEvidence:
    entries = evidence_graph.get_evidence_for_competency(interview_id, competency_id)
    history = conversation_memory.get_history(interview_id)
    question_by_turn_id = {t.turn_id: t.question_text for t in history}

    items = [
        CollectedEvidenceItem(
            evidence_id=e.evidence_id,
            evidence_excerpt=e.evidence_excerpt,
            relation=e.relation,
            question_text=question_by_turn_id.get(e.turn_id, ""),
        )
        for e in entries
    ]
    return CollectedEvidence(competency_id=competency_id, items=items)
