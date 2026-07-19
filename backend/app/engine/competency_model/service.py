"""
Public API for Competency Model.
"""

from typing import Optional

from app.engine.competency_model.schema import (
    CompetencyState,
    CompetencySeed,
    CompetencyModelError,
    ErrorCode,
)
from app.engine.competency_model.store import (
    CompetencyModelStore,
    InMemoryCompetencyModelStore,
)


class CompetencyModelService:
    def __init__(self, store: Optional[CompetencyModelStore] = None):
        self._store = store or InMemoryCompetencyModelStore()

    def initialize_competencies(
        self, interview_id: str, competencies: list[CompetencySeed]
    ) -> list[CompetencyState]:
        return self._store.initialize(interview_id, competencies)

    def update_from_evaluation(
        self,
        interview_id: str,
        competency_id: str,
        confidence_contribution: float,
        contradiction_detected: bool,
        evidence_ids_created: list[str],
    ) -> CompetencyState:
        if not (0.0 <= confidence_contribution <= 1.0):
            raise CompetencyModelError(
                ErrorCode.CONFIDENCE_CONTRIBUTION_OUT_OF_RANGE,
                f"confidence_contribution {confidence_contribution} is outside [0.0, 1.0].",
            )
        return self._store.update(
            interview_id,
            competency_id,
            confidence_contribution,
            contradiction_detected,
            evidence_ids_created,
        )

    def get_competency_state(
        self, interview_id: str, competency_id: str
    ) -> Optional[CompetencyState]:
        return self._store.get_state(interview_id, competency_id)

    def get_all_competency_states(self, interview_id: str) -> list[CompetencyState]:
        return self._store.get_all_states(interview_id)

    def get_lowest_confidence_competency(self, interview_id: str) -> Optional[str]:
        states = self._store.get_all_states(interview_id)
        if not states:
            return None
        lowest = min(states, key=lambda s: s.confidence)
        return lowest.competency_id
