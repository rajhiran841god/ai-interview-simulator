# Module Contract — Evaluation Engine

**Status:** Draft — pending review before implementation
**Milestone:** 3, Module 6 of 10 (see Milestone_2_Architecture.md Section 11)

**Note on module nature:** this is the first module since JD
Understanding to call `ProviderAdapter`, and the first module in the
project that makes a genuine judgment call — "does this answer
actually address the gap" (Architecture Section 2.8) — rather than
extracting facts (Resume/JD Understanding) or passively storing them
(Conversation Memory, Evidence Graph, Logging). The no-fabrication and
determinism disciplines from earlier modules still apply where
relevant, but this module's core job is evaluative, not extractive.

**Explicit scope resolution, stated before implementation rather than
discovered during it:** this module's output feeds Logging's
`confidence_post` field. Competency-level *aggregate* confidence is
Competency Model's job (Module 7, not yet built). To avoid this module
silently overreaching into territory it doesn't own, **`confidence_post`
as written by this module represents this module's assessment of how
convincingly this one specific answer addressed this one specific
evidence gap — not an aggregate competency score.** Competency Model
will later be responsible for aggregating per-question confidence
contributions like this one into an overall per-competency score,
using its own logic. This module does not attempt that aggregation.

**Confidence Handling Policy (single deterministic rule, not a choice
of two):** if the LLM-proposed confidence value falls outside
`[0.0, 1.0]`, this module **rejects it — it never clamps**. A clamped
value (e.g. `1.83` silently becoming `1.0`) is indistinguishable from a
legitimately-computed `1.0` downstream, destroying the evidence that
something went wrong upstream. An out-of-range value is treated as an
`EVALUATION_FAILED` condition: return the same degraded
`EvaluationResult` used for a failed/unparseable LLM response
(`confidence_contribution: 0.0`, empty evidence,
`reasoning_summary` explaining the anomaly), so the failure is visible
and investigable rather than silently absorbed.

---

## Purpose

Given a candidate's answer to a question, determine whether and how
well it addresses the targeted evidence gap, extract evidence from the
answer (writing it to Evidence Graph, Module 4 — already built),
detect whether it contradicts prior evidence for the same competency,
and record the outcome in Logging (Module 5 — already built) via
`update_trace_outcome`.

Per Architecture Section 2.8: "must be able to recognize a non-answer,
a deflection, or a strong answer, not just log text." This module's
central deliverable is that classification, not just evidence
extraction — a candidate who deflects or gives a non-answer still
needs to be recognized as having done so, which is itself a form of
evidence (or absence of it).

## Inputs

### `evaluate_answer(...)`

| Field | Type | Required | Notes |
|---|---|---|---|
| interview_id | string | Yes | |
| question_id | string | Yes | References Conversation Memory's `question_id` |
| turn_id | string | Yes | References Conversation Memory's `turn_id` — needed to call Evidence Graph's `add_evidence`, which itself validates against Conversation Memory |
| target_competency_id | string | No | May be null for non-competency-targeted turns (e.g. greeting) — if null, this module does no evidence extraction and returns a minimal result (see Non-Responsibilities) |
| evidence_missing | string | Yes | The gap this question was trying to close — from the trace record, gives this module context on what it's checking for |
| answer_text | string | Yes | The candidate's actual answer — this module does not re-fetch it from Conversation Memory itself; the caller supplies it, since the caller (eventually Reasoning Engine's orchestration) already has it in context |

### Output — `EvaluationResult`

```json
{
  "answer_classification": "substantive" | "partial" | "deflection" | "non_answer",
  "evidence_ids_created": [string],
  "contradiction_detected": boolean,
  "contradicted_evidence_id": string | null,
  "confidence_contribution": number,
  "reasoning_summary": string
}
```

- **`answer_classification`** — the core judgment this module makes.
  `substantive`: directly and specifically addresses the gap.
  `partial`: addresses it somewhat but leaves real ambiguity.
  `deflection`: answers a different, easier question instead (a common
  interview evasion pattern — must be distinguished from `non_answer`).
  `non_answer`: doesn't engage with the question at all (e.g. "I don't
  know," off-topic rambling, refusal).
- **`evidence_ids_created`** — the actual `evidence_id`s returned by
  Evidence Graph's `add_evidence()` calls this module makes. Not
  duplicated content — references only, consistent with the identity
  discipline established in Module 4.
