# Module Contract — Question Generator / Cross-Questioning Engine

**Status:** Draft — pending review before implementation
**Milestone:** 3, Module 9 of 10 (see Milestone_2_Architecture.md Section 11)

**Note on module nature:** this module calls `ProviderAdapter` — the
second reasoning-family module to do so after Evaluation Engine — but
its fabrication risk is qualitatively different from every prior
LLM-using module. Resume/JD Understanding and Evaluation Engine
extract or classify *facts*, where fabrication means inventing
something that wasn't said. This module *generates* a question, which
is inherently creative — the risk here isn't inventing facts, it's
**misattributing what the candidate actually said** when a
cross-question references their prior answer (e.g. putting words in
their mouth, or referencing something from a different competency's
evidence). The grounding discipline below addresses that specific,
narrower risk.

---

## Purpose

Turn a `ReasoningDecision` (Module 8's output: target competency,
strategy, evidence gap, reason) into actual natural-language question
text, correctly distinguishing a fresh question (opening a new
competency) from a cross-question (probing deeper into or challenging
something already said). Per Milestone 2 Architecture Section 2.6,
this module also owns recording the resulting turn in Conversation
Memory — it's the actual point where a `ReasoningDecision` becomes a
real conversational turn the candidate will see.

## Inputs

### `generate_question(interview_id, reasoning_decision)`

| Field | Type | Required | Notes |
|---|---|---|---|
| interview_id | string | Yes | |
| reasoning_decision | `ReasoningDecision` | Yes | Module 8's output. Must have `decision_type: "continue"` — see Error Contract |

This module derives everything else itself: it queries Evidence Graph
for the target competency's existing evidence (for cross-questioning
grounding) and Conversation Memory for recent history (for repetition
avoidance), rather than requiring the caller to supply that context.

## Question Type Mapping — Deterministic, Not LLM-Decided

Per Architecture Section 2.6's fresh/cross-question distinction, this
module maps `decision_strategy` + target competency's evidence state
to `question_type` deterministically, before any LLM call:

```
if decision_strategy == "probe_deeper" and target competency has zero evidence:
    question_type = "fresh"
elif decision_strategy == "probe_deeper" and target competency has some evidence:
    question_type = "cross_question"   # deepening, not opening
elif decision_strategy in ("challenge_inconsistency", "verify", "wrap_up_competency"):
    question_type = "cross_question"   # all reference prior answers
elif decision_strategy == "switch_competency":
    question_type = "fresh"            # not reachable in v0.1 — Reasoning
                                         # Engine never selects this strategy
                                         # yet, mapping included for completeness
```

This mapping is deterministic code, not something the LLM decides —
keeping the fresh/cross-question distinction auditable independent of
model output quality.

## Grounding Discipline (the fabrication-adjacent risk specific to this module)

For any `cross_question`, the LLM call is given **only real evidence
excerpts already stored in Evidence Graph** for the target competency
(via `get_evidence_for_competency`) as grounding context — never
free-text summaries this module invents itself. The prompt explicitly
instructs the model to reference only what's in the supplied evidence,
never to introduce a claim about what the candidate said that isn't
present in that context. This does not use the exact-substring
provenance check from earlier modules (a generated question
paraphrases naturally — "you mentioned leading a team" is a reasonable
paraphrase of stored evidence, not a fabrication) — the discipline
here is at the **prompt-construction level**: only real evidence ever
enters the prompt, not the free-form invention earlier modules guarded
against.

## Output — `GeneratedQuestion`

```json
{
  "question_id": string,
  "question_text": string,
  "question_type": "fresh" | "cross_question",
  "target_competency_id": string,
  "generation_method": "llm" | "fallback_template"
}
```

