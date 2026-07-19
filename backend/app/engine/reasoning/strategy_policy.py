"""
StrategyPolicy — isolated per reviewer's recommendation. This is the
single most speculative piece of logic in the project: a first-pass
heuristic for "what would a good interviewer do next," not validated
against real interview data.

Isolating it here means a future replacement (e.g. expected
information gain instead of lowest-confidence targeting) only touches
this file — StoppingPolicy, DecisionAssembler, and every other module
remain untouched, exactly the property the reviewer wanted.

switch_competency is NOT selected by this heuristic in v0.1 —
explicitly deferred per the contract, not half-implemented.
"""

from dataclasses import dataclass

from app.shared.reasoning_config import STOP_CONFIDENCE_THRESHOLD, STOP_CONFIDENCE_FLOOR
from app.shared.types import DecisionStrategy


@dataclass
class StrategySelection:
    target_competency_id: str
    strategy: DecisionStrategy
    evidence_missing: str
    reason_for_asking: str


def select_strategy(
    target_competency_id: str,
    target_evidence_count: int,
    target_confidence: float,
    has_contradiction: bool,
) -> StrategySelection:
    # Priority order, exactly as documented in the contract:
    # contradiction > no evidence > below floor > below threshold > wrap up.
    # Contradictions dominate every other signal — an unresolved
    # inconsistency is treated as more informative than one more
    # supporting example.
    if has_contradiction:
        strategy: DecisionStrategy = "challenge_inconsistency"
        evidence_missing = (
            f"Unresolved contradiction in evidence for {target_competency_id}."
        )
        reason = f"Prior evidence for {target_competency_id} contains a contradiction that needs to be addressed directly."
    elif target_evidence_count == 0:
        strategy = "probe_deeper"
        evidence_missing = f"No evidence yet collected for {target_competency_id}."
        reason = (
            f"{target_competency_id} has not been explored yet — opening the topic."
        )
    elif target_confidence < STOP_CONFIDENCE_FLOOR:
        strategy = "probe_deeper"
        evidence_missing = f"Confidence for {target_competency_id} ({target_confidence:.2f}) remains below the acceptance floor."
        reason = f"{target_competency_id} still has insufficient evidence — continuing to gather."
    elif target_confidence < STOP_CONFIDENCE_THRESHOLD:
        strategy = "verify"
        evidence_missing = f"Confidence for {target_competency_id} ({target_confidence:.2f}) is borderline."
        reason = (
            f"{target_competency_id} is close to sufficient but needs confirmation."
        )
    else:
        strategy = "wrap_up_competency"
        evidence_missing = f"{target_competency_id} already has strong evidence but remains the lowest-confidence competency."
        reason = f"{target_competency_id} is comparatively strong — wrapping up before moving on."

    return StrategySelection(
        target_competency_id=target_competency_id,
        strategy=strategy,
        evidence_missing=evidence_missing,
        reason_for_asking=reason,
    )
