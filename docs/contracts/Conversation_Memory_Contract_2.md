# Module Contract — Conversation Memory

**Status:** Draft — pending review before implementation
**Milestone:** 3, Module 3 of 10 (see Milestone_2_Architecture.md Section 11)

**Note on module nature:** unlike Resume/JD Understanding, this module
is not an LLM-based extractor — it's a stateful record-keeper. No
`ProviderAdapter` usage, no provenance/fabrication concerns in the
same sense (there's nothing to fabricate; it stores what actually
happened). The lessons still carried forward: explicit Error Contract,
no placeholder values, CI-testable Acceptance Criteria.

**Enforceable constraint:** Conversation Memory must be deterministic.
No LLMs, embeddings, semantic search, or provider calls are permitted
anywhere in this module. This reinforces the storage/reasoning
boundary described below and makes scope creep easy to catch in
review — any PR touching this module that imports `ProviderAdapter` or
any embedding/similarity library is an automatic contract violation.

---

## Purpose

Maintain the full, ordered, turn-by-turn record of a single
interview — every question asked and every answer given — so that
other modules (Question Generator, Evidence Graph, Evaluation Engine,
Feedback Generator, and eventually the Reasoning Engine) can read
interview context without each maintaining their own copy of history.
Per Milestone 2 Architecture Section 2.7: "nearly every module reads
this."

This module is the single source of truth for "what has been asked
and answered so far in this interview." No other module should keep
its own parallel copy of conversation history.

## Inputs

### `record_turn(...)`
| Field | Type | Required | Notes |
|---|---|---|---|
| interview_id | string | Yes | |
| question_id | string | Yes | Caller-supplied unique ID for this question |
| question_text | string | Yes | |
| target_competency_id | string | No | May be null for non-competency-targeted turns (e.g. greeting) |
| question_type | enum | Yes | `fresh` \| `cross_question` — per Architecture Section 2.6's distinction |
| answer_text | string | No | Null until the candidate has actually answered (see Turn Lifecycle) |
| timestamp | ISO 8601 string | Yes | When the question was asked |

### `record_answer(...)`
| Field | Type | Required | Notes |
|---|---|---|---|
| interview_id | string | Yes | |
| question_id | string | Yes | Must match a previously recorded question |
| answer_text | string | Yes | |
| answer_timestamp | ISO 8601 string | Yes | |

### `get_history(interview_id)`
Returns the full ordered turn list for an interview.

### `get_turns_by_competency(interview_id, competency_id)`
Returns only turns targeting a specific competency — used by Question
Generator/Reasoning Engine to check what's already been asked about a
given competency before deciding to probe further.

### `has_asked_similar(interview_id, question_text, threshold=DEFAULT_SIMILARITY_THRESHOLD)`
Returns whether a highly similar question has already been asked in
this interview — supports the "avoid repetition" responsibility named
in the architecture. See Non-Responsibilities for what "similar" does
and does not mean here. **Threshold ownership:** `threshold` has a
module-level default (a configurable constant, not hardcoded inline —
same "implementation configuration" approach used elsewhere in this
project) so callers get consistent behavior without needing to know or
supply a value themselves. Callers may override it explicitly if they
have a specific reason to, but the default should cover normal use.

## Output — Turn Record Schema

```json
{
  "turn_id": string,
  "interview_id": string,
  "question_id": string,
  "sequence_number": integer,
  "question_text": string,
  "question_type": "fresh" | "cross_question",
  "target_competency_id": string | null,
  "question_timestamp": string,
  "answer_text": string | null,
  "answer_timestamp": string | null,
  "status": "asked" | "answered"
}
```

`turn_id` is an internally-generated, immutable identity for the
stored record itself — distinct from `question_id` (which is
caller-supplied and semantically tied to "which question"). Not
exposed as a required part of any public method signature in v0.1, but
generated and stored on every record, so future modules (Logging,
Evidence Graph) have a stable reference to attach annotations to
without relying on `question_id` alone. `question_id` remains the
primary lookup key for `record_answer()` and related operations.

