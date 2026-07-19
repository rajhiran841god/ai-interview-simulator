"""
Tests mapped to Logging_Trace_Recorder_Contract.md's 14 Acceptance
Criteria. Deterministic module — no mocking of external providers
needed.
"""

import pytest

from app.engine.logging.service import LoggingService
from app.engine.logging.store import InMemoryTraceStore
from app.engine.logging.schema import LoggingError, ErrorCode


@pytest.fixture
def service():
    return LoggingService(InMemoryTraceStore())


def _record_sample_trace(
    service, interview_id="int-1", question_id="q-1", competency_id="leadership"
):
    return service.record_trace(
        interview_id=interview_id,
        question_id=question_id,
        decision_strategy="probe_deeper",
        confidence_pre=0.4,
        evidence_missing="No concrete example of conflict resolution",
        reason_for_asking="Candidate mentioned leading a team but gave no evidence of handling disagreement",
        prompt_version="v1.0.0",
        model_version="claude-sonnet-4-6",
        target_competency_id=competency_id,
    )


# AC1 — initial state
def test_ac1_record_trace_initial_state(service):
    trace = _record_sample_trace(service)
    assert trace.confidence_post is None
    assert trace.evidence_ids_referenced == []
    assert trace.trace_id is not None


# AC2 — update populates outcome fields
def test_ac2_update_trace_outcome_populates_fields(service):
    _record_sample_trace(service)
    updated = service.update_trace_outcome(
        "int-1", "q-1", confidence_post=0.75, evidence_ids_referenced=["ev-1", "ev-2"]
    )
    assert updated.confidence_post == 0.75
    assert updated.evidence_ids_referenced == ["ev-1", "ev-2"]

    fetched = service.get_trace("int-1", "q-1")
    assert fetched.confidence_post == 0.75


# AC3 — duplicate question_id rejected
def test_ac3_duplicate_question_id_rejected(service):
    _record_sample_trace(service)
    with pytest.raises(LoggingError) as exc_info:
        _record_sample_trace(service)
    assert exc_info.value.code == ErrorCode.DUPLICATE_QUESTION_ID


# AC4 — update on nonexistent trace rejected
def test_ac4_update_nonexistent_trace_rejected(service):
    with pytest.raises(LoggingError) as exc_info:
        service.update_trace_outcome("int-1", "nonexistent-q", 0.5, [])
    assert exc_info.value.code == ErrorCode.TRACE_NOT_FOUND


# AC5 — double outcome update rejected, first preserved
def test_ac5_outcome_already_recorded_rejected(service):
    _record_sample_trace(service)
    service.update_trace_outcome("int-1", "q-1", 0.75, ["ev-1"])
    with pytest.raises(LoggingError) as exc_info:
        service.update_trace_outcome("int-1", "q-1", 0.90, ["ev-2"])
    assert exc_info.value.code == ErrorCode.OUTCOME_ALREADY_RECORDED

    fetched = service.get_trace("int-1", "q-1")
    assert fetched.confidence_post == 0.75  # unchanged


# AC6 — update_trace_outcome cannot alter non-outcome fields
def test_ac6_update_cannot_alter_immutable_fields(service):
    original = _record_sample_trace(service)
    updated = service.update_trace_outcome("int-1", "q-1", 0.75, ["ev-1"])

    assert updated.decision_strategy == original.decision_strategy
    assert updated.confidence_pre == original.confidence_pre
    assert updated.evidence_missing == original.evidence_missing
    assert updated.reason_for_asking == original.reason_for_asking
    assert updated.trace_id == original.trace_id
    assert updated.sequence_number == original.sequence_number
    assert updated.target_competency_id == original.target_competency_id


# AC7 — empty interview returns empty list
def test_ac7_empty_interview_returns_empty_list(service):
    assert service.get_traces_for_interview("nonexistent-interview") == []


# AC8 — competency filtering
def test_ac8_get_traces_for_competency_filters(service):
    _record_sample_trace(service, question_id="q-1", competency_id="leadership")
    service.record_trace(
        "int-1",
        "q-2",
        "probe_deeper",
        0.5,
        "gap",
        "reason",
        "v1",
        "model",
        target_competency_id="problem_solving",
    )
    leadership_traces = service.get_traces_for_competency("int-1", "leadership")
    assert len(leadership_traces) == 1
    assert leadership_traces[0].question_id == "q-1"


# AC9 — interview isolation (merge blocker per review)
def test_ac9_interview_isolation(service):
    _record_sample_trace(service, interview_id="int-1", question_id="q-1")
    _record_sample_trace(service, interview_id="int-2", question_id="q-1")

    traces_1 = service.get_traces_for_interview("int-1")
    traces_2 = service.get_traces_for_interview("int-2")
    assert len(traces_1) == 1
    assert len(traces_2) == 1
    assert traces_1[0].interview_id == "int-1"
    assert traces_2[0].interview_id == "int-2"


