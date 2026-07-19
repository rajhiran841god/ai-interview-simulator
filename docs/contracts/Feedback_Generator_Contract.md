# Module Contract — Feedback Generator

**Status:** Draft — pending review before implementation
**Milestone:** 3, Module 10 of 10 — the final module (see
Milestone_2_Architecture.md Section 11)

**This module is where Architecture Review Gate #4 (Evidence-Based
Feedback) is finally, concretely delivered.** Every prior module's
discipline — provenance validation, evidence traceability, the
confidence-scores-are-internal rule — exists to make this module
possible. This is the module a student actually sees output from.

**Note on module nature:** calls `ProviderAdapter` (third reasoning-
family module to do so, after Evaluation Engine and Question
Generator) to synthesize qualitative summaries — but the fabrication
discipline here is stricter than any prior module's, because this is
the first output a real person reads and may act on. See Grounding
and Verification below.

---

## Purpose

Produce the final, student-facing interview report: per-competency
qualitative feedback, every claim traceable to specific evidence
already recorded in Evidence Graph, with **zero raw confidence numbers
ever exposed**, per the Critical Constraint established in Milestone 2
Architecture Section 5 and restated in every module that has touched
confidence since (Evaluation Engine, Competency Model, Reasoning
Engine).

## Inputs

### `generate_feedback_report(interview_id)`

| Field | Type | Required |
|---|---|---|
| interview_id | string | Yes |

This module derives everything else by querying Competency Model (for
the tracked competency set — not their confidence values, just which
competencies exist and their `emphasis`), Evidence Graph (for actual
evidence), and Conversation Memory (for question/answer context to
enrich generation).

## Grounding and Verification — Stricter Than Any Prior Module

Per-competency generation works like this:

1. Fetch all real evidence entries for the competency from Evidence
   Graph — both `supports` and `contradicts` — each with its
   `evidence_id` and `evidence_excerpt`.
2. Optionally enrich with the full question text from Conversation
   Memory (via each evidence entry's `turn_id`) for better context —
   real data only, never invented.
3. Supply the LLM with **exactly this list** — `{evidence_id,
   evidence_excerpt, relation}` tuples — and ask it to write a
   qualitative summary, and to explicitly report **which
   `evidence_id`s from the supplied list** support each claim it makes.
4. **Verification step, structural not fuzzy:** every `evidence_id`
   the LLM reports using is checked against the real set supplied in
   step 1. Any `evidence_id` not in that set is dropped — this can
   never happen if prompted correctly, but the check exists
   defensively, the same "never trust LLM output blindly" discipline
   every prior provider-using module has applied.

This differs from earlier modules' provenance approach (exact
substring matching on raw extracted text) because the LLM here is
synthesizing prose, not extracting facts — but it achieves the same
goal: **the LLM can only ever reference evidence that actually exists
and was actually supplied to it**, never evidence it invents.

## Output — `InterviewFeedbackReport`

```json
{
  "interview_id": string,
  "competency_feedback": [
    {
      "competency_id": string,
      "emphasis": "primary" | "secondary",
      "summary_text": string,
      "supporting_evidence_ids": [string],
      "contradictory_evidence_ids": [string],
      "has_unresolved_contradiction": boolean,
      "insufficient_evidence": boolean
    }
  ],
  "overall_summary": string,
  "generated_at": string
}
```

**No field in this schema is, or derives directly from, a raw
confidence number.** This is a hard structural rule — see Acceptance
Criterion 1.