### Turn Lifecycle

A turn is created via `record_turn()` in `status: "asked"` with
`answer_text: null`. It transitions to `status: "answered"` only via a
subsequent `record_answer()` call for the same `question_id`. This
two-step lifecycle exists because the Reasoning Engine generates and
logs a question (and its reasoning trace) before the candidate has
responded — the record must be queryable in that in-between state too,
not only once complete.

**Immutability rule:** `record_answer()` may only modify
`answer_text`, `answer_timestamp`, and `status`. Every other field on
the turn record — `question_text`, `target_competency_id`,
`question_type`, `question_timestamp`, `turn_id`, `sequence_number` —
is immutable once written by `record_turn()` and must never be
altered by any later call. This prevents accidental rewriting of the
historical record under the guise of "answering" it.

`sequence_number` is assigned by this module itself (auto-incrementing
per interview_id), not supplied by the caller. **Ordering guarantee:**
`sequence_number` is monotonic within an interview and, once assigned,
never changes for the lifetime of that turn record — this holds
regardless of the order `timestamp` values arrive in, and regardless
of concurrent write attempts. **Concurrency:** simultaneous writes to
the same `interview_id` must preserve this ordering guarantee; the
implementation is responsible for ensuring this (e.g. via a database
transaction, a per-interview lock, or an atomic increment), even
though v0.1 does not need to solve general distributed-locking
concerns.

## Error Contract

| Code | Meaning | Behavior |
|---|---|---|
| `DUPLICATE_QUESTION_ID` | `record_turn()` called with a `question_id` already used in this interview | Reject — raise, do not silently overwrite |
| `ANSWER_WITHOUT_QUESTION` | `record_answer()` called with a `question_id` that has no matching prior `record_turn()` call | Reject — raise |
| `ALREADY_ANSWERED` | `record_answer()` called twice for the same `question_id` | Reject — raise. Turns are immutable once answered; no silent overwrite |
| `INTERVIEW_NOT_FOUND` | `get_history()` / `get_turns_by_competency()` called for an `interview_id` with no recorded turns | Return an empty list, not an error — an interview with zero turns so far is a valid, expected state (e.g. right after creation), not a failure |

All four codes above are rejections for the write operations
(`record_turn`, `record_answer`) — this module does not silently
tolerate malformed call sequences, since correctness of "what actually
happened" is its entire purpose. Read operations degrade gracefully
(empty list) rather than erroring on an interview with no history yet.

## Responsibilities