- **`contradiction_detected`** / **`contradicted_evidence_id`** — set
  when this module determines the answer conflicts with previously
  recorded evidence for the same competency. If true, the evidence
  entry created here is written to Evidence Graph with
  `relation: "contradicts"` and the matching `contradicts_evidence_id`
  — this module is the one that actually performs the semantic
  contradiction judgment Evidence Graph explicitly declined to do
  itself (Evidence Graph Contract's Non-Responsibilities: "does not
  perform semantic contradiction detection itself... the caller
  determines that"). **Contradiction detection is scoped strictly to
  evidence within the same `interview_id`** — this module never
  compares against or is influenced by evidence from any other
  interview.
- **`confidence_contribution`** — see the Explicit Scope Resolution
  above. Range `[0.0, 1.0]`, same domain as Logging's confidence
  fields.
- **`reasoning_summary`** — human-readable, becomes part of
  `reason_for_asking`-adjacent context for debugging; not shown to
  students (same internal-only status as all Logging data).

## Responsibilities

- Classify the answer's engagement with the question (substantive /
  partial / deflection / non_answer).
- Extract evidence from substantive or partial answers and write it to
  Evidence Graph via `add_evidence()` — reusing that module's existing
  provenance enforcement, not reimplementing it. This module is
  responsible for identifying *which excerpt* constitutes evidence;
  Evidence Graph remains responsible for verifying that excerpt is
  real.
- Detect contradictions with prior evidence for the same competency —
  this module owns the semantic judgment; Evidence Graph owns the
  structural recording of it.
- Compute a per-question `confidence_contribution`, scoped exactly as
  described above — not a competency aggregate.
