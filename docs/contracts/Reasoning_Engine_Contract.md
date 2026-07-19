# Module Contract — Reasoning / Decision Engine

**Status:** Draft — pending review before implementation
**Milestone:** 3, Module 8 of 10 (see Milestone_2_Architecture.md Section 11)

**Note on module nature:** this is the module the entire project has
been building toward — the "core adaptive logic" (Milestone 2
Architecture Section 2.5). It makes no LLM calls itself (no
`ProviderAdapter` usage) — it decides *what* to ask about and *why*,
using only the deterministic state already produced by Competency
Model, Evidence Graph, and Logging. Question wording is explicitly
Question Generator's job (Module 9, not yet built) — this module
decides target and strategy, not phrasing.

**Honesty standard carried forward:** the strategy-selection heuristic
in this contract is a first-pass, explicitly-flagged pilot default —
same standard as Competency Model's update algorithm and the
Architecture's 6/18 question bounds. This is the single most
speculative piece of logic in the project so far, since it encodes
"what would a good interviewer do next" without any real interview
data to validate it against yet.

---

## Purpose

Each turn, decide whether the interview should continue or stop, and
if continuing, which competency to target next and what strategy to
use (per Milestone 2 Architecture Section 2.5's five decision
strategies: `probe_deeper`, `challenge_inconsistency`, `verify`,
`switch_competency`, `wrap_up_competency`). Implements the stopping
condition from Architecture Section 4 and the dynamic reasoning loop
from Architecture Section 3 (Layer 2).

This module owns the question's `question_id` — generated here and
passed forward to Question Generator and Conversation Memory, so a
single ID lifecycle threads through the whole turn (Logging trace →
eventual Conversation Memory turn → eventual Evidence Graph entries).

## Inputs

### `decide_next_action(interview_id)`

No other parameters — this module derives everything it needs by
querying Competency Model, Evidence Graph, and Logging directly, per
the same dependency-injection pattern established in Evaluation
Engine (Module 6).

| Field | Type | Required |
|---|---|---|
| interview_id | string | Yes |

## Output — `ReasoningDecision`

```json
{
  "question_id": string,
  "decision_type": "continue" | "stop",
  "target_competency_id": string | null,
  "decision_strategy": "probe_deeper" | "challenge_inconsistency" | "verify" | "switch_competency" | "wrap_up_competency" | null,
  "evidence_missing": string | null,
  "reason_for_asking": string | null,
  "stop_reason": string | null
}
```

`target_competency_id`, `decision_strategy`, `evidence_missing`,
`reason_for_asking` are populated only when `decision_type: "continue"`.
`stop_reason` is populated only when `decision_type: "stop"` — a
human-readable explanation (e.g. "Target confidence threshold reached
across all competencies" or "Maximum question count reached").

## Stopping Condition — Implements Architecture Section 4 Exactly

Uses the configurable values from `app.shared.reasoning_config`
(placeholders already anticipated there since Module 7's
implementation): `MIN_QUESTIONS` (pilot default 6), `MAX_QUESTIONS`
(pilot default 18), `STOP_CONFIDENCE_THRESHOLD` (pilot default 0.85),
`STOP_CONFIDENCE_FLOOR` (pilot default 0.60).

```
question_count = len(Logging.get_traces_for_interview(interview_id))

if question_count < MIN_QUESTIONS:
    decision_type = "continue"  # floor overrides everything else
elif question_count >= MAX_QUESTIONS:
    decision_type = "stop"      # ceiling overrides everything else
else:
    states = CompetencyModel.get_all_competency_states(interview_id)
    average_confidence = mean(s.confidence for s in states)
    minimum_confidence = min(s.confidence for s in states)
    if average_confidence >= STOP_CONFIDENCE_THRESHOLD
       and minimum_confidence >= STOP_CONFIDENCE_FLOOR:
        decision_type = "stop"
    else:
        decision_type = "continue"
```

`question_count` is derived from Logging's trace count, not a
separately maintained counter — Logging already records one trace per
Reasoning Engine decision, so it's the authoritative source, avoiding
a second, potentially-drifting counter.

## Strategy Selection Heuristic — Explicitly Flagged Pilot Default

**This is a first-pass heuristic, not a validated model of interviewer
behavior.** Stated in full so it's reviewable, not buried in code:

```
target = CompetencyModel.get_lowest_confidence_competency(interview_id)
target_state = CompetencyModel.get_competency_state(interview_id, target)

if EvidenceGraph.has_contradictions(interview_id, target):
    strategy = "challenge_inconsistency"
elif target_state.evidence_count == 0:
    strategy = "probe_deeper"       # no evidence yet — open the topic
elif target_state.confidence < STOP_CONFIDENCE_FLOOR:
    strategy = "probe_deeper"       # still insufficient — keep gathering
elif target_state.confidence < STOP_CONFIDENCE_THRESHOLD:
    strategy = "verify"             # borderline — needs confirmation
else:
    strategy = "wrap_up_competency" # already strong — edge case if still "lowest"
```

**`switch_competency` is not selected by this heuristic in v0.1.** The
contract acknowledges this strategy exists (per Architecture Section
2.5) but the current heuristic always targets the single
lowest-confidence competency rather than implementing logic for when
to deliberately move to a *different* competency than pure
lowest-confidence would suggest (e.g. to avoid several consecutive
questions on the same topic feeling repetitive). **This is a known,
stated gap, not an oversight** — a more sophisticated selection
policy is real future work, explicitly deferred rather than
half-implemented now.

`evidence_missing` and `reason_for_asking` are generated from a
template referencing the target competency and current state (e.g.
"No evidence yet collected for {competency_name}" / "This competency
has the lowest confidence ({confidence}) among all tracked
competencies") — **not LLM-generated** in this module, since this
module makes no provider calls. Question Generator (Module 9) is
responsible for turning this structured reasoning into natural
language question text.

## Responsibilities

- Evaluate the stopping condition exactly as specified above, every
  call.
- When continuing, select a target competency and strategy per the
  heuristic above.
- Generate the `question_id` for this turn.
- Write the reasoning trace via `Logging.record_trace()` — this
  module is Logging's actual first real writer for the pre-answer
  trace fields (Module 6 only ever wrote the post-answer outcome via
  `update_trace_outcome`).
- Return a `ReasoningDecision` for the caller (eventually an
  orchestrator, not yet built) to pass to Question Generator.

## Explicit Non-Responsibilities

- Does not generate question text or phrasing — Question Generator's
  job (Module 9).
- Does not call any LLM provider — this module is deterministic given
  its inputs (Competency Model, Evidence Graph, Logging state).
- Does not record the conversation turn itself — that remains
  Conversation Memory's job, called by whatever orchestrator sits
  above both this module and Question Generator.
- Does not evaluate answers — Evaluation Engine's job (Module 6,
  already built).
- Does not implement `switch_competency` selection logic — explicitly
  deferred, stated above.
- Does not decide feedback content — Feedback Generator's job (Module
  10, not yet built).

