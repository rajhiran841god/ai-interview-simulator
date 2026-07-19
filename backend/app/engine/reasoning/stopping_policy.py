"""
StoppingPolicy — isolated per reviewer's recommendation, so the
stopping rule can be tested and (eventually) swapped independently of
strategy selection and decision assembly.

Implements Reasoning_Engine_Contract.md's stopping condition exactly:
floor overrides everything, ceiling overrides everything, otherwise
average+minimum confidence rule.
"""

from dataclasses import dataclass
from typing import Optional

from app.shared.reasoning_config import (
    MIN_QUESTIONS,
    MAX_QUESTIONS,
    STOP_CONFIDENCE_THRESHOLD,
    STOP_CONFIDENCE_FLOOR,
)


@dataclass
class StoppingDecision:
    should_stop: bool
    reason: Optional[str] = None


def evaluate_stopping_condition(
    question_count: int, competency_confidences: list[float]
) -> StoppingDecision:
    if question_count < MIN_QUESTIONS:
        return StoppingDecision(
            should_stop=False,
            reason=f"Below minimum question count ({question_count} < {MIN_QUESTIONS}) — floor overrides.",
        )

    if question_count >= MAX_QUESTIONS:
        return StoppingDecision(
            should_stop=True,
            reason=f"Maximum question count reached ({question_count} >= {MAX_QUESTIONS}).",
        )

    if not competency_confidences:
        # No competencies tracked — caller (service.py) should have
        # already raised NO_COMPETENCIES_INITIALIZED before reaching
        # here; this is a defensive fallback, not the primary guard.
        return StoppingDecision(
            should_stop=False, reason="No competency confidence data available."
        )

    average_confidence = sum(competency_confidences) / len(competency_confidences)
    minimum_confidence = min(competency_confidences)

    if (
        average_confidence >= STOP_CONFIDENCE_THRESHOLD
        and minimum_confidence >= STOP_CONFIDENCE_FLOOR
    ):
        return StoppingDecision(
            should_stop=True,
            reason=(
                f"Target confidence threshold reached: average={average_confidence:.2f} "
                f">= {STOP_CONFIDENCE_THRESHOLD}, minimum={minimum_confidence:.2f} >= {STOP_CONFIDENCE_FLOOR}."
            ),
        )

    return StoppingDecision(
        should_stop=False,
        reason=(
            f"Confidence not yet sufficient: average={average_confidence:.2f}, "
            f"minimum={minimum_confidence:.2f} (need avg>={STOP_CONFIDENCE_THRESHOLD} "
            f"and min>={STOP_CONFIDENCE_FLOOR})."
        ),
    )