# AC10 — sequence_number monotonic, immutable after assignment
def test_ac10_sequence_number_monotonic_and_immutable(service):
    t1 = _record_sample_trace(service, question_id="q-1")
    t2 = service.record_trace(
        "int-1", "q-2", "verify", 0.6, "gap", "reason", "v1", "model"
    )
    assert t1.sequence_number == 1
    assert t2.sequence_number == 2

    updated = service.update_trace_outcome("int-1", "q-1", 0.8, [])
    assert updated.sequence_number == t1.sequence_number


# AC11 — no full conversation/evidence content duplicated (structural check)
def test_ac11_no_full_content_duplicated():
    from app.engine.logging.schema import TraceRecord

    fields = set(TraceRecord.model_fields.keys())
    forbidden = {"question_text", "answer_text", "evidence_excerpt", "full_answer"}
    assert forbidden.isdisjoint(fields)


# AC12 — confidence_pre out of range rejected, both directions
def test_ac12_confidence_pre_above_range_rejected(service):
    with pytest.raises(LoggingError) as exc_info:
        service.record_trace(
            "int-1", "q-1", "probe_deeper", 1.7, "gap", "reason", "v1", "model"
        )
    assert exc_info.value.code == ErrorCode.CONFIDENCE_OUT_OF_RANGE


def test_ac12_confidence_pre_below_range_rejected(service):
    with pytest.raises(LoggingError) as exc_info:
        service.record_trace(
            "int-1", "q-1", "probe_deeper", -0.2, "gap", "reason", "v1", "model"
        )
    assert exc_info.value.code == ErrorCode.CONFIDENCE_OUT_OF_RANGE


# AC13 — same boundary check on the update path
def test_ac13_confidence_post_out_of_range_rejected(service):
    _record_sample_trace(service)
    with pytest.raises(LoggingError) as exc_info:
        service.update_trace_outcome(
            "int-1", "q-1", confidence_post=1.5, evidence_ids_referenced=[]
        )
    assert exc_info.value.code == ErrorCode.CONFIDENCE_OUT_OF_RANGE


# AC14 — contract_version populated automatically
def test_ac14_contract_version_populated(service):
    trace = _record_sample_trace(service)
    assert trace.contract_version == "v1"
    assert trace.contract_version is not None


# ============================================================
# Full lifecycle integration test — per reviewer's explicit request to
# test record_trace() -> update_trace_outcome() together, not just
# each function independently, since that's the seam where Module 6
# (Evaluation Engine) will eventually write.
# ============================================================
def test_full_lifecycle_record_then_update(service):
    # Simulates the Reasoning Engine asking a question...
    trace = service.record_trace(
        interview_id="int-1",
        question_id="q-1",
        decision_strategy="probe_deeper",
        confidence_pre=0.35,
        evidence_missing="No evidence of how conflict was actually resolved",
        reason_for_asking="Leadership claim lacks supporting detail",
        prompt_version="v1.0.0",
        model_version="claude-sonnet-4-6",
        target_competency_id="leadership",
    )
    assert trace.confidence_post is None
    assert trace.decision_strategy == "probe_deeper"

    # ...candidate answers, Evaluation Engine (not yet built) would
    # eventually call this after extracting evidence...
    service.update_trace_outcome(
        interview_id="int-1",
        question_id="q-1",
        confidence_post=0.7,
        evidence_ids_referenced=["ev-101", "ev-102"],
    )

    # Full record, queried fresh, reflects both stages correctly:
    final = service.get_trace("int-1", "q-1")
    assert final.confidence_pre == 0.35
    assert final.confidence_post == 0.7
    assert final.evidence_ids_referenced == ["ev-101", "ev-102"]
    assert final.decision_strategy == "probe_deeper"  # untouched by the update
    assert final.trace_id == trace.trace_id  # same record, not a new one


# Determinism check
def test_determinism_no_provider_imports():
    import inspect
    import app.engine.logging.service as svc_module
    import app.engine.logging.store as store_module

    for module in (svc_module, store_module):
        source = inspect.getsource(module)
        import_lines = [
            line.strip().lower()
            for line in source.splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        for line in import_lines:
            for forbidden in ("provider_adapter", "import anthropic", "embedding"):
                assert forbidden not in line, f"Forbidden import: '{line}'"


# Shared type usage check (Decision #003)
def test_uses_shared_decision_strategy_type():
    from app.engine.logging.schema import TraceRecord
    from app.shared.types import DecisionStrategy

    field_info = TraceRecord.model_fields["decision_strategy"]
    # Confirms this field's type actually comes from the shared module,
    # not a locally redefined Literal — the exact pattern Decision #003
    # was written to prevent going forward.
    assert field_info.annotation == DecisionStrategy
