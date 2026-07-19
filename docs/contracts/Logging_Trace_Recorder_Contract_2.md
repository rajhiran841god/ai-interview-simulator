# Module Contract — Logging / Trace Recorder

**Status:** Draft — pending review before implementation
**Milestone:** 3, Module 5 of 10 (see Milestone_2_Architecture.md Section 11)

**Note on module nature:** deterministic storage module, same category
as Conversation Memory and Evidence Graph. No `ProviderAdapter` usage.
**Explicit discipline carried forward per review guidance given before
this contract was written:**
- Records decisions; does not make them. This module has zero
  reasoning logic of its own — it is a passive recorder.
- References immutable IDs (`turn_id`, `evidence_id`, `competency_id`,
  `question_id`) wherever possible rather than duplicating state owned
  by other modules.
- Append-only by default. There is no update or delete operation in
  this contract's public API — a trace record, once written, is
  permanent for the lifetime of the interview.

---

## Purpose

Structural, queryable record of every reasoning step taken during an
interview — the mechanism that makes Adaptive Reasoning Transparency
(Architecture Review Gate #5) answerable by querying a record, not by
guessing. Per Milestone 2 Architecture Section 2.10: "every other
module writes to this as a side effect of doing its job, not as a
separate manual step" — meaning this module's write API needs to be
simple enough that Reasoning Engine and Evaluation Engine (Modules 6
and 8, not yet built) can call it naturally as part of their own work,
not as an afterthought bolted on later.

This module is built before its primary writers exist, same
relationship Conversation Memory and Evidence Graph had to their
eventual callers — its write API must be usable by future modules
without requiring changes here.

## Inputs

### `record_trace(...)`

Matches the schema defined in Milestone 2 Architecture Section 6
exactly — this contract does not redefine those fields, only formalizes
them into a module API:

| Field | Type | Required | Notes |
|---|---|---|---|
| interview_id | string | Yes | |
| question_id | string | Yes | References Conversation Memory's `question_id` — not duplicated data, a reference |
| target_competency_id | string | No | References JD Understanding's `competency_id`; null for non-competency-targeted turns (e.g. greeting) |
| decision_strategy | enum | Yes | `probe_deeper` \| `challenge_inconsistency` \| `verify` \| `switch_competency` \| `wrap_up_competency` — per Architecture Section 2.5 |
| confidence_pre | float | Yes | Confidence value before this question. **Must be within `[0.0, 1.0]`** — this module validates the value is within the documented domain (schema-level validation, not reasoning about what the value should be) and rejects anything outside that range |
| evidence_missing | string | Yes | Human-readable description of the gap this question targets |
| reason_for_asking | string | Yes | Human-readable justification |
| prompt_version | string | Yes | |
| model_version | string | Yes | |
| evidence_ids_referenced | list[string] | No | References into Evidence Graph — populated once evidence has been extracted from the answer; may be empty/null at question-time before an answer exists |
| confidence_post | float | No | Populated once the answer has been evaluated; null in the interim state, same two-step lifecycle pattern as Conversation Memory's `asked`/`answered`. **Must be within `[0.0, 1.0]` when present**, same domain validation as `confidence_pre` |

**Confidence domain validation, explicitly scoped:** this module
validates that `confidence_pre`/`confidence_post` fall within
`[0.0, 1.0]` — a storage-layer sanity check on the documented domain,
not an evaluation of whether the value is the *correct* confidence
for the situation. A value of `1.7` or `-0.2` is rejected because it's
outside the schema's defined range, the same category of check as
rejecting a malformed enum value — it does not require this module to
understand or judge the reasoning that produced the number. This does
not violate the "zero reasoning" non-responsibility below.

### `get_trace(interview_id, question_id)`
Single trace record lookup.

### `get_traces_for_interview(interview_id)`
Full ordered trace history for an interview.

### `get_traces_for_competency(interview_id, competency_id)`
Filtered by target competency — supports later analysis of "how did
reasoning behave for this specific competency."

## Output — Trace Record Schema

```json
{
  "trace_id": string,
  "interview_id": string,
  "question_id": string,
  "target_competency_id": string | null,
  "decision_strategy": "probe_deeper" | "challenge_inconsistency" | "verify" | "switch_competency" | "wrap_up_competency",
  "confidence_pre": number,
  "confidence_post": number | null,
  "evidence_missing": string,
  "reason_for_asking": string,
  "evidence_ids_referenced": [string],
  "prompt_version": string,
  "model_version": string,
  "sequence_number": integer,
  "created_at": string,
  "contract_version": string
}
```

`contract_version` is an internal-only field (not required in equality
checks against the public schema above the line) recording which
version of this contract produced the record — e.g. `"v1"`. Not
exposed as a required part of any public method signature, populated
automatically on every write. Not needed for anything today, but if
trace records ever need migration after a future contract revision,
versioned records make that tooling and debugging substantially
easier — same rationale as Conversation Memory's internal
`created_at`/`updated_at` fields.

`trace_id` is internally generated, same discipline as Evidence
Graph's `evidence_id` — never caller-supplied. `sequence_number` is
assigned by this module, ordering derived independently per interview
(not borrowed from Conversation Memory's sequence, since a trace can
in principle exist slightly out of lockstep with a conversation turn —
kept as its own monotonic counter for this module's own records,
consistent with the append-only, module-owns-its-own-ordering pattern
already established).

### Two-step lifecycle: pre-answer and post-answer trace state

A trace record can be created with only the pre-answer fields
(`confidence_pre`, `evidence_missing`, `reason_for_asking`, etc.)
populated, before the candidate has answered — this mirrors
Conversation Memory's `asked` → `answered` lifecycle. `confidence_post`
and `evidence_ids_referenced` are populated later via a distinct update
operation once the Evaluation Engine has processed the answer.

### `update_trace_outcome(interview_id, question_id, confidence_post, evidence_ids_referenced)`

The **one exception to strict append-only**, and it's narrow and
justified: this updates only `confidence_post` and
`evidence_ids_referenced` on an existing trace record — never any
other field. This is the same immutability-with-one-controlled-mutation
pattern Conversation Memory established for `record_answer()`. Every
other field, once written by `record_trace()`, is permanent.

## Error Contract

| Code | Meaning | Behavior |
|---|---|---|
| `DUPLICATE_QUESTION_ID` | `record_trace()` called with a `question_id` that already has a trace for this interview | Reject — raise |
| `TRACE_NOT_FOUND` | `update_trace_outcome()` called for a `question_id` with no existing trace | Reject — raise |
| `OUTCOME_ALREADY_RECORDED` | `update_trace_outcome()` called twice for the same `question_id` | Reject — raise. Same immutability discipline as Conversation Memory's `ALREADY_ANSWERED` |
| `CONFIDENCE_OUT_OF_RANGE` | `confidence_pre` or `confidence_post` falls outside `[0.0, 1.0]` | Reject — raise. Schema-domain validation, not reasoning evaluation |
| `INTERVIEW_NOT_FOUND` | `get_traces_for_interview()` for an interview with no traces | Return an empty list, not an error — reads degrade gracefully, same as Conversation Memory and Evidence Graph |

## Responsibilities

- Persist a trace record for every reasoning decision, referencing
  `question_id`, `target_competency_id`, and (once available)
  `evidence_ids_referenced` rather than duplicating the underlying
  content those IDs point to.
- Enforce append-only semantics with exactly one controlled, narrow
  exception (`update_trace_outcome`).
- Provide interview-scoped and competency-scoped queries.
- Make "why was this question asked, and what happened after" fully
  answerable from stored data — this is the concrete deliverable behind
  Architecture Review Gate #5.

## Explicit Non-Responsibilities

- Does not decide `decision_strategy`, generate `reason_for_asking`, or
  compute `confidence_pre`/`confidence_post` — this module only stores
  what the Reasoning Engine and Evaluation Engine report. Zero
  reasoning logic lives here.
- Does not validate that `confidence_pre`/`confidence_post` values are
  "correct" in any evaluative sense — only that they're present and
  numeric. Correctness of the reasoning itself is entirely upstream.
- Does not surface data to students — this is an internal
  observability tool (Architecture Review Gate #5's explicit purpose:
  debugging and reasoning transparency for the team, not a
  student-facing feature). Any future student-facing "why was I asked
  this" feature would be a distinct, separate concern built on top of
  this data, not something this module does itself.
- Does not aggregate, summarize, or analyze trace data across
  interviews — this module is a record store and query interface, not
  an analytics engine.
- Is not the Pilot Learning Loop's feedback-form storage (Architecture
  Section 7) — that's a separate, student-facing data path, not to be
  conflated with this internal reasoning trace.