## Error Contract

| Code | Meaning | Behavior |
|---|---|---|
| `NO_COMPETENCIES_INITIALIZED` | `Competency Model` has no tracked competencies for this `interview_id` | Reject — raise. This module cannot make a targeting decision with nothing to target; indicates an upstream orchestration bug (Competency Model should have been initialized from JD Understanding before the interview loop starts) |
| `TRACE_WRITE_FAILED` | The call to `Logging.record_trace()` itself fails (e.g. `DUPLICATE_QUESTION_ID` if a `question_id` collision somehow occurs) | Reject — raise, surfacing the underlying Logging error rather than swallowing it |

Both are rejection errors — this module has no recoverable-degradation
tier, unlike Evaluation Engine. A reasoning decision either succeeds
cleanly or something upstream is broken and needs to be surfaced, not
papered over.

## Acceptance Criteria

1. `question_count < MIN_QUESTIONS` always produces `decision_type:
   "continue"`, regardless of how high current confidence is —
   tested with an artificially high-confidence state to confirm the
   floor genuinely overrides.
2. `question_count >= MAX_QUESTIONS` always produces `decision_type:
   "stop"`, regardless of how low current confidence is — tested with
   an artificially low-confidence state to confirm the ceiling
   genuinely overrides.
3. Between the floor and ceiling, stopping is correctly determined by
   the average/minimum confidence rule — tested with a case that
   should stop (average and minimum both above threshold) and a case
   that should continue (average high but one competency below the
   floor — confirming the minimum-confidence check isn't skipped just
   because the average looks good).
4. When continuing, `target_competency_id` always matches
   `CompetencyModel.get_lowest_confidence_competency()`'s result.
5. `challenge_inconsistency` is selected whenever
   `EvidenceGraph.has_contradictions()` is true for the target
   competency — tested by seeding a real contradiction through
   Evidence Graph (not a mock) and confirming the strategy follows.
6. `probe_deeper` is selected for a target competency with zero
   evidence.
7. `verify` is selected for a target competency with confidence
   between the floor and threshold.
8. A `question_id` is generated for every `"continue"` decision, is
   unique across calls, and is successfully used to write a Logging
   trace — verified by querying Logging directly afterward (same
   verify-through-the-real-API standard as Module 6's AC7).
9. `decide_next_action()` for an interview with no initialized
   competencies raises `NO_COMPETENCIES_INITIALIZED`.
10. **End-to-end integration test**: a real Competency Model state,
    built up through actual `update_from_evaluation()` calls (not
    hand-constructed), drives a `decide_next_action()` call, and the
    resulting decision is verified against that real state — same
    integration standard as Module 7's AC12.
11. Two different `interview_id`s never produce cross-contaminated
    decisions — tested explicitly, same isolation severity as every
    prior module.
12. `decide_next_action()` produces no side effects on Competency
    Model or Evidence Graph — it only reads from them and writes to
    Logging. Verified by confirming their state is byte-for-byte
    identical before and after a call (excluding Logging's own state,
    which is expected to change).

## Review Checklist (before merge)

- [ ] Schema matches this contract exactly
- [ ] Both Error Contract codes have test coverage
- [ ] Stopping condition tested at all three regions (below floor, in
      range, at/above ceiling) — AC1-3
- [ ] Strategy heuristic tested for each of the 4 implemented
      strategies (challenge_inconsistency, probe_deeper, verify,
      wrap_up_competency) — `switch_competency`'s absence is expected
      and should not be treated as a missing test
- [ ] `question_id` generation and Logging trace write verified
      end-to-end (AC8)
- [ ] Read-only guarantee on Competency Model / Evidence Graph tested
      explicitly (AC12) — this module must never mutate the state it
      reads
- [ ] Interview isolation tested (AC11)
- [ ] No `ProviderAdapter`, LLM, or embeddings import anywhere —
      deterministic only, same constraint as Conversation Memory,
      Evidence Graph, Logging
- [ ] All tunable thresholds imported from `app.shared.reasoning_config`,
      not hardcoded inline — this is the module those placeholders
      were anticipated for
