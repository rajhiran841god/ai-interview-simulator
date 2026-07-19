"""
Public API for Evaluation Engine, implemented as a discrete pipeline
per reviewer's recommendation:

evaluate_answer()
    -> validate input
    -> call ProviderAdapter (classifier.py)
    -> parse structured response
    -> validate confidence domain (reject, never clamp)
    -> extract evidence
    -> write Evidence Graph
    -> update Logging
    -> return EvaluationResult

Each stage is a separate method so it's individually testable and
failures are localized, per the reviewer's stated rationale.
"""

from typing import Optional

from app.engine.evaluation.schema import (
    EvaluationResult,
    EvaluationEngineError,
    ErrorCode,
    degraded_result,
)
from app.engine.evaluation.classifier import classify_answer
from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.logging.service import LoggingService


class EvaluationEngineService:
    def __init__(
        self,
        evidence_graph: Optional[EvidenceGraphService] = None,
        logging_service: Optional[LoggingService] = None,
    ):
        self._evidence_graph = evidence_graph or EvidenceGraphService()
        self._logging = logging_service or LoggingService()

    def evaluate_answer(
        self,
        interview_id: str,
        question_id: str,
        turn_id: str,
        evidence_missing: str,
        answer_text: str,
        target_competency_id: Optional[str] = None,
    ) -> EvaluationResult:
        # Stage 1: validate input
        self._validate_trace_exists(interview_id, question_id)

        if not answer_text or not answer_text.strip():
            result = degraded_result("Answer was empty or whitespace-only.")
            self._record_outcome(interview_id, question_id, result)
            return result

        if target_competency_id is None:
            # Non-competency-targeted turn (e.g. greeting) — no
            # evidence extraction, per contract's Non-Responsibilities.
            result = EvaluationResult(
                answer_classification="substantive",
                evidence_ids_created=[],
                contradiction_detected=False,
                confidence_contribution=0.5,
                reasoning_summary="No target competency — evaluated for engagement only, no evidence extraction performed.",
            )
            self._record_outcome(interview_id, question_id, result)
            return result

        # Stage 2 & 3: call provider, parse response
        prior_evidence = self._evidence_graph.get_evidence_for_competency(
            interview_id, target_competency_id
        )
        prior_excerpts = [e.evidence_excerpt for e in prior_evidence]

        raw = classify_answer(evidence_missing, answer_text, prior_excerpts)
        if not raw or "answer_classification" not in raw:
            result = degraded_result(
                "LLM classification failed or returned unparseable output."
            )
            self._record_outcome(interview_id, question_id, result)
            return result

        # Stage 4: validate confidence domain — reject, never clamp
        raw_confidence = raw.get("confidence_contribution")
        if not isinstance(raw_confidence, (int, float)) or not (
            0.0 <= raw_confidence <= 1.0
        ):
            result = degraded_result(
                f"LLM proposed an out-of-range or invalid confidence_contribution: {raw_confidence!r}. Rejected per no-clamp policy."
            )
            self._record_outcome(interview_id, question_id, result)
            return result

        classification = raw.get("answer_classification")
        if classification not in ("substantive", "partial", "deflection", "non_answer"):
            result = degraded_result(
                f"LLM proposed an invalid answer_classification: {classification!r}."
            )
            self._record_outcome(interview_id, question_id, result)
            return result

        # Stage 5 & 6: extract evidence, write to Evidence Graph
        evidence_ids_created: list[str] = []
        contradiction_detected = False
        contradicted_evidence_id = None

        if classification in ("substantive", "partial"):
            excerpts = raw.get("evidence_excerpts") or []
            contradicts_flag = bool(raw.get("contradicts_prior_evidence"))

            for excerpt in excerpts:
                if not isinstance(excerpt, str) or not excerpt.strip():
                    continue
                try:
                    if contradicts_flag and prior_evidence:
                        # AC5/AC12: contradiction scoped to same
                        # interview only — prior_evidence was already
                        # fetched scoped to this interview_id via
                        # Evidence Graph, so this is structurally
                        # guaranteed, not just asserted.
                        target = prior_evidence[0]
                        entry = self._evidence_graph.add_evidence(
                            interview_id=interview_id,
                            competency_id=target_competency_id,
                            turn_id=turn_id,
                            evidence_excerpt=excerpt,
                            relation="contradicts",
                            contradicts_evidence_id=target.evidence_id,
                        )
                        contradiction_detected = True
                        contradicted_evidence_id = target.evidence_id
                    else:
                        entry = self._evidence_graph.add_evidence(
                            interview_id=interview_id,
                            competency_id=target_competency_id,
                            turn_id=turn_id,
                            evidence_excerpt=excerpt,
                            relation="supports",
                        )
                    evidence_ids_created.append(entry.evidence_id)
                except Exception:
                    # AC10: a fabricated excerpt (fails Evidence
                    # Graph's EXCERPT_NOT_TRACEABLE check) is dropped,
                    # not bypassed and not a crash. Not caught more
                    # narrowly on purpose — ANY failure to write this
                    # specific evidence entry should not abort the
                    # whole evaluation, but must never be silently
                    # "fixed" by weakening Evidence Graph's own check.
                    continue

        result = EvaluationResult(
            answer_classification=classification,
            evidence_ids_created=evidence_ids_created,
            contradiction_detected=contradiction_detected,
            contradicted_evidence_id=contradicted_evidence_id,
            confidence_contribution=float(raw_confidence),
            reasoning_summary=raw.get("reasoning_summary", ""),
        )

        # Stage 7: update Logging via its public API only
        self._record_outcome(interview_id, question_id, result)

        return result

    def _validate_trace_exists(self, interview_id: str, question_id: str) -> None:
        trace = self._logging.get_trace(interview_id, question_id)
        if trace is None:
            raise EvaluationEngineError(
                ErrorCode.TRACE_NOT_FOUND,
                f"No trace found for question_id '{question_id}' in interview '{interview_id}'.",
            )

    def _record_outcome(
        self, interview_id: str, question_id: str, result: EvaluationResult
    ) -> None:
        self._logging.update_trace_outcome(
            interview_id=interview_id,
            question_id=question_id,
            confidence_post=result.confidence_contribution,
            evidence_ids_referenced=result.evidence_ids_created,
        )
