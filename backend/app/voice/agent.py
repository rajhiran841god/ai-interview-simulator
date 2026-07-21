"""
Voice interface adapter — per Decision Log #004.

This is a NEW presentation-layer adapter. It does NOT reimplement or
modify the Interview Intelligence Engine. It calls the exact same
services (ConversationMemoryService, ReasoningEngineService,
QuestionGeneratorService, EvaluationEngineService) that the text
interface already uses.

Voice mechanics (speech-to-text, text-to-speech, turn detection) are
entirely delegated to LiveKit Agents + Deepgram + ElevenLabs — mature,
purpose-built infrastructure. No custom STT/TTS/turn-detection is
implemented here, per Decision #004's implementation constraint.

Architecture of this file:
- InterviewVoiceAgent (Agent subclass) overrides llm_node — the ONE
  hook LiveKit provides for replacing the "generic chat LLM" step with
  custom logic. Everywhere else (STT streaming, turn detection, TTS
  synthesis, audio I/O) is the standard LiveKit pipeline, untouched.
- llm_node pulls the student's latest transcribed answer out of the
  conversation context, feeds it through Evaluation Engine (if this
  isn't the first turn), then Reasoning Engine, then Question
  Generator — exactly the same call sequence the text interface would
  use — and yields the resulting question text for TTS to speak.

KNOWN OPEN RISK (see Decision #004): each turn now makes 1-2 real LLM
calls (Evaluation Engine's classifier, Question Generator's LLM call)
inside the voice turn-taking loop. This adds real latency between
"student stops talking" and "AI starts speaking" that a text interface
never had to worry about. This has NOT been measured yet — it needs
real testing with a live Anthropic API key, same validation gap as
every other LLM-backed module in this project.
"""

import logging
from typing import AsyncIterable, Optional

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, llm
from livekit.plugins import deepgram, elevenlabs, silero

from app.engine.conversation_memory.service import ConversationMemoryService
from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.logging.service import LoggingService
from app.engine.competency_model.service import CompetencyModelService
from app.engine.evaluation.service import EvaluationEngineService
from app.engine.reasoning.service import ReasoningEngineService
from app.engine.question_generator.service import QuestionGeneratorService
from app.shared.turn_timer import TurnTimer

logger = logging.getLogger("placementos.voice")


