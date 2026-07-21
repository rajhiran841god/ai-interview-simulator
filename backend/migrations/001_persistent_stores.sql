-- Persistent storage for the Interview Intelligence Engine's stores.
-- Replaces InMemory* implementations so state is shared across
-- processes (needed because the voice agent worker and the FastAPI
-- backend are separate processes — this was the real bug found
-- during live voice testing: "No competencies initialized" even
-- though they'd just been initialized via a different process).
--
-- Per Decision Log #006: this changes ONLY the storage layer behind
-- each module's existing ABC interface. No reasoning logic, schema,
-- or prompt changes — every module's own code (ConversationMemory,
-- EvidenceGraph, Logging, CompetencyModel, ReasoningEngine, etc.)
-- is completely unchanged.
--
-- Design: one row per record, natural keys as real columns (for
-- lookups/filtering), full record as JSONB (matches each module's
-- Pydantic schema exactly, avoids a fragile column-per-field mapping).

CREATE TABLE IF NOT EXISTS interview_sessions (
    interview_id TEXT PRIMARY KEY,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversation_turns (
    turn_id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    sequence_number INT NOT NULL,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (interview_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_conversation_turns_interview ON conversation_turns (interview_id);

CREATE TABLE IF NOT EXISTS evidence_entries (
    evidence_id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    competency_id TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_evidence_interview_competency ON evidence_entries (interview_id, competency_id);
CREATE INDEX IF NOT EXISTS idx_evidence_interview_turn ON evidence_entries (interview_id, turn_id);

CREATE TABLE IF NOT EXISTS logging_traces (
    interview_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    sequence_number INT NOT NULL,
    competency_id TEXT,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (interview_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_traces_interview_competency ON logging_traces (interview_id, competency_id);

CREATE TABLE IF NOT EXISTS competency_states (
    interview_id TEXT NOT NULL,
    competency_id TEXT NOT NULL,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (interview_id, competency_id)
);
