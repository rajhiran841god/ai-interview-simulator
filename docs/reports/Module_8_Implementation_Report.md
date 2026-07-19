# Implementation Report — Module 8: Reasoning / Decision Engine

**The core adaptive logic the entire project has been building toward.
Highest architectural risk module so far, per the reviewer's own
framing. Implemented as three isolated, independently-testable
components (StoppingPolicy, StrategyPolicy, DecisionAssembler) per
explicit reviewer recommendation.**

---

## 1. Files Created

```
backend/app/engine/reasoning/__init__.py
backend/app/engine/reasoning/schema.py
backend/app/engine/reasoning/stopping_policy.py
backend/app/engine/reasoning/strategy_policy.py
backend/app/engine/reasoning/service.py
backend/tests/engine/reasoning/__init__.py
backend/tests/engine/reasoning/test_reasoning_engine.py
```

## 2. Files Modified

`app/shared/reasoning_config.py` — activated the `MIN_QUESTIONS`,
`MAX_QUESTIONS`, `STOP_CONFIDENCE_THRESHOLD`, `STOP_CONFIDENCE_FLOOR`
placeholders that were anticipated (commented out) during Module 7's
implementation. This is exactly the payoff the centralization
recommendation was made for — no new file needed, no scattered
constants, just uncommenting values that already had an obvious home.

## 3. Public API

```python
from app.engine.reasoning.service import ReasoningEngineService

reasoning = ReasoningEngineService(competency_model=cm, evidence_graph=eg, logging_service=logging_svc)
decision = reasoning.decide_next_action(interview_id)
```

Internally structured exactly as the reviewer recommended:
- `stopping_policy.py` — `evaluate_stopping_condition()`, isolated and
  independently testable.
- `strategy_policy.py` — `select_strategy()`, isolated, contains the
  single most speculative logic in the project (explicitly labeled as
  such in the module's own docstring).
- `service.py` — the DecisionAssembler role: pulls both policies
  together, generates `question_id`, writes the Logging trace, returns
  the final `ReasoningDecision`.

This means a future replacement of the targeting heuristic (e.g.
"expected information gain" instead of lowest-confidence, as the
reviewer suggested as a future direction) only touches
`strategy_policy.py` — nothing else in this module or any other module
needs to change.

## 4. External Libraries Introduced

None. Zero LLM/provider dependency — confirmed no `ProviderAdapter`
import anywhere in this module.

## 5. Design Decisions Made

- **`switch_competency` genuinely not implemented**, not
  half-implemented. `strategy_policy.py`'s docstring states this
  directly. The reviewer's guidance to resist a shallow
  "N-consecutive-questions" version rather than a real policy was
  followed — there is no code path that ever selects this strategy in
  v0.1.
- **A `stop` decision still generates a `question_id`** (required by
  the schema) but does not write a Logging trace — only `continue`
  decisions correspond to an actual question being asked, so only
  those get logged. This wasn't explicitly stated as a rule in the
  contract; documenting it here as the implementation's resolution of
  that gap.
- **Defensive `None` guards added** around
  `get_lowest_confidence_competency()`'s and
  `get_competency_state()`'s return values, even though both should be
  logically unreachable given the prior non-empty-states check — see
  Section 6, this is where mypy caught a real gap between "should
  never happen" and "is actually guaranteed by the type system."

## 6. Real Bugs Found

**One real mypy finding, the most significant type-safety catch in
the project so far**: `get_lowest_confidence_competency()` returns
`Optional[str]`, and the original code passed its result directly into
three subsequent calls (`get_competency_state`, `has_contradictions`,
`select_strategy`) that all require a non-`None` `str`. The code
*would* have worked correctly at runtime in every test scenario, since
`states` was already confirmed non-empty — but mypy correctly flagged
that nothing in the code actually *proved* the lowest-confidence
lookup couldn't still return `None` (e.g. if `CompetencyModelService`'s
internal logic ever changed). Fixed with explicit guards that raise a
clear, diagnosable error rather than crash with an `AttributeError` on
`None` several calls downstream — the same "unreachable but not
provably so" gap this project's tooling has now caught multiple times
across different modules (Module 3, Module 4, and now this one, though
this one is the most consequential given how central this module is).

**Two ruff findings**, both auto-fixed, confirmed cosmetic on review.

## 7. Contract Ambiguities Encountered

One, documented in Section 5: whether `stop` decisions write a Logging
trace. Resolved as "no" — only actual questions get logged, which
seems the only sensible reading, but the contract itself doesn't say
this explicitly.

## 8. Acceptance Criteria Checklist