class InterviewVoiceAgent(Agent):
    """
    Voice front-end for the Interview Intelligence Engine. Wires the
    same services the text interface uses into LiveKit's llm_node hook
    — the engine itself is completely unchanged.
    """

    def __init__(
        self,
        interview_id: str,
        conversation_memory: ConversationMemoryService,
        evidence_graph: EvidenceGraphService,
        logging_service: LoggingService,
        competency_model: CompetencyModelService,
        evaluation_engine: EvaluationEngineService,
        reasoning_engine: ReasoningEngineService,
        question_generator: QuestionGeneratorService,
    ):
        super().__init__(
            instructions=(
                "You are an AI interviewer. You never generate your own "
                "questions directly — question text is supplied by "
                "llm_node from the Interview Intelligence Engine."
            )
        )
        self.interview_id = interview_id
        self._conversation_memory = conversation_memory
        self._evidence_graph = evidence_graph
        self._logging = logging_service
        self._competency_model = competency_model
        self._evaluation_engine = evaluation_engine
        self._reasoning_engine = reasoning_engine
        self._question_generator = question_generator
        # Tracks the question_id currently awaiting an answer, so we
        # know what to evaluate once the student finishes speaking.
        self._pending_question_id: Optional[str] = None
        self._pending_turn_id: Optional[str] = None
        self._pending_evidence_missing: Optional[str] = None
        self._pending_target_competency_id: Optional[str] = None
        self._turn_number = 0

    async def llm_node(
        self, chat_ctx: llm.ChatContext, tools: list, model_settings
    ) -> AsyncIterable[str]:
        """
        The ONE integration point with LiveKit. Replaces a generic LLM
        call with: evaluate the student's last answer (if any) via the
        existing Evaluation Engine -> ask Reasoning Engine what's next
        -> ask Question Generator for the actual question text ->
        yield it for TTS to speak.
        """
        latest_user_message = self._extract_latest_user_text(chat_ctx)

        self._turn_number += 1
        timer = TurnTimer(interview_id=self.interview_id, turn_number=self._turn_number)
        # NOTE on honesty: this mark fires when llm_node is invoked,
        # which is AFTER LiveKit's own STT has already produced a
        # transcript — our code cannot observe "student finished
        # speaking" or "STT complete" as separate moments, since both
        # happen upstream of this hook. Labeled accurately as
        # "transcript_received", not mislabeled to imply precision we
        # don't have. Real STT-stage timing requires LiveKit's own
        # session-level metrics (MetricsCollectedEvent), not yet wired
        # up here — a real, stated gap, not a silent omission.
        timer.mark("transcript_received")

        # Step 1: if a question is pending, this transcript is the
        # answer to it. Record it in Conversation Memory FIRST — the
        # Evaluation Engine looks up the turn's answer_text via
        # Conversation Memory internally (for Evidence Graph's
        # provenance check), so the answer must already be recorded
        # before evaluation runs, or every evidence excerpt will fail
        # the traceability check against an empty answer_text.
        if self._pending_question_id and latest_user_message:
            self._conversation_memory.record_answer(
                interview_id=self.interview_id,
                question_id=self._pending_question_id,
                answer_text=latest_user_message,
                answer_timestamp=_now_iso(),
            )
            if self._pending_turn_id is None:
                # Defensive guard: this should be unreachable if
                # record_answer (just above) succeeded, since that
                # implies a real turn exists for this question_id — but
                # trusting an Optional without a check is exactly the
                # class of bug caught repeatedly elsewhere in this
                # project (Module 8's Reasoning Engine, most notably).
                logger.error(
                    "pending_turn_id was None despite a pending question — "
                    "skipping evaluation for interview %s, question %s",
                    self.interview_id,
                    self._pending_question_id,
                )
                return
            evaluation_result = self._evaluation_engine.evaluate_answer(
                interview_id=self.interview_id,
                question_id=self._pending_question_id,
                turn_id=self._pending_turn_id,
                evidence_missing=self._pending_evidence_missing or "",
                answer_text=latest_user_message,
                target_competency_id=self._pending_target_competency_id,
            )
            timer.mark("evaluation_complete")
            # CRITICAL STEP, easy to miss: Evaluation Engine deliberately
            # does NOT update competency-level confidence itself (see
            # Evaluation_Engine_Contract.md's Explicit Scope Resolution
            # — that's Competency Model's job). The caller (this
            # orchestrator) must feed the result through explicitly.
            # Skipped for turns with no target competency (e.g. greetings).
            if self._pending_target_competency_id:
                self._competency_model.update_from_evaluation(
                    interview_id=self.interview_id,
                    competency_id=self._pending_target_competency_id,
                    confidence_contribution=evaluation_result.confidence_contribution,
                    contradiction_detected=evaluation_result.contradiction_detected,
                    evidence_ids_created=evaluation_result.evidence_ids_created,
                )
                timer.mark("competency_updated")

        # Step 2: ask the UNCHANGED Reasoning Engine what happens next.
        decision = self._reasoning_engine.decide_next_action(self.interview_id)
        timer.mark("reasoning_complete")

        if decision.decision_type == "stop":
            timer.mark("stop_decision_ready")
            timer.log_summary()
            yield decision.stop_reason or "Thank you, that concludes the interview."
            return

        # Step 3: ask the UNCHANGED Question Generator for real question text.
        generated = self._question_generator.generate_question(
            self.interview_id, decision
        )
        timer.mark("question_generated")

        # Track what we're waiting for, so the NEXT llm_node call
        # (after the student answers) knows what to evaluate.
        self._pending_question_id = generated.question_id
        self._pending_target_competency_id = generated.target_competency_id
        self._pending_evidence_missing = decision.evidence_missing
        # turn_id comes from Conversation Memory's own record of this
        # question, since Question Generator already called record_turn().
        turn = self._conversation_memory.get_history(self.interview_id)
        self._pending_turn_id = turn[-1].turn_id if turn else None

        # NOTE on honesty: this is the last point our code observes.
        # From here, LiveKit takes the yielded text, runs TTS, and
        # plays audio — none of that is visible to this hook. "AI
        # speaking" (per the requested log format) would need to be
        # captured via LiveKit's own TTS/playback events, not this
        # override. Logging what we can honestly measure now, rather
        # than estimating or faking the remaining stages.
        timer.mark("text_ready_for_tts")
        timer.log_summary()

        yield generated.question_text

    @staticmethod
    def _extract_latest_user_text(chat_ctx: llm.ChatContext) -> Optional[str]:
        """Pulls the most recent user-role message's text out of the
        LiveKit chat context (populated by the STT stage upstream)."""
        for item in reversed(chat_ctx.items):
            if getattr(item, "role", None) == "user":
                text = getattr(item, "text_content", None)
                if text:
                    return text
        return None


def _now_iso() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()


async def entrypoint(ctx: JobContext):
    """
    LiveKit worker entrypoint — one of these runs per interview
    session (per "Job", in LiveKit's terms). Real interview_id must be
    passed via the room name or job metadata; placeholder shown here.
    """
    await ctx.connect()

    interview_id = ctx.room.name  # convention: room name == interview_id

    # Wire the SAME engine services the text interface uses. In
    # production these would be constructed with real (e.g.
    # Postgres-backed) stores, not the in-memory ones used in tests —
    # that swap is exactly what the storage abstractions built in
    # Modules 3/4/5/7 were designed for.
    conversation_memory = ConversationMemoryService()
    evidence_graph = EvidenceGraphService(conversation_memory=conversation_memory)
    logging_service = LoggingService()
    competency_model = CompetencyModelService()
    evaluation_engine = EvaluationEngineService(
        evidence_graph=evidence_graph, logging_service=logging_service
    )
    reasoning_engine = ReasoningEngineService(
        competency_model=competency_model,
        evidence_graph=evidence_graph,
        logging_service=logging_service,
    )
    question_generator = QuestionGeneratorService(
        evidence_graph=evidence_graph, conversation_memory=conversation_memory
    )

    agent = InterviewVoiceAgent(
        interview_id=interview_id,
        conversation_memory=conversation_memory,
        evidence_graph=evidence_graph,
        logging_service=logging_service,
        competency_model=competency_model,
        evaluation_engine=evaluation_engine,
        reasoning_engine=reasoning_engine,
        question_generator=question_generator,
    )

    session: AgentSession = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        tts=elevenlabs.TTS(),
        vad=silero.VAD.load(),
        # turn_detection left as LiveKit's default semantic model
        # (MultilingualModel) rather than raw silence-based VAD only —
        # per Decision #004, we don't build our own turn detection.
    )

    await session.start(agent=agent, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
