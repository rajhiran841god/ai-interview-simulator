# Module Contract — Competency Model / Confidence Tracker

**Status:** Draft — pending review before implementation
**Milestone:** 3, Module 7 of 10 (see Milestone_2_Architecture.md Section 11)

**Framing, stated explicitly so this module doesn't drift into
Evaluation Engine's territory:** Evaluation Engine (Module 6) answers
"how much did this one answer help?" — a per-question signal. This
module answers "given everything we've seen so far, what do we
believe about this competency?" — an aggregate, evolving belief state.
Module 6 does not own that aggregate; this module does. This module
does not re-judge individual answers; it only aggregates what
Evaluation Engine already reported.

**Critical constraint, carried from Milestone 2 Architecture Section
5 (restated here so it's self-contained):** confidence values produced
by this module are internal reasoning signals — "confidence that
sufficient evidence has been collected to assess this competency" —
never an objective measure of the candidate's true ability. Never
exposed raw to students. This module's output feeds the Reasoning
Engine (Module 8) internally.

---

## Purpose

Maintain the live, per-competency belief state for an interview:
evidence count, references to supporting and contradictory evidence,
and a derived confidence score — updated incrementally as Evaluation
Engine reports on each answer. Per Milestone 2 Architecture Section
2.3, this module also exposes "lowest-confidence competency" so the
Reasoning Engine (not yet built) can decide what to probe next.

This module is built before its primary reader (Reasoning Engine)
exists, same relationship every prior module had to its eventual
caller.

## Inputs

### `initialize_competencies(interview_id, competencies)`

Seeds tracked state at interview start, from JD Understanding's
`required_competencies` output. Each competency starts at
`evidence_count: 0`, empty evidence lists, `confidence: 0.0`.
Competencies not initialized here cannot later be updated — see
Non-Responsibilities.

| Field | Type | Required |
|---|---|---|
| interview_id | string | Yes |
| competencies | list of `{competency_id, emphasis}` (from JD Understanding's schema) | Yes |

### `update_from_evaluation(interview_id, competency_id, confidence_contribution, contradiction_detected, evidence_ids_created)`

The core update operation, called once per answer evaluated by
Evaluation Engine.

| Field | Type | Required | Notes |
|---|---|---|---|
| interview_id | string | Yes | |
| competency_id | string | Yes | Must already be initialized via `initialize_competencies` |
| confidence_contribution | float | Yes | From Evaluation Engine's `EvaluationResult`, `[0.0, 1.0]` |
| contradiction_detected | boolean | Yes | From `EvaluationResult` |
| evidence_ids_created | list[string] | Yes | References into Evidence Graph — appended to `positive_evidence` or `contradictory_evidence` depending on `contradiction_detected`, never copied as content |

### `get_competency_state(interview_id, competency_id)`
Single competency's current state.

### `get_all_competency_states(interview_id)`
Full state for every tracked competency.

### `get_lowest_confidence_competency(interview_id)`
Returns the `competency_id` with the lowest current confidence among
tracked competencies — the query the Reasoning Engine will use to
decide what to target next. Returns `None` if no competencies are
tracked (should not happen in practice if `initialize_competencies`
was called correctly, but handled gracefully rather than raising).

## Output — Competency State Schema

```json
{
  "interview_id": string,
  "competency_id": string,
  "emphasis": "primary" | "secondary",
  "evidence_count": integer,
  "positive_evidence": [string],
  "contradictory_evidence": [string],
  "confidence": number,
  "last_updated": string | null
}
```

Deliberately limited to these fields, per Milestone 2 Architecture
Section 2.3: "kept to these four fields for the pilot" (evidence_count,
positive_evidence, contradictory_evidence, confidence) plus `emphasis`
(carried from JD Understanding, needed so Reasoning Engine can weight
primary vs. secondary competencies) and `last_updated` (operational,
same rationale as other modules' internal timestamp fields).

## Update Algorithm — Stated Explicitly, Flagged as a Tunable Pilot Default

This is the first module in the project where the update logic itself
is a real design decision, not just a storage/validation pattern.
Documenting it precisely here so it's reviewable and tunable, not
buried in code:

**No contradiction (`contradiction_detected: false`):**
- `evidence_count += len(evidence_ids_created)`
- `positive_evidence` extended with the new evidence IDs
- `confidence` updated via incremental weighted average:
  `new_confidence = old_confidence + (confidence_contribution - old_confidence) / evidence_count`
  (standard incremental mean — each new piece of supporting evidence
  moves the aggregate toward the new data point, with diminishing
  influence as more evidence accumulates)

**Contradiction detected (`contradiction_detected: true`):**
- `evidence_count += len(evidence_ids_created)`
- `contradictory_evidence` extended with the new evidence IDs
- `confidence` reduced by a fixed penalty, not averaged in:
  `new_confidence = max(0.0, old_confidence - CONTRADICTION_PENALTY)`
  where `CONTRADICTION_PENALTY` is a configurable constant (pilot
  default: `0.3`) — **not derived from any validated model of how much
  a contradiction should matter.** A contradiction is treated as a
  penalty rather than averaged in like supporting evidence because it
  represents an inconsistency signal, not a data point about the
  competency's true strength — averaging it in would let contradictory
  and supporting evidence wash out to a misleadingly stable-looking
  number.

**This algorithm is a first-pass, honestly-flagged pilot default.**
Like the 6/18 question-count bounds in Milestone 2 Architecture Section
4, `CONTRADICTION_PENALTY` and the incremental-mean approach should be
expected to change once real pilot data shows whether this produces
sensible-feeling confidence trajectories. Implemented as configurable
values, not hardcoded, for exactly this reason.

## Error Contract

| Code | Meaning | Behavior |
|---|---|---|
| `COMPETENCY_NOT_INITIALIZED` | `update_from_evaluation()` called for a `competency_id` never passed to `initialize_competencies()` for this interview | Reject — raise. Prevents silent drift from JD Understanding's actual competency set |
| `DUPLICATE_INITIALIZATION` | `initialize_competencies()` called twice for the same `interview_id` | Reject — raise. Competency sets are fixed at interview start, not re-seedable mid-interview |
| `CONFIDENCE_CONTRIBUTION_OUT_OF_RANGE` | `confidence_contribution` outside `[0.0, 1.0]` | Reject — raise. Same reject-not-clamp philosophy as Evaluation Engine and Logging — this module does not silently adjust a bad input |
| `INTERVIEW_NOT_FOUND` | `get_all_competency_states()` / `get_lowest_confidence_competency()` for an interview never initialized | Return empty list / `None` respectively — reads degrade gracefully, same as every prior deterministic module |

## Responsibilities

- Initialize per-interview competency tracking from JD Understanding's
  output.
- Apply the update algorithm above on every `update_from_evaluation`
  call, maintaining `evidence_count`, `positive_evidence`,
  `contradictory_evidence`, and `confidence` correctly.
- Expose the lowest-confidence competency for Reasoning Engine's use.
- Enforce that confidence never leaves `[0.0, 1.0]` regardless of how
  many updates accumulate.

## Explicit Non-Responsibilities

- Does not itself extract evidence or classify answers — consumes
  Evaluation Engine's already-computed `confidence_contribution` and
  `contradiction_detected`, does not re-derive them.
- Does not decide what question to ask next, or when to stop
  (Reasoning Engine's job, Module 8).
- Does not expose confidence values to students in any form — this
  remains an internal reasoning signal per the Critical Constraint
  stated above. Any future student-facing "readiness" signal is a
  distinct, separate concern (Feedback Generator's eventual job, using
  qualitative evidence-grounded language, not raw numbers).
- Does not allow competencies to be added or removed mid-interview —
  the set is fixed at `initialize_competencies()` time. If JD
  Understanding's output changes mid-interview (it shouldn't, given
  the JD is fixed at interview start), that's an upstream orchestration
  concern, not something this module accommodates.
- Does not itself decide the interview's stopping condition — it
  exposes confidence values; Reasoning Engine applies the actual
  threshold/floor logic from Architecture Section 4 against them.

## Acceptance Criteria

1. `initialize_competencies()` followed by `get_competency_state()`
   for each seeded competency returns `evidence_count: 0`,
   `confidence: 0.0`, empty evidence lists.
2. A single `update_from_evaluation()` call with no contradiction sets
   `confidence` exactly equal to the reported `confidence_contribution`
   (correct behavior of the incremental mean on the first data point).
3. A second `update_from_evaluation()` call with no contradiction
   moves `confidence` toward the new `confidence_contribution` without
   overwriting it entirely — verified with concrete numbers (e.g.
   starting confidence 0.8, new contribution 0.4, resulting confidence
   should be the correct incremental mean, not 0.4 and not unchanged).
4. A contradiction-flagged update reduces confidence by exactly
   `CONTRADICTION_PENALTY`, clamped at `0.0` (never negative) — tested
   with a case that would go negative without the floor.
5. `evidence_ids_created` are correctly routed to `positive_evidence`
   or `contradictory_evidence` depending on `contradiction_detected`,
   never both.
6. `update_from_evaluation()` for a never-initialized `competency_id`
   raises `COMPETENCY_NOT_INITIALIZED`.
7. `initialize_competencies()` called twice for the same interview
   raises `DUPLICATE_INITIALIZATION`.
8. `update_from_evaluation()` with `confidence_contribution` outside
   `[0.0, 1.0]` raises `CONFIDENCE_CONTRIBUTION_OUT_OF_RANGE` —
   rejected, not clamped, same policy as Evaluation Engine.
9. `get_lowest_confidence_competency()` correctly identifies the
   lowest-confidence tracked competency across at least 3 competencies
   with distinct confidence values.
10. `get_lowest_confidence_competency()` returns `None` for an
    interview with no initialized competencies, rather than raising.
11. Two different `interview_id`s never see each other's competency
    state — same isolation severity as every prior deterministic
    module; merge blocker.
12. **End-to-end integration test**: a real `EvaluationResult` from
    Evaluation Engine (Module 6, already built) is fed directly into
    `update_from_evaluation()`, and the resulting competency state is
    verified — not a hand-constructed mock of what an `EvaluationResult`
    looks like. This is the same standard Module 6 set for its own
    integration with Modules 3-5.

## Review Checklist (before merge)

- [ ] Schema matches this contract exactly
- [ ] All 4 Error Contract codes have test coverage
- [ ] Update algorithm matches the documented formulas exactly (AC2-4)
      — this is the one place a subtle implementation bug could easily
      hide behind passing-looking tests if the formula itself isn't
      checked against concrete expected numbers
- [ ] Interview isolation tested explicitly (AC11) — merge blocker
- [ ] `CONTRADICTION_PENALTY` implemented as a configurable value, not
      hardcoded inline
- [ ] End-to-end integration with real Evaluation Engine output tested
      (AC12), not just hand-mocked inputs
- [ ] No confidence value ever exposed through any method in a form
      that could reach a student-facing surface — this module has no
      legitimate student-facing caller at all in v0.1, and the
      contract should stay that way
- [ ] `Emphasis` and any other enum-like field imports from
      `app.shared.types` per Decision #003