- Call Logging's `update_trace_outcome()` with `confidence_post =
  confidence_contribution` and `evidence_ids_referenced =
  evidence_ids_created`, closing the trace lifecycle Module 5 was
  built to support.

## Explicit Non-Responsibilities

- Does not decide what question to ask next (Reasoning Engine's job,
  Module 8 — not yet built).
- Does not maintain or aggregate competency-level confidence across
  multiple questions — see Explicit Scope Resolution above. This
  module's output is an input to that future aggregation, not the
  aggregation itself.
- Does not generate follow-up questions, even when it detects a
  deflection or contradiction — it only reports the classification;
  deciding to probe further is Reasoning Engine's job.
- If `target_competency_id` is null (e.g. a greeting turn), this
  module performs no evidence extraction and returns a minimal
  `EvaluationResult` with `answer_classification` still populated (a
  greeting can still be classified, e.g. as `substantive` if
  appropriately responded to) but `evidence_ids_created: []` and
  `confidence_contribution` reflecting only engagement, not competency
  evidence.
- Does not itself decide the interview's stopping condition (that's
  Reasoning Engine territory, per Milestone 2 Architecture Section 4).
- Does not fabricate evidence under any framing — the LLM call this
  module makes proposes evidence excerpts, but every proposed excerpt
  passes through Evidence Graph's existing `EXCERPT_NOT_TRACEABLE`
  check before being accepted. This module does not bypass or weaken
  that check.

## Error Contract

| Code | Meaning | Behavior |
|---|---|---|
| `EMPTY_ANSWER` | `answer_text` is empty or whitespace-only | Classify as `non_answer` immediately, skip the LLM call entirely — an empty answer needs no semantic judgment to classify |
| `EVALUATION_FAILED` | LLM call fails or returns unparseable output | Return a minimal `EvaluationResult` with `answer_classification: "non_answer"`, empty evidence, `confidence_contribution: 0.0`, and a `reasoning_summary` explaining the evaluation itself failed — this is a recoverable degradation, not a rejection, consistent with Resume/JD Understanding's `STRUCTURING_FAILED` pattern |
| `TRACE_NOT_FOUND` | The `question_id` supplied has no corresponding trace in Logging (i.e. `record_trace` was never called for it) | Reject — raise. This module should never be evaluating an answer to a question that was never logged as asked; that indicates a caller ordering bug upstream, not a recoverable condition here |

`EMPTY_ANSWER` and `EVALUATION_FAILED` are recoverable — a bad or
missing answer is a legitimate interview outcome, not a system error.
`TRACE_NOT_FOUND` is a rejection because it indicates something
upstream is calling this module out of order.

## Acceptance Criteria

1. A clearly substantive, on-topic answer with specific detail is
   classified `substantive`, and at least one evidence entry is
   created in Evidence Graph, traceable back to real answer text
   (verified via Evidence Graph's own provenance check succeeding, not
   reimplemented here).
2. A clearly off-topic or evasive answer (e.g. answering a different
   question than asked) is classified `deflection`, distinct from
   `non_answer` — tested with both a deflection example and a genuine
   non-answer example, confirming they produce different
   classifications.
3. An empty or whitespace-only answer is classified `non_answer`
   immediately, via the `EMPTY_ANSWER` path, without an LLM call being
   made (verified by mocking the provider and confirming it's never
   invoked for this case).
4. When the LLM call fails or returns unparseable output, the module
   returns a minimal, safe `EvaluationResult` rather than raising —
   `EVALUATION_FAILED` handled gracefully.
5. A contradictory answer (conflicting with a previously recorded
   piece of evidence for the same competency) results in
   `contradiction_detected: true`, a correctly populated
   `contradicted_evidence_id`, and an Evidence Graph entry written with
   `relation: "contradicts"` — verified end-to-end, not just at the
   classification level.
6. `evaluate_answer()` for a `question_id` with no existing trace in
   Logging raises `TRACE_NOT_FOUND`.
7. After a successful evaluation, Logging's trace record for that
   `question_id` has `confidence_post` and `evidence_ids_referenced`
   correctly populated — verified by querying Logging directly after
   the call, not just checking `EvaluationResult`'s return value.
8. `confidence_contribution` is always within `[0.0, 1.0]` — this
   module is responsible for producing a value within Logging's
   accepted domain. **Policy: reject, never clamp** (see Confidence
   Handling Policy below). Tested by confirming an out-of-range
   LLM-proposed value results in the `EVALUATION_FAILED` degraded path
   — not a silently adjusted value passed through to
   `update_trace_outcome()`.
9. `target_competency_id: null` input produces no Evidence Graph
   writes and a minimal `EvaluationResult`, without raising.
10. No evidence is ever written to Evidence Graph that fails its own
    `EXCERPT_NOT_TRACEABLE` check — i.e. this module never attempts to
    bypass, catch-and-suppress, or weaken that check; a fabricated
    excerpt proposal from the LLM should surface as a dropped/skipped
    evidence entry (with a warning), not a system crash and not a
    silent bypass.
11. **Orchestration determinism:** given a fixed, mocked provider
    response, repeated calls to `evaluate_answer()` with identical
    inputs produce identical `EvaluationResult` output. This does not
    claim production LLM calls are deterministic — they aren't — it
    verifies that this module's own orchestration code (parsing,
    classification mapping, evidence-writing logic) introduces no
    accidental randomness of its own around a fixed model response.
12. Contradiction detection only ever compares against evidence
    recorded within the **same `interview_id`** — tested explicitly
    with evidence seeded in a different interview, confirming it is
    never considered as a contradiction candidate. Evidence Graph and
    Conversation Memory already enforce this isolation structurally,
    but this module's contract states it directly so the constraint is
    self-contained and doesn't rely on a reader tracing it through two
    other contracts.

## Review Checklist (before merge)

- [ ] Schema matches this contract exactly
- [ ] All 3 Error Contract codes have test coverage
- [ ] Deflection vs. non-answer distinction tested explicitly (AC2) —
      this is the subtlest classification judgment in the module
- [ ] Contradiction detection tested end-to-end through Evidence Graph,
      not just at the classification level (AC5)
- [ ] Full Logging integration tested — `update_trace_outcome` actually
      called and verified via a fresh query, not just asserted on the
      return value (AC7)
- [ ] `confidence_contribution` domain enforcement tested (AC8)
- [ ] No `ProviderAdapter` SDK import outside the established
      abstraction — same rule as Resume/JD Understanding
- [ ] Evidence Graph's `EXCERPT_NOT_TRACEABLE` check is never bypassed
      or caught-and-suppressed in a way that lets fabricated evidence
      through (AC10)
- [ ] `decision_strategy`/`Relation`/other enum-like fields import from
      `app.shared.types` per Decision #003, not redefined locally
- [ ] Confidence handling follows reject-not-clamp policy exclusively
      — no code path silently adjusts an out-of-range value (AC8)
- [ ] Orchestration determinism tested against a fixed mocked provider
      response (AC11)
- [ ] Contradiction detection cross-interview isolation tested
      explicitly (AC12)