## Acceptance Criteria

1. `record_trace()` followed by `get_trace()` returns a record with
   `confidence_post: null` and `evidence_ids_referenced` empty/null
   until updated.
2. `update_trace_outcome()` correctly populates `confidence_post` and
   `evidence_ids_referenced` on the matching record — verified by
   `get_trace()` returning the updated values.
3. `record_trace()` with a duplicate `question_id` raises
   `DUPLICATE_QUESTION_ID`.
4. `update_trace_outcome()` for a nonexistent `question_id` raises
   `TRACE_NOT_FOUND`.
5. `update_trace_outcome()` called twice for the same `question_id`
   raises `OUTCOME_ALREADY_RECORDED` on the second call; the first
   outcome is preserved.
6. `update_trace_outcome()` cannot alter any field other than
   `confidence_post` and `evidence_ids_referenced` — tested explicitly,
   same discipline as Conversation Memory's AC11.
7. `get_traces_for_interview()` for an interview with no traces returns
   an empty list, not an error.
8. `get_traces_for_competency()` correctly filters by
   `target_competency_id`.
9. Two different `interview_id`s never see each other's traces — same
   severity as Conversation Memory's AC10 and Evidence Graph's AC9;
   treat as a merge blocker.
10. `sequence_number` is monotonic within an interview and does not
    change after assignment.
