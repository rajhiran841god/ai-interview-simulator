"""
Tests for the interview orchestration API (Phase 1 backend). These are
the FIRST tests in the project that exercise the engine through real
HTTP requests, via FastAPI's TestClient, rather than calling services
directly in Python. Only LLM calls are mocked.
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.interviews import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


FAKE_JD_RESPONSE = {
    "role_title": {
        "value": "Marketing Associate",
        "source_text": "Marketing Associate role",
    },
    "seniority_level": None,
    "required_competencies": [
        {
            "competency_name": "Consumer Insight",
            "emphasis": "primary",
            "source_text": "consumer insight skills required",
        },
    ],
    "role_specific_signals": [],
}

JD_TEXT = (
    "Marketing Associate role. We need someone with strong "
    "consumer insight skills required for this position, plus general "
    "marketing experience and a collaborative mindset for the team."
)


def test_create_session_returns_valid_session(client):
    r = client.post("/api/interviews", params={"user_id": "user-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "created"
    assert len(body["interview_id"]) > 0


def test_get_nonexistent_session_returns_404(client):
    r = client.get("/api/interviews/nonexistent-id")
    assert r.status_code == 404


def test_jd_upload_initializes_competencies(client):
    r = client.post("/api/interviews", params={"user_id": "user-1"})
    interview_id = r.json()["interview_id"]

    with patch(
        "app.engine.jd.service.structure_jd_text", return_value=FAKE_JD_RESPONSE
    ):
        r = client.post(f"/api/interviews/{interview_id}/jd", data={"jd_text": JD_TEXT})

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert "consumer_insight" in body["competencies_initialized"]


def test_next_question_before_jd_upload_rejected(client):
    r = client.post("/api/interviews", params={"user_id": "user-1"})
    interview_id = r.json()["interview_id"]

    r = client.post(f"/api/interviews/{interview_id}/next-question")
    assert r.status_code == 400


def test_full_interview_loop_end_to_end(client):
    """The core smoke test: create -> JD -> question -> answer -> report,
    entirely through real HTTP calls into the real engine."""
    r = client.post("/api/interviews", params={"user_id": "user-1"})
    interview_id = r.json()["interview_id"]

    with patch(
        "app.engine.jd.service.structure_jd_text", return_value=FAKE_JD_RESPONSE
    ):
        r = client.post(f"/api/interviews/{interview_id}/jd", data={"jd_text": JD_TEXT})
    assert r.status_code == 200

    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="Tell me about a time you used consumer insight.",
    ):
        r = client.post(f"/api/interviews/{interview_id}/next-question")
    assert r.status_code == 200
    question = r.json()
    assert question["decision_type"] == "continue"
    assert len(question["question_text"]) > 0
    question_id = question["question_id"]

    fake_eval = {
        "answer_classification": "substantive",
        "evidence_excerpts": ["I analyzed customer surveys"],
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 0.75,
        "reasoning_summary": "Good.",
    }
    with patch("app.engine.evaluation.service.classify_answer", return_value=fake_eval):
        r = client.post(
            f"/api/interviews/{interview_id}/answer",
            json={
                "question_id": question_id,
                "answer_text": "I analyzed customer surveys to find insights.",
            },
        )
    assert r.status_code == 200
    assert r.json()["accepted"] is True
    assert r.json()["answer_classification"] == "substantive"

    with patch(
        "app.engine.feedback.service.call_feedback_generation",
        return_value={
            "summary_text": "Strong evidence of consumer insight skills.",
            "cited_evidence_ids": [],
        },
    ):
        r = client.get(f"/api/interviews/{interview_id}/report")
    assert r.status_code == 200
    report = r.json()
    assert len(report["competency_feedback"]) == 1
    assert report["competency_feedback"][0]["competency_id"] == "consumer_insight"
    # AC1's discipline carries through the API layer too: no confidence number anywhere
    assert "confidence" not in str(report).lower().replace("consumer", "")


def test_answer_to_unknown_question_returns_404(client):
    r = client.post("/api/interviews", params={"user_id": "user-1"})
    interview_id = r.json()["interview_id"]
    with patch(
        "app.engine.jd.service.structure_jd_text", return_value=FAKE_JD_RESPONSE
    ):
        client.post(f"/api/interviews/{interview_id}/jd", data={"jd_text": JD_TEXT})

    r = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={"question_id": "fake-question-id", "answer_text": "test"},
    )
    assert r.status_code == 404


def test_concurrent_next_question_requests_are_rejected_with_409(client):
    """Regression test for the two-tab race condition flagged during
    review: a second concurrent request for the same interview_id
    while one is already processing must be rejected (409), not
    silently allowed to generate duplicate state."""
    from app.orchestrator import concurrency_guard

    r = client.post("/api/interviews", params={"user_id": "user-1"})
    interview_id = r.json()["interview_id"]

    with patch(
        "app.engine.jd.service.structure_jd_text", return_value=FAKE_JD_RESPONSE
    ):
        client.post(f"/api/interviews/{interview_id}/jd", data={"jd_text": JD_TEXT})

    # Simulate "already processing" by manually holding the guard,
    # exactly as a real concurrent request would.
    with concurrency_guard.guard(interview_id):
        with patch(
            "app.engine.question_generator.service.call_generation",
            return_value="Should not be reached.",
        ):
            r = client.post(f"/api/interviews/{interview_id}/next-question")

    assert r.status_code == 409
    assert "already processing" in r.json()["detail"].lower()


def test_guard_releases_after_request_completes_allowing_next_call(client):
    """The guard must not permanently wedge an interview — after one
    request completes, the next one must succeed normally."""
    r = client.post("/api/interviews", params={"user_id": "user-1"})
    interview_id = r.json()["interview_id"]

    with patch(
        "app.engine.jd.service.structure_jd_text", return_value=FAKE_JD_RESPONSE
    ):
        client.post(f"/api/interviews/{interview_id}/jd", data={"jd_text": JD_TEXT})

    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="First question.",
    ):
        r1 = client.post(f"/api/interviews/{interview_id}/next-question")
    assert r1.status_code == 200

    # Guard should be released now — a second, sequential call must succeed, not 409.
    from app.orchestrator import concurrency_guard

    assert interview_id not in concurrency_guard._processing


def test_guard_releases_even_if_the_wrapped_call_raises(client):
    """The guard uses a finally block specifically so a failed request
    can't leave an interview permanently locked."""
    from app.orchestrator import concurrency_guard

    interview_id = "test-error-release"
    try:
        with concurrency_guard.guard(interview_id):
            raise ValueError("simulated failure inside the guarded block")
    except ValueError:
        pass

    assert interview_id not in concurrency_guard._processing


