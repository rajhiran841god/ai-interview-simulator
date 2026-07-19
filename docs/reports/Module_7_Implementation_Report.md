# Implementation Report — Module 7: Competency Model / Confidence Tracker

**First module built around an algorithm rather than a storage
pattern. Zero tooling findings on the first pass — fourth consecutive
clean mypy run since app.shared.types came into use. First test suite
to integrate five modules together in one end-to-end test (AC12).**

---

## 1. Files Created

```
backend/app/shared/reasoning_config.py
backend/app/engine/competency_model/__init__.py
backend/app/engine/competency_model/schema.py
backend/app/engine/competency_model/store.py
backend/app/engine/competency_model/service.py
backend/tests/engine/competency_model/__init__.py
backend/tests/engine/competency_model/test_competency_model.py
```

## 2. Files Modified

`app/shared/types.py` — added `Emphasis`, per the established pattern
(Decision #003). No modification to Modules 1-6's own code.

## 3. Public API

```python
from app.engine.competency_model.service import CompetencyModelService

cmodel = CompetencyModelService()
cmodel.initialize_competencies(interview_id, [CompetencySeed(...), ...])
cmodel.update_from_evaluation(interview_id, competency_id, confidence_contribution,
                                contradiction_detected, evidence_ids_created)
cmodel.get_competency_state(interview_id, competency_id)
cmodel.get_all_competency_states(interview_id)
cmodel.get_lowest_confidence_competency(interview_id)
```

`app.shared.reasoning_config` is new — the centralized tunable-
parameter location the reviewer recommended, ahead of Module 8's
thresholds, with those anticipated (commented, not yet used) as a
placeholder for where they'll go.

## 4. External Libraries Introduced

None.

## 5. Design Decisions Made

- **Update algorithm implemented exactly as specified in the
  contract** — no deviation. `store.py`'s `update()` method is a
  direct translation of the documented formulas, with the formulas
  quoted in code comments so a future reader can check implementation
  against contract without cross-referencing two documents.
- **Division-by-zero guard added** for the no-contradiction path: if
  `evidence_ids_created` is empty (e.g. a `substantive`-adjacent
  answer that somehow produced no extractable evidence — an edge case
  the contract doesn't explicitly address), confidence is left
  unchanged rather than dividing by the current `evidence_count`
  (which could be the pre-update count of 0, causing a crash). This
  wasn't explicitly specified in the contract; flagging it as a
  reasonable implementation-time judgment call, not a silent contract
  deviation.
- **`CompetencyState` is not frozen** (unlike `TurnRecord` and
  `EvidenceEntry`), since it's genuinely a live, evolving belief state,
  not an immutable historical record — a deliberate difference from
  the immutability pattern established in Modules 3-4-5, stated here
  so it doesn't look like an oversight.

## 6. Real Bugs Found

**None this time** — zero ruff findings, zero mypy findings, on the
first tooling pass. This is the first module in the project with a
completely clean tooling run with no fixes required. Worth noting as a
data point, not over-claiming: this module's logic is genuinely
simpler in surface area (a handful of storage operations plus one
well-specified formula) than, say, Evaluation Engine's LLM
orchestration, so a clean run here is less surprising than it would be
for a more complex module.

## 7. Contract Ambiguities Encountered

One, documented in Section 5: the contract's formula doesn't explicitly
address the zero-evidence edge case on the no-contradiction path.
Resolved by leaving confidence unchanged in that case, which seems the
only sensible behavior, but flagging that the contract itself doesn't
state this explicitly.

## 8. Acceptance Criteria Checklist

| # | Criterion | Status |
|---|---|---|
| 1 | Initial state correct | ✅ Pass |
| 2 | First update equals contribution exactly | ✅ Pass |
| 3 | Second update — correct incremental mean, verified against exact expected value | ✅ Pass |
| 4 | Contradiction penalty applied and floored at 0.0 | ✅ Pass |
| 5 | Evidence routed to correct list | ✅ Pass |
| 6 | Uninitialized competency rejected | ✅ Pass |
| 7 | Duplicate initialization rejected | ✅ Pass |
| 8 | Out-of-range confidence rejected, not clamped | ✅ Pass |
| 9 | Lowest-confidence competency correctly identified | ✅ Pass |
| 10 | None returned for uninitialized interview | ✅ Pass |
| 11 | Interview isolation | ✅ Pass |
| 12 | End-to-end integration using a REAL EvaluationResult from Module 6 | ✅ Pass |

**12/12, plus a configuration check confirming `CONTRADICTION_PENALTY`
is imported from the shared config, not redefined locally — 13 total,
all passing.**

## 9. Test Summary

**14 new tests, all passing. Combined with Modules 1–6: 110 tests, 110
passing, actually executed.**

```
PYTHONPATH=. python -m pytest tests/engine/ -v
...
110 passed, 1 warning in 1.27s
```

**Float comparisons use `pytest.approx()` throughout**, per the
reviewer's explicit instruction — no direct equality checks on
computed confidence values, since the incremental-mean formula
involves division that may not be exactly representable in floating
point.

## 10. End-to-End Integration (AC12, five modules)

`test_ac12_end_to_end_integration_with_real_evaluation_engine` wires
together Conversation Memory, Evidence Graph, Logging, Evaluation
Engine, and Competency Model — records a real turn, evaluates a real
answer (only the LLM call itself mocked), and feeds the actual
`EvaluationResult` object directly into `update_from_evaluation()`,
rather than constructing a hand-made stand-in. This is the deepest
integration test in the project so far, and it passed on the first
real run — a good signal that the module boundaries established across
Modules 3-7 are genuinely compatible in practice, not just individually
correct.

## 11. Tooling

```
black app/engine/competency_model/ tests/engine/competency_model/ app/shared/reasoning_config.py app/shared/types.py
  → 4 files reformatted (first run)

ruff check ... --fix
  → All checks passed, no findings

mypy app/engine/competency_model/*.py --ignore-missing-imports --follow-imports=silent
  → Success: no issues found in 4 source files
```

## 12. Known Limitations

- **`InMemoryCompetencyModelStore` is not persistent**, same caveat as
  every prior storage module.
- **The update algorithm is an explicitly-flagged pilot default**, not
  validated against real interview data — `CONTRADICTION_PENALTY =
  0.3` and the incremental-mean approach are the project's current
  best guess, stated as such in the contract, and should be revisited
  once real pilot confidence trajectories can be inspected.
- **The reviewer's suggested future separation of `confidence` from
  `consistency`** (tracking internal contradiction rate as a distinct
  signal from overall evidence strength) was explicitly deferred per
  their own recommendation — noted here so it isn't lost, not
  implemented.

## 13. Future Improvements (Not Implemented)

- Persistent `CompetencyModelStore` backend
- Separating `confidence` from a distinct `consistency` signal (per
  reviewer's explicit "not for this contract" suggestion)
- Tuning `CONTRADICTION_PENALTY` and the incremental-mean weighting
  once real pilot data exists

---

## Definition of Done — Self-Check

| Requirement | Met? |
|---|---|
| All Acceptance Criteria pass | ✅ 12/12 |
| No contract violations | ✅ |
| No TODO/FIXME comments | ✅ |
| Public interfaces documented | ✅ |
| Unit tests pass | ✅ (110/110 combined, actually run) |
| Type checking passes | ✅ (clean on first run) |
| Linting passes | ✅ (clean on first run) |
| Formatting passes | ✅ |
| Only documented public API exposed | ✅ |
| No functionality outside Competency Model added (except the shared config/types additions, explicitly noted) | ✅ |

**Honest verdict: full, unqualified 🟢 — fourth module in this
category (joining Conversation Memory, Evidence Graph, Logging), and
the first "reasoning family" module with no provider dependency of its
own.** This module consumes Evaluation Engine's output but makes no
LLM calls itself, so it has no live-API validation gap — only the
underlying algorithm's real-world tuning remains genuinely open, and
that requires pilot data, not an API key.