11. A structural test confirms no field in the schema holds full
    conversation or evidence content — only IDs, short human-readable
    justification strings (`evidence_missing`, `reason_for_asking`),
    and numeric confidence values. Same class of check as Evidence
    Graph's AC8.
12. `record_trace()` with `confidence_pre` outside `[0.0, 1.0]` raises
    `CONFIDENCE_OUT_OF_RANGE` — tested with both a value above 1.0 and
    a value below 0.0.
13. `update_trace_outcome()` with `confidence_post` outside
    `[0.0, 1.0]` raises `CONFIDENCE_OUT_OF_RANGE` — same boundary
    tested on the update path, not just creation.
14. Every stored record has a non-null `contract_version` field,
    populated automatically without the caller needing to supply it.

## Review Checklist (before merge)

- [ ] Schema matches Architecture Section 6's field list, formalized
      per this contract
- [ ] All 4 Error Contract codes have test coverage
- [ ] `update_trace_outcome` immutability tested (AC6)
- [ ] Interview isolation tested explicitly (AC9) — merge blocker
- [ ] Append-only discipline verified — no public method other than
      `update_trace_outcome` can mutate an existing record
- [ ] No full conversation/evidence content duplicated (AC11)
- [ ] `decision_strategy` and any other enum-like field uses a shared
      type alias where one already exists elsewhere in the codebase,
      rather than a fresh string/Literal redefinition — per the
      recurring str-vs-Literal pattern flagged in Module 4's review
- [ ] No `ProviderAdapter`, LLM, or embeddings import anywhere —
      deterministic only
