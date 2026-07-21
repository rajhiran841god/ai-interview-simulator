"""
Public API for Feedback Generator. Orchestrates EvidenceCollector,
FeedbackPlanner, Generator, EvidenceVerifier, FallbackFormatter — per
reviewer's recommended five-piece internal structure.

This is the final module in the 10-module Interview Intelligence
Engine. AC1 (no confidence leakage) is the merge-blocking criterion:
verified structurally by schema, not just by example output.
"""

import datetime
import re
from typing import Optional

from app.engine.feedback.schema import (
    InterviewFeedbackReport,
    CompetencyFeedback,
    FeedbackGeneratorError,
    ErrorCode,
)
from app.engine.feedback.evidence_collector import collect_evidence
from app.engine.feedback.feedback_planner import plan_competency_feedback
from app.engine.feedback.generator import call_feedback_generation
from app.engine.feedback.evidence_verifier import verify_cited_evidence
from app.engine.feedback.fallback_formatter import fallback_summary_text

from app.engine.competency_model.service import CompetencyModelService
from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.conversation_memory.service import ConversationMemoryService
from app.shared.types import Emphasis


class FeedbackGeneratorService:
    def __init__(
        self,
        competency_model: Optional[CompetencyModelService] = None,
        evidence_graph: Optional[EvidenceGraphService] = None,
        conversation_memory: Optional[ConversationMemoryService] = None,
    ):
        self._competency_model = competency_model or CompetencyModelService()
        self._evidence_graph = evidence_graph or EvidenceGraphService()
        self._conversation_memory = conversation_memory or ConversationMemoryService()

    def generate_feedback_report(self, interview_id: str) -> InterviewFeedbackReport:
        states = self._competency_model.get_all_competency_states(interview_id)
        if not states:
            raise FeedbackGeneratorError(
                ErrorCode.NO_COMPETENCIES_INITIALIZED,
                f"No competencies initialized for interview '{interview_id}'.",
            )

        # Deterministic ordering: emphasis (primary first) then
        # competency_id alphabetically — never derived from confidence,
        # even implicitly (AC8).
        ordered_states = sorted(
            states, key=lambda s: (0 if s.emphasis == "primary" else 1, s.competency_id)
        )

        competency_feedback_list = []
        for state in ordered_states:
            feedback = self._generate_for_competency(
                interview_id, state.competency_id, state.emphasis
            )
            competency_feedback_list.append(feedback)

        overall_summary = self._build_overall_summary(competency_feedback_list)

        return InterviewFeedbackReport(
            interview_id=interview_id,
            competency_feedback=competency_feedback_list,
            overall_summary=overall_summary,
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    def _generate_for_competency(
        self, interview_id: str, competency_id: str, emphasis: Emphasis
    ) -> CompetencyFeedback:
        # 1. EvidenceCollector
        collected = collect_evidence(
            self._evidence_graph, self._conversation_memory, interview_id, competency_id
        )
        # 2. FeedbackPlanner — decides structure BEFORE any LLM call
        plan = plan_competency_feedback(collected, emphasis)

        # 3. Generator
        raw = call_feedback_generation(plan)

        if not raw or "summary_text" not in raw:
            # GENERATION_FAILED — per-competency fallback, does not abort the report
            return CompetencyFeedback(
                competency_id=competency_id,
                emphasis=emphasis,
                summary_text=fallback_summary_text(
                    competency_id, plan.insufficient_evidence
                ),
                supporting_evidence_ids=[],
                contradictory_evidence_ids=[],
                has_unresolved_contradiction=plan.has_unresolved_contradiction,
                insufficient_evidence=plan.insufficient_evidence,
            )

        # 4. EvidenceVerifier — never trust cited IDs blindly
        cited_ids = raw.get("cited_evidence_ids", [])
        verified = verify_cited_evidence(plan, cited_ids)

        return CompetencyFeedback(
            competency_id=competency_id,
            emphasis=emphasis,
            summary_text=_scrub_evidence_ids(raw.get("summary_text", "")),
            supporting_evidence_ids=verified.supporting_evidence_ids,
            contradictory_evidence_ids=verified.contradictory_evidence_ids,
            has_unresolved_contradiction=plan.has_unresolved_contradiction,
            insufficient_evidence=plan.insufficient_evidence,
        )

    def _build_overall_summary(self, feedback_list: list[CompetencyFeedback]) -> str:
        # Deterministic, non-LLM overall summary — counts only, no
        # confidence involved, avoiding a second generation call whose
        # failure would be harder to degrade gracefully at the report level.
        total = len(feedback_list)
        insufficient = sum(1 for f in feedback_list if f.insufficient_evidence)
        contradictions = sum(1 for f in feedback_list if f.has_unresolved_contradiction)
        parts = [f"Feedback generated for {total} competencies."]
        if insufficient:
            parts.append(f"{insufficient} had insufficient evidence collected.")
        if contradictions:
            parts.append(
                f"{contradictions} contain unresolved contradictions worth reviewing."
            )
        return " ".join(parts)


# UUID pattern (standard 8-4-4-4-12 hex format, the shape every
# evidence_id in this project actually takes — see uuid.uuid4() calls
# in evidence_graph/store.py). Also strips common citation-marker
# wrapping like "(evidence: ...)" around it, so the scrub doesn't just
# remove the ID and leave an awkward empty parenthetical behind.
_UUID_PATTERN = re.compile(
    r"\s*\(?\s*(?:evidence[:\s]*)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\)?",
    re.IGNORECASE,
)


def _scrub_evidence_ids(summary_text: str) -> str:
    """
    Defensive, structural safeguard — per the project's established
    discipline of never trusting LLM prompt compliance alone (the same
    reasoning behind EvidenceVerifier's structural ID check). Found
    necessary via live validation: a real model response embedded raw
    evidence_id UUIDs directly in prose (e.g. "...redesigned our
    approach (evidence: c8f16fa5-4b83-40de-9d74-b21e748094d7)."),
    despite the system prompt asking it not to. Strips any UUID-shaped
    string from student-facing text, regardless of how the model
    chooses to format it, rather than relying solely on prompt wording
    to prevent this.
    """
    cleaned = _UUID_PATTERN.sub("", summary_text)
    # Collapse any resulting double spaces or dangling punctuation
    # left behind by the removal (e.g. "feedback . " -> "feedback.")
    cleaned = re.sub(r"\s+([.,;])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()