- Persist the ordered turn history for each interview.
- Enforce turn lifecycle integrity (no duplicate question IDs, no
  answering a question that wasn't asked, no double-answering).
- Provide competency-filtered history lookups.
- Provide a repetition check (`has_asked_similar`) for the specific,
  narrow purpose of avoiding literal or near-literal repeated
  questions.
- Assign reliable sequence ordering, independent of timestamp
  precision or arrival order.

## Explicit Non-Responsibilities

- Does not decide what question to ask next (Reasoning Engine's job).
- Does not evaluate answer quality or extract evidence (Evaluation
  Engine's job) — `answer_text` is stored verbatim, uninterpreted.
- Does not track competency confidence (Competency Model's job).
- **`has_asked_similar` is a narrow literal/near-literal check (e.g.
  normalized string comparison or a simple similarity threshold), not
  a semantic "have we covered this topic" judgment.** Determining
  whether two differently-worded questions probe the same underlying
  gap is a reasoning-level judgment, not something this module decides
  — it belongs to the Reasoning Engine, which has access to competency
  and evidence context this module deliberately does not.
- Does not persist across interviews — each `interview_id`'s history
  is independent; this module has no concept of a candidate's history
  across multiple separate interview sessions.
- Does not generate the reasoning trace/log entry (Logging module's
  job, per Architecture Section 6) — Conversation Memory stores the
  question/answer pair; the *reasoning* behind why that question was
  asked is a separate record owned by Logging, cross-referenced by
  `question_id`, not duplicated here.

## Implementation Constraint — Storage Abstraction

The implementation must define a small internal `ConversationMemoryStore`
abstraction (interface/protocol) rather than having the rest of the
engine depend directly on an in-memory list or a specific database
client. The public API (`record_turn`, `record_answer`, `get_history`,
etc.) should be implemented against this abstraction, so the storage
backend can change later (e.g. moving from an in-memory store during
early development to Postgres/Supabase for the pilot) without
rewriting call sites elsewhere in the engine. This is an
implementation-level requirement, not a schema change — it does not
alter any of the public method signatures above.

## Deferred (not in v0.1, noted so it isn't lost)

`get_recent_turns(interview_id, limit)` — a bounded retrieval for
prompt construction, so downstream modules (e.g. Question Generator)
don't have to fetch and re-filter the entire interview history every
time they need recent context. Not needed yet at this module's current
scale, but worth keeping in mind so the storage abstraction above
doesn't accidentally make this awkward to add later.

## Acceptance Criteria

1. `record_turn()` followed by `get_history()` returns the turn with
   `status: "asked"`, `answer_text: null`, and a non-null, unique
   `turn_id`.
2. `record_answer()` on an existing question_id transitions that
   turn's status to `"answered"` and populates `answer_text` —
   verified by `get_history()` returning the updated record.
3. `sequence_number` is monotonic and correctly ordered regardless of
   the order `timestamp` values arrive in (test: submit two turns with
   out-of-order or identical timestamps, confirm sequence_number still
   reflects call order), and does not change after assignment.
4. `record_turn()` with a duplicate `question_id` raises
   `DUPLICATE_QUESTION_ID` and does not modify the existing record.
5. `record_answer()` for a nonexistent `question_id` raises
   `ANSWER_WITHOUT_QUESTION`.
6. `record_answer()` called twice for the same `question_id` raises
   `ALREADY_ANSWERED` on the second call; the first answer is
   unchanged.
7. `get_history()` for an interview with no recorded turns returns an
   empty list, not an error.
8. `get_turns_by_competency()` correctly filters — a turn with a
   different `target_competency_id` is excluded.
9. `has_asked_similar()` correctly identifies a near-duplicate
   question (e.g. same question reworded with minor changes) and
   correctly does NOT flag two genuinely different questions about the
   same competency as similar — both directions tested, not just the
   positive case. Default threshold used when caller doesn't supply
   one.
10. Two different `interview_id`s never see each other's turns —
    tested explicitly, since cross-interview data leakage would be a
    serious correctness bug, not a minor one.
11. `record_answer()` cannot alter any field other than `answer_text`,
    `answer_timestamp`, and `status` — tested by attempting to change
    `question_text` or `target_competency_id` via the answer path and
    confirming the original values persist.

## Review Checklist (before merge)

- [ ] Schema matches this contract exactly, including `turn_id`
- [ ] All 4 Error Contract codes have test coverage
- [ ] Turn lifecycle (asked → answered) tested explicitly, including
      the in-between state
- [ ] Immutability rule tested — `record_answer()` cannot alter
      non-answer fields
- [ ] Sequence ordering tested against out-of-order timestamp input,
      including that sequence_number never changes post-assignment
- [ ] Interview isolation tested explicitly (AC10) — this is the one
      failure mode with real consequences if missed; treat as a merge
      blocker
- [ ] `has_asked_similar` tested for both false positives and false
      negatives, not just one direction; default threshold verified
- [ ] `ConversationMemoryStore` abstraction used — no direct
      list/database dependency leaked into call sites elsewhere in the
      engine
- [ ] No semantic/topic-level judgment logic leaked into this module
      from Reasoning Engine's territory
- [ ] No `ProviderAdapter`, LLM, or embedding/similarity library import
      anywhere in this module — deterministic only