def test_evidence_detail_endpoint_joins_evidence_with_question_number(client):
    """Decision Log #006 — presentation-layer endpoint, zero engine
    modification. Exposes real Evidence Graph data joined with
    Conversation Memory's sequence number, for the frontend's
    evidence-footnote interaction."""
    r = client.post("/api/interviews", params={"user_id": "user-1"})
    interview_id = r.json()["interview_id"]

    with patch(
        "app.engine.jd.service.structure_jd_text", return_value=FAKE_JD_RESPONSE
    ):
        client.post(f"/api/interviews/{interview_id}/jd", data={"jd_text": JD_TEXT})

    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="Tell me about consumer insight.",
    ):
        q = client.post(f"/api/interviews/{interview_id}/next-question").json()

    fake_eval = {
        "answer_classification": "substantive",
        "evidence_excerpts": ["I analyzed customer surveys"],
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 0.75,
        "reasoning_summary": "Good.",
    }
    with patch("app.engine.evaluation.service.classify_answer", return_value=fake_eval):
        client.post(
            f"/api/interviews/{interview_id}/answer",
            json={
                "question_id": q["question_id"],
                "answer_text": "I analyzed customer surveys.",
            },
        )

    r = client.get(f"/api/interviews/{interview_id}/evidence/consumer_insight")
    assert r.status_code == 200
    evidence = r.json()
    assert len(evidence) == 1
    assert evidence[0]["evidence_excerpt"] == "I analyzed customer surveys"
    assert evidence[0]["relation"] == "supports"
    assert evidence[0]["question_number"] == 1


def test_evidence_detail_endpoint_unknown_session_returns_404(client):
    r = client.get("/api/interviews/nonexistent-id/evidence/leadership")
    assert r.status_code == 404


def test_voice_token_endpoint_returns_valid_scoped_token(client, monkeypatch):
    """Decision Log #006 — presentation/infrastructure endpoint, zero
    engine modification. Generates a real, valid LiveKit access token
    scoped to the interview's room, matching app/voice/agent.py's
    existing room_name == interview_id convention."""
    monkeypatch.setattr(
        "app.api.interviews.settings.LIVEKIT_URL", "wss://test.livekit.cloud"
    )
    monkeypatch.setattr("app.api.interviews.settings.LIVEKIT_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.api.interviews.settings.LIVEKIT_API_SECRET",
        "test-secret-long-enough-for-jwt-signing",
    )

    r = client.post("/api/interviews", params={"user_id": "voice-user"})
    interview_id = r.json()["interview_id"]

    r = client.post(f"/api/interviews/{interview_id}/voice-token")
    assert r.status_code == 200
    body = r.json()
    assert body["livekit_url"] == "wss://test.livekit.cloud"
    assert body["room_name"] == interview_id
    assert len(body["token"]) > 0

    # Decode the JWT payload (no signature verification needed here —
    # this test checks OUR code constructed the right claims, not that
    # the JWT library itself works) to confirm room scoping is correct.
    import base64
    import json as json_module

    payload_b64 = body["token"].split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json_module.loads(base64.urlsafe_b64decode(payload_b64))
    assert payload["video"]["room"] == interview_id
    assert payload["video"]["roomJoin"] is True


def test_voice_token_endpoint_without_config_returns_503(client, monkeypatch):
    monkeypatch.setattr("app.api.interviews.settings.LIVEKIT_URL", "")
    monkeypatch.setattr("app.api.interviews.settings.LIVEKIT_API_KEY", "")
    monkeypatch.setattr("app.api.interviews.settings.LIVEKIT_API_SECRET", "")

    r = client.post("/api/interviews", params={"user_id": "voice-user"})
    interview_id = r.json()["interview_id"]

    r = client.post(f"/api/interviews/{interview_id}/voice-token")
    assert r.status_code == 503


def test_voice_token_endpoint_unknown_session_returns_404(client):
    r = client.post("/api/interviews/nonexistent-id/voice-token")
    assert r.status_code == 404
