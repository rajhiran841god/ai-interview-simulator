"""
Public API for Question Generator. Orchestrates GroundingBuilder,
PromptBuilder, Generator, and SimilarityHandler, per reviewer's
recommended internal structure. Records the resulting turn in
Conversation Memory.
"""

import datetime
from typing import Optional

from app.engine.question_generator.schema import (
    GeneratedQuestion,
    QuestionGeneratorError,
    ErrorCode,
)
from app.engine.question_generator.grounding_builder import build_grounding_context
from app.engine.question_generator.prompt_builder import build_prompt
from app.engine.question_generator.generator import call_generation
from app.engine.question_generator.similarity_handler import generate_with_retry
from app.engine.question_generator.fallback_templates import fallback_question_text

from app.engine.reasoning.schema import ReasoningDecision
from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.conversation_memory.service import ConversationMemoryService
from app.shared.types import QuestionType


class QuestionGeneratorService:
    def __init__(
        self,
        evidence_graph: Optional[EvidenceGraphService] = None,
        conversation_memory: Optional[ConversationMemoryService] = None,
    ):
        self._evidence_graph = evidence_graph or EvidenceGraphService()
        self._conversation_memory = conversation_memory or ConversationMemoryService()

    def generate_question(
        self, interview_id: str, reasoning_decision: ReasoningDecision
    ) -> GeneratedQuestion:
        if reasoning_decision.decision_type != "continue":
            raise QuestionGeneratorError(
                ErrorCode.INVALID_DECISION_TYPE,
                f"Cannot generate a question for decision_type '{reasoning_decision.decision_type}'.",
            )

        target_competency_id = reasoning_decision.target_competency_id
        assert (
            target_competency_id is not None
        )  # guaranteed by decision_type == "continue"

        # 1. GroundingBuilder — real evidence only
        grounding = build_grounding_context(
            self._evidence_graph, interview_id, target_competency_id
        )

        # Deterministic question_type mapping — code, not LLM-decided
        question_type = self._determine_question_type(
            reasoning_decision.decision_strategy, grounding.evidence_excerpts
        )

        # 2. PromptBuilder
        user_prompt = build_prompt(reasoning_decision, grounding)

        # 3 & SimilarityHandler — bounded retry via Generator
        fallback_text = fallback_question_text(
            target_competency_id, reasoning_decision.decision_strategy or "probe_deeper"
        )
        outcome = generate_with_retry(
            conversation_memory=self._conversation_memory,
            interview_id=interview_id,
            user_prompt=user_prompt,
            call_generation_fn=call_generation,
            fallback_text=fallback_text,
        )

        # Record the turn — Conversation Memory remains the sole owner
        # of stored turns; this module only calls its public API.
        try:
            self._conversation_memory.record_turn(
                interview_id=interview_id,
                question_id=reasoning_decision.question_id,
                question_text=outcome.question_text,
                question_type=question_type,
                question_timestamp=datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
                target_competency_id=target_competency_id,
            )
        except Exception as e:
            raise QuestionGeneratorError(
                ErrorCode.TURN_RECORDING_FAILED,
                f"Failed to record turn in Conversation Memory: {e}",
            )

        return GeneratedQuestion(
            question_id=reasoning_decision.question_id,
            question_text=outcome.question_text,
            question_type=question_type,
            target_competency_id=target_competency_id,
            generation_method=outcome.generation_method,
        )

    def _determine_question_type(
        self, decision_strategy: Optional[str], evidence_excerpts: list[str]
    ) -> QuestionType:
        if decision_strategy == "probe_deeper":
            return "fresh" if len(evidence_excerpts) == 0 else "cross_question"
        if decision_strategy in (
            "challenge_inconsistency",
            "verify",
            "wrap_up_competency",
        ):
            return "cross_question"
        # switch_competency, or any unmapped value — defaults to fresh
        return "fresh"
