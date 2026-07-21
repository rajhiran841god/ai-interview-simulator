"""
Interview session API — Phase 1 backend, per the product spec's own
phased plan. This is the orchestration layer connecting Resume
Understanding, JD Understanding, and the rest of the engine
(via app/orchestrator/engine_singletons.py) into an actual usable
HTTP flow: create session -> upload resume -> upload JD -> loop
(get question / submit answer) -> get report.

No Claude API calls happen here directly — every LLM call already
lives inside the engine modules themselves (Resume/JD Understanding,
Evaluation Engine, Question Generator, Feedback Generator). This file
only orchestrates calls into them.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.orchestrator import session_store, concurrency_guard
from app.orchestrator.engine_singletons import (
    competency_model,
    reasoning_engine,
    question_generator,
    evaluation_engine,
    feedback_generator,
)
from app.orchestrator.schema import (
    SessionResponse,
    NextQuestionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    EvidenceDetail,
)
from app.engine.resume.service import understand_resume
from app.engine.resume.schema import RejectionError as ResumeRejectionError
from app.engine.jd.service import understand_jd
from app.engine.competency_model.schema import CompetencySeed
from app.engine.reasoning.schema import ReasoningDecision
from app.engine.question_generator.schema import QuestionGeneratorError

router = APIRouter()


# NOTE: real user auth (via Supabase, per app/api/auth.py) should
# populate user_id from the authenticated request in production. Kept
# as an explicit query param here since wiring auth-context extraction
# into every route is a separate, orthogonal piece of work — not
# silently guessed at or skipped without saying so.
@router.post("/interviews", response_model=SessionResponse)
def create_interview(user_id: str):
    session = session_store.create_session(user_id=user_id)
    return SessionResponse(
        interview_id=session.interview_id,
        status=session.status,
        created_at=session.created_at,
    )


@router.get("/interviews/{interview_id}", response_model=SessionResponse)
def get_interview(interview_id: str):
    session = session_store.get_session(interview_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    return SessionResponse(
        interview_id=session.interview_id,
        status=session.status,
        created_at=session.created_at,
    )


@router.post("/interviews/{interview_id}/resume")
def upload_resume(interview_id: str, file: UploadFile = File(...)):
    session = session_store.get_session(interview_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    file_bytes = file.file.read()
    file_format = "pdf" if (file.filename or "").lower().endswith(".pdf") else "docx"

    try:
        result = understand_resume(file_bytes, file_format)
    except ResumeRejectionError as e:
        raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}")

    session_store.update_session(
        interview_id, resume_summary=result.model_dump(), status="resume_uploaded"
    )
    return {"status": "resume_uploaded", "parse_warnings": result.parse_warnings}


@router.post("/interviews/{interview_id}/jd")
def upload_jd(interview_id: str, jd_text: str = Form(...)):
    session = session_store.get_session(interview_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    result = understand_jd(jd_text)

    # This is the critical wiring step: JD Understanding's output
    # directly seeds Competency Model — the moment the engine actually
    # becomes usable for a real interview, not just individually
    # testable.
    seeds = [
        CompetencySeed(competency_id=c.competency_id, emphasis=c.emphasis)
        for c in result.required_competencies
    ]
    if seeds:
        competency_model.initialize_competencies(interview_id, seeds)

    session_store.update_session(
        interview_id,
        jd_summary=result.model_dump(),
        status="ready" if seeds else "jd_uploaded",
    )
    return {
        "status": "ready" if seeds else "jd_uploaded",
        "competencies_initialized": [s.competency_id for s in seeds],
        "parse_warnings": result.parse_warnings,
    }


@router.post(
    "/interviews/{interview_id}/next-question", response_model=NextQuestionResponse
)
def get_next_question(interview_id: str):
    session = session_store.get_session(interview_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    if session.status not in ("ready", "in_progress"):
        raise HTTPException(
            status_code=400,
            detail=f"Interview not ready for questions (status: {session.status}). Upload resume and JD first.",
        )

    with concurrency_guard.guard(interview_id):
        try:
            decision: ReasoningDecision = reasoning_engine.decide_next_action(
                interview_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Reasoning Engine error: {e}")

        if decision.decision_type == "stop":
            session_store.update_session(interview_id, status="completed")
            return NextQuestionResponse(
                decision_type="stop",
                question_id=decision.question_id,
                stop_reason=decision.stop_reason,
            )

        try:
            generated = question_generator.generate_question(interview_id, decision)
        except QuestionGeneratorError as e:
            raise HTTPException(status_code=500, detail=f"{e.code}: {e.message}")

        session_store.update_session(interview_id, status="in_progress")
        return NextQuestionResponse(
            decision_type="continue",
            question_id=generated.question_id,
            question_text=generated.question_text,
            target_competency_id=generated.target_competency_id,
        )


@router.post("/interviews/{interview_id}/answer", response_model=SubmitAnswerResponse)
def submit_answer(interview_id: str, payload: SubmitAnswerRequest):
    session = session_store.get_session(interview_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    from app.orchestrator.engine_singletons import conversation_memory

    with concurrency_guard.guard(interview_id):
        history = conversation_memory.get_history(interview_id)
        turn = next((t for t in history if t.question_id == payload.question_id), None)
        if turn is None:
            raise HTTPException(
                status_code=404, detail="Question not found for this interview."
            )

        conversation_memory.record_answer(
            interview_id=interview_id,
            question_id=payload.question_id,
            answer_text=payload.answer_text,
            answer_timestamp=_now_iso(),
        )

        trace = None
        try:
            trace = _get_trace(interview_id, payload.question_id)
        except Exception:
            pass

        evaluation_result = evaluation_engine.evaluate_answer(
            interview_id=interview_id,
            question_id=payload.question_id,
            turn_id=turn.turn_id,
            evidence_missing=trace.evidence_missing if trace else "",
            answer_text=payload.answer_text,
            target_competency_id=turn.target_competency_id,
        )

        if turn.target_competency_id:
            competency_model.update_from_evaluation(
                interview_id=interview_id,
                competency_id=turn.target_competency_id,
                confidence_contribution=evaluation_result.confidence_contribution,
                contradiction_detected=evaluation_result.contradiction_detected,
                evidence_ids_created=evaluation_result.evidence_ids_created,
            )

        return SubmitAnswerResponse(
            accepted=True, answer_classification=evaluation_result.answer_classification
        )


@router.get("/interviews/{interview_id}/report")
def get_report(interview_id: str):
    session = session_store.get_session(interview_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    try:
        report = feedback_generator.generate_feedback_report(interview_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feedback Generator error: {e}")

    return report.model_dump()


@router.get(
    "/interviews/{interview_id}/evidence/{competency_id}",
    response_model=list[EvidenceDetail],
)
def get_evidence_detail(interview_id: str, competency_id: str):
    """
    Presentation-layer endpoint (Decision Log #006) — exposes real
    Evidence Graph entries, joined with Conversation Memory's turn
    sequence numbers, for the frontend's evidence-footnote UI. Does
    not modify, call, or depend on Feedback Generator in any way —
    reads Evidence Graph and Conversation Memory directly, both
    already-existing, unchanged engine modules.
    """
    session = session_store.get_session(interview_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    from app.orchestrator.engine_singletons import evidence_graph, conversation_memory

    entries = evidence_graph.get_evidence_for_competency(interview_id, competency_id)
    history = conversation_memory.get_history(interview_id)
    sequence_by_turn_id = {t.turn_id: t.sequence_number for t in history}

    return [
        EvidenceDetail(
            evidence_id=e.evidence_id,
            evidence_excerpt=e.evidence_excerpt,
            relation=e.relation,
            question_number=sequence_by_turn_id.get(e.turn_id, 0),
        )
        for e in entries
    ]


def _get_trace(interview_id: str, question_id: str):
    from app.orchestrator.engine_singletons import logging_service

    return logging_service.get_trace(interview_id, question_id)


def _now_iso() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()