| # | Criterion | Status |
|---|---|---|
| 1 | Min-questions floor overrides high confidence | ✅ Pass |
| 2 | Max-questions ceiling overrides low confidence | ✅ Pass |
| 3 | High average + one weak competency still continues (the case developers most commonly get wrong) | ✅ Pass |
| 4 | Target matches lowest-confidence competency | ✅ Pass |
| 5 | Contradiction selects challenge_inconsistency, tested via real Evidence Graph seeding | ✅ Pass |
| 6 | probe_deeper for zero evidence | ✅ Pass |
| 7 | verify for borderline confidence | ✅ Pass |
| 8 | question_id generated, unique, logged, verified via fresh query | ✅ Pass |
| 9 | No competencies initialized raises | ✅ Pass |
| 10 | End-to-end integration with REAL Competency Model state | ✅ Pass |
| 11 | Interview isolation | ✅ Pass |
| 12 | Read-only guarantee on Competency Model and Evidence Graph | ✅ Pass |

**12/12, plus a determinism test and a threshold-centralization test —
14 total, all passing.**

## 9. Test Summary

**15 new tests, all passing. Combined with Modules 1–7: 125 tests, 125
passing, actually executed.**

```
PYTHONPATH=. python -m pytest tests/engine/ -v
...
125 passed, 1 warning in 1.22s
```

## 10. Read-Only Guarantee (AC12) — How It Was Actually Verified

`test_ac12_read_only_on_competency_model_and_evidence_graph` takes a
deep copy of Competency Model's and Evidence Graph's state before
calling `decide_next_action()`, then compares against the state
after — asserting byte-for-byte equality. This is the test the
reviewer said they'd want kept permanently, and it's written to fail
loudly (a plain equality assertion, not a narrower "did the confidence
number change" check) so any future accidental mutation of upstream
state — not just the specific field someone might think to check —
gets caught.

## 11. Determinism (explicitly checked, not just assumed)

`test_decision_determinism_given_identical_state` builds two fully
independent systems with identical seeded state and confirms both
produce the same `decision_type`, `target_competency_id`, and
`decision_strategy` (excluding the intentionally-unique `question_id`).
This directly verifies the reviewer's first stated review focus:
"identical state should always produce identical decisions."

## 12. Tooling

```
black app/engine/reasoning/ tests/engine/reasoning/ app/shared/reasoning_config.py
  → 5 files reformatted (first run)

ruff check ... --fix
  → 2 findings, auto-fixed, confirmed cosmetic

mypy app/engine/reasoning/*.py --ignore-missing-imports --follow-imports=silent
  → 6 real findings on first run (Section 6) — all traced to the same
    root cause (an unguarded Optional), fixed with explicit None
    checks
  → Success: no issues found in 5 source files, after fix
```

## 13. Known Limitations

- **`switch_competency` is entirely unimplemented** — stated
  repeatedly and explicitly rather than buried; this is the known,
  intentional gap the contract flagged from the start.
- **The strategy heuristic is an unvalidated pilot default** — same
  honesty standard as Competency Model's update algorithm. Priority
  ordering (contradiction > no evidence > below floor > borderline >
  wrap up) is defensible reasoning, per the reviewer, but has never
  been checked against a real interview transcript.
- **`InMemory*Store` backends throughout the dependency chain are not
  persistent** — same caveat carried through every storage-backed
  module in the project.

## 14. Future Improvements (Not Implemented)

- Real `switch_competency` policy (diminishing returns, pacing,
  question budget, per reviewer's explicit list of what a proper
  version should consider)
- Alternative `StrategyPolicy` implementations (e.g. expected
  information gain) — the isolation work done in this module makes
  this a contained future change, per its explicit design goal

---

## Definition of Done — Self-Check

| Requirement | Met? |
|---|---|
| All Acceptance Criteria pass | ✅ 12/12 |
| No contract violations | ✅ |
| No TODO/FIXME comments | ✅ |
| Public interfaces documented | ✅ |
| Unit tests pass | ✅ (125/125 combined, actually run) |
| Type checking passes | ✅ (after fixing 6 real findings, all one root cause) |
| Linting passes | ✅ (after 2 cosmetic auto-fixes) |
| Formatting passes | ✅ |
| Only documented public API exposed | ✅ |
| No functionality outside Reasoning Engine added (except activating the pre-anticipated config constants, explicitly noted) | ✅ |

**Honest verdict: full, unqualified 🟢 — sixth module in this category,
and the most architecturally significant one to reach it.** No
provider dependency, so nothing here waits on the Anthropic billing
issue — but this module's real value can't be fully assessed until
Question Generator and Feedback Generator exist and the full interview
loop can actually run end-to-end, which is a different kind of
validation than any single module's test suite can provide alone.
