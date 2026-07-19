"""
Public API for Reasoning Engine — the DecisionAssembler role from the
reviewer's recommended three-piece structure: pulls StoppingPolicy and
StrategyPolicy together, generates question_id, writes the Logging
trace, returns the final ReasoningDecision.

Deterministic — no ProviderAdapter, no LLM. Reads Competency Model and
Evidence Graph; writes ONLY to Logging (AC12's read-only guarantee).
"""

import uuid
from typing import Optional

from app.engine.reasoning.schema import (
    ReasoningDecision,
    ReasoningEngineError,
    ErrorCode,
)
from app.engine.reasoning.stopping_policy import evaluate_stopping_condition
from app.engine.reasoning.strategy_policy import select_strategy
from app.engine.competency_model.service import CompetencyModelService
from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.logging.service import LoggingService


class ReasoningEngineService:
    def __init__(
        self,
        competency_model: Optional[CompetencyModelService] = None,
        evidence_graph: Optional[EvidenceGraphService] = None,
        logging_service: Optional[LoggingService] = None,
    ):
        self._competency_model = competency_model or CompetencyModelService()
        self._evidence_graph = evidence_graph or EvidenceGraphService()
        self._logging = logging_service or LoggingService()

    def decide_next_action(self, interview_id: str) -> ReasoningDecision:
        states = self._competency_model.get_all_competency_states(interview_id)
        if not states:
            raise ReasoningEngineError(
                ErrorCode.NO_COMPETENCIES_INITIALIZED,
                f"No competencies initialized for interview '{interview_id}'.",
            )

        question_count = len(self._logging.get_traces_for_interview(interview_id))
        confidences = [s.confidence for s in states]

        stopping = evaluate_stopping_condition(question_count, confidences)

        if stopping.should_stop:
            return ReasoningDecision(
                question_id=self._generate_question_id(),
                decision_type="stop",
                stop_reason=stopping.reason,
            )

        # Continue: select target + strategy
        target_competency_id = self._competency_model.get_lowest_confidence_competency(
            interview_id
        )
        if target_competency_id is None:
            # Defensive guard: states is non-empty (checked above), so
            # this should be unreachable in practice — but mypy is
            # correctly pointing out the return type is Optional, and
            # trusting that without a check is exactly the kind of
            # assumption that caused real bugs in earlier modules.
            raise ReasoningEngineError(
                ErrorCode.NO_COMPETENCIES_INITIALIZED,
                f"get_lowest_confidence_competency returned None for interview "
                f"'{interview_id}' despite non-empty competency states — inconsistent state.",
            )

        target_state = self._competency_model.get_competency_state(
            interview_id, target_competency_id
        )
        if target_state is None:
            raise ReasoningEngineError(
                ErrorCode.NO_COMPETENCIES_INITIALIZED,
                f"No state found for competency '{target_competency_id}' despite being "
                f"returned as lowest-confidence — inconsistent state.",
            )

        has_contradiction = self._evidence_graph.has_contradictions(
            interview_id, target_competency_id
        )

        selection = select_strategy(
            target_competency_id=target_competency_id,
            target_evidence_count=target_state.evidence_count,
            target_confidence=target_state.confidence,
            has_contradiction=has_contradiction,
        )

        question_id = self._generate_question_id()

        try:
            self._logging.record_trace(
                interview_id=interview_id,
                question_id=question_id,
                decision_strategy=selection.strategy,
                confidence_pre=target_state.confidence,
                evidence_missing=selection.evidence_missing,
                reason_for_asking=selection.reason_for_asking,
                prompt_version="reasoning_engine_v1.0.0",
                model_version="deterministic",  # this module makes no LLM call
                target_competency_id=target_competency_id,
            )
        except Exception as e:
            raise ReasoningEngineError(
                ErrorCode.TRACE_WRITE_FAILED,
                f"Failed to write reasoning trace: {e}",
            )

        return ReasoningDecision(
            question_id=question_id,
            decision_type="continue",
            target_competency_id=target_competency_id,
            decision_strategy=selection.strategy,
            evidence_missing=selection.evidence_missing,
            reason_for_asking=selection.reason_for_asking,
        )

    def _generate_question_id(self) -> str:
        return str(uuid.uuid4())