`question_id` is **not generated here** — it's carried through from
`reasoning_decision.question_id` (Module 8's output), preserving the
single-ID-lifecycle discipline established when Reasoning Engine was
built. `generation_method` records whether the LLM call succeeded or a
fallback template was used (see Error Contract) — internal-only,
useful for debugging generation failure rates, not shown to students.

## Responsibilities

- Deterministically classify `question_type` per the mapping above.
- Gather grounding context (real evidence excerpts) for cross-questions.
- Call the LLM to generate natural-language question text.
- Check the generated question against Conversation Memory's
  `has_asked_similar()` — if too similar to a prior question, retry
  generation **once**, then fall back to a template variation rather
  than looping indefinitely.
- Record the resulting turn in Conversation Memory via `record_turn()`,
  using the carried-through `question_id`.

## Explicit Non-Responsibilities

- Does not decide target competency or strategy — consumes
  `ReasoningDecision` as given, does not second-guess it.
- Does not evaluate answers — Evaluation Engine's job.
- Does not decide the interview's stopping condition.
- Does not generate a question for a `"stop"` decision — that's a
  contradiction in terms; see Error Contract.
- Does not fabricate specifics about what the candidate said — see
  Grounding Discipline above.
- Does not retry generation more than once before falling back to a
  template — avoids unbounded LLM calls if the model repeatedly
  produces near-duplicate phrasing.

## Error Contract

| Code | Meaning | Behavior |
|---|---|---|
| `INVALID_DECISION_TYPE` | `reasoning_decision.decision_type == "stop"` was passed in | Reject — raise. This module cannot meaningfully process a stop decision; calling it with one indicates an upstream orchestration bug |
| `GENERATION_FAILED` | LLM call fails or returns unparseable/empty output, on both the initial attempt and the one retry | Fall back to a templated question (see below) — recoverable, not a rejection, consistent with Resume/JD Understanding's `STRUCTURING_FAILED` and Evaluation Engine's `EVALUATION_FAILED` pattern. An interview cannot simply stop because generation failed once |
| `TURN_RECORDING_FAILED` | The call to `ConversationMemory.record_turn()` fails (e.g. `DUPLICATE_QUESTION_ID`, which should be unreachable given `question_id` uniqueness upstream, but surfaced rather than swallowed if it somehow occurs) | Reject — raise, surfacing the underlying Conversation Memory error |

**Fallback template behavior:** when `GENERATION_FAILED` is hit after
the retry, this module uses a simple, deterministic template based on
`reasoning_decision.evidence_missing` and `decision_strategy` (e.g.
"Can you tell me more about {competency_id}?" for `probe_deeper`,
generic enough to never be wrong, specific enough to keep the
interview moving). This is a genuinely worse question than an
LLM-generated one, but a working generic question beats no question at
all in a live pilot session.

## Acceptance Criteria

1. `probe_deeper` with zero existing evidence for the target
   competency produces `question_type: "fresh"`.
2. `probe_deeper` with existing evidence for the target competency
   produces `question_type: "cross_question"`.
3. `challenge_inconsistency`, `verify`, and `wrap_up_competency` all
   produce `question_type: "cross_question"` — tested for all three
   strategies, not just one representative case.
4. A `"stop"`-type `reasoning_decision` raises `INVALID_DECISION_TYPE`
   without attempting generation.
5. When the LLM call fails (mocked failure), the module falls back to
   a templated question rather than raising — `generation_method:
   "fallback_template"` in the result.
6. A cross-question's grounding context, as sent to the LLM, contains
   only real evidence excerpts fetched from Evidence Graph — verified
   by inspecting the actual prompt content sent to `classify_answer`-
   equivalent provider call, confirming no free-text summary is
   injected instead of real excerpts.
7. When a generated question is too similar to a recent question
   (per `has_asked_similar()`), the module retries once — verified by
   confirming exactly two provider calls occur in this scenario, not
   one and not unbounded.
8. After the one retry, if still too similar, the module falls back to
   a template rather than retrying again — verified by confirming
   provider call count stays at exactly two even when every attempt
   would be flagged similar.
9. A successful `generate_question()` call results in a real turn
   recorded in Conversation Memory, using the same `question_id` —
   verified by querying Conversation Memory directly afterward.
10. **End-to-end integration test**: a real `ReasoningDecision`
    produced by Module 8's actual `decide_next_action()` call (not
    hand-constructed) drives `generate_question()`, and the resulting
    turn is verified through Conversation Memory's own API — same
    integration standard as Modules 7 and 8's own AC10/AC12.
11. Two different `interview_id`s never see cross-contaminated
    grounding context or repetition checks — tested explicitly.

## Review Checklist (before merge)

- [ ] Schema matches this contract exactly
- [ ] All 3 Error Contract codes have test coverage
- [ ] Question-type mapping tested for every `decision_strategy` value
      the Reasoning Engine can actually produce (AC1-3)
- [ ] Grounding discipline verified by inspecting actual prompt
      content, not just trusting the LLM call happened (AC6)
- [ ] Retry-then-fallback behavior tested with an exact call-count
      assertion, not just "eventually returns something" (AC7-8)
- [ ] End-to-end integration with a real Reasoning Engine decision
      tested (AC10)
- [ ] `question_id` is carried through from `ReasoningDecision`, never
      independently generated in this module
- [ ] No `ProviderAdapter` SDK import outside the established
      abstraction
- [ ] `question_type`/`decision_strategy` import from
      `app.shared.types` per Decision #003