- **`insufficient_evidence: true`** — used when a competency has zero
  or near-zero evidence. The `summary_text` in this case must say so
  plainly (e.g. "There wasn't enough discussion of this area to
  provide meaningful feedback") rather than inventing a qualitative
  assessment from nothing. This is the direct feedback-layer
  consequence of Resume/JD Understanding's original no-fabrication
  rule — absence of data must be reported as absence, never papered
  over.
- **`has_unresolved_contradiction`** — set when
  `contradictory_evidence_ids` is non-empty. `summary_text` should
  address this directly and professionally (e.g. "Your answers gave
  differing accounts of who made the final decision — it would help
  to clarify this"), not silently ignore it.
- **Competency ordering in `competency_feedback`** is `emphasis`
  (primary before secondary) then `competency_id` alphabetically —
  **deterministic, and deliberately never derived from confidence**,
  even implicitly through sort order. This avoids any risk of
  confidence leaking through presentation structure, not just through
  an explicit field.

## Responsibilities

- Generate qualitative, evidence-grounded feedback for every
  competency tracked by Competency Model for the interview.
- Enforce the verification step above for every generated claim.
- Handle zero-evidence competencies explicitly and honestly
  (`insufficient_evidence: true`), never fabricating substance.
- Surface unresolved contradictions in the feedback text.
- Never include a raw confidence number, or any field a reasonable
  reader could reverse-engineer into one (e.g. a 1-10 score, a
  percentage, a letter grade derived from confidence).

## Explicit Non-Responsibilities

- Does not re-evaluate answers — relies entirely on Evidence Graph's
  already-recorded evidence; does not call Evaluation Engine again.
- Does not decide interview flow, questions, or stopping — purely
  post-interview synthesis, called once the interview has ended.
- Does not manage the Pilot Learning Loop's student feedback form
  (Milestone 2 Architecture Section 7 — "did this feel like a real
  interview?") — that is a separate, distinct data path collecting
  the student's *experience* of the pilot, not this module's
  evaluation *of* the student. The two must not be conflated in the
  same report or the same module.
- Does not expose confidence values under any label, transformation,
  or derived metric — see Responsibilities.
- Does not generate feedback for a competency that was never
  initialized in Competency Model.

## Error Contract

| Code | Meaning | Behavior |
|---|---|---|
| `NO_COMPETENCIES_INITIALIZED` | Competency Model has no tracked competencies for this interview | Reject — raise. Cannot generate a report for an interview that never started properly |
| `GENERATION_FAILED` | LLM call fails or returns unparseable output for a specific competency | Recoverable — that competency's `summary_text` falls back to a neutral templated statement (e.g. "Feedback for this area could not be generated — evidence was recorded but could not be synthesized"), while other competencies' feedback generation proceeds independently. One competency's failure must not abort the whole report |

Only one rejection error — everything else degrades gracefully,
per-competency, since a partial report (some competencies with good
feedback, one with a fallback message) is far more useful to a student
than no report at all.

## Acceptance Criteria

1. **Structural schema check**: no field in `InterviewFeedbackReport`
   or its nested objects is a float, a percentage, or any numeric
   confidence-derived value — verified by inspecting the schema
   itself, not just a sample output. This is the single most important
   acceptance criterion in the entire project, given the Critical
   Constraint it enforces.
2. A competency with real, unambiguous supporting evidence produces
   `summary_text` that references content genuinely present in that
   evidence — not generic boilerplate.
3. A competency with zero evidence produces `insufficient_evidence:
   true` and an honest `summary_text` acknowledging the gap, never
   invented substance.
4. A competency with contradictory evidence produces
   `has_unresolved_contradiction: true` and `summary_text` that
   addresses the inconsistency directly.
5. **Fabricated evidence_id rejection**: if the LLM's raw response
   references an `evidence_id` not present in the real set supplied to
   it (simulated via a mocked response for testing), that ID is
   dropped from `supporting_evidence_ids`/`contradictory_evidence_ids`
   — never silently trusted.
6. When LLM generation fails for one competency, that competency falls
   back to a templated statement while other competencies in the same
   report generate normally — verified by confirming a multi-
   competency report with one forced failure still returns complete,
   non-empty feedback for the unaffected competencies.
7. `generate_feedback_report()` for an interview with no initialized
   competencies raises `NO_COMPETENCIES_INITIALIZED`.
8. Competency ordering in the output is deterministic
   (emphasis-then-alphabetical) and does not vary across repeated
   calls with identical underlying state.
9. **End-to-end integration test**: real Evidence Graph and
   Competency Model state, built through the actual multi-module
   pipeline (Conversation Memory → Evidence Graph → Evaluation Engine
   → Competency Model, not hand-constructed), drives
   `generate_feedback_report()`, and the resulting report is verified
   against that real state — the widest integration test in the
   project, matching the standard set by every module since
   Competency Model.
10. Two different `interview_id`s never produce cross-contaminated
    feedback — tested explicitly, same isolation severity as every
    prior module.

## Review Checklist (before merge)

- [ ] Schema matches this contract exactly
- [ ] AC1 (no confidence leakage) verified structurally, not just by
      example output — this is the merge blocker above all others
- [ ] Both Error Contract codes have test coverage
- [ ] Per-competency graceful degradation tested (AC6) — one failure
      must not abort the whole report
- [ ] Fabricated evidence_id rejection tested (AC5)
- [ ] Ordering determinism tested (AC8)
- [ ] End-to-end integration with the real multi-module pipeline
      tested (AC9)
- [ ] Interview isolation tested (AC10)
- [ ] No `ProviderAdapter` SDK import outside the established
      abstraction
- [ ] Pilot Learning Loop's student-experience feedback form is
      nowhere referenced or conflated with this module's output
