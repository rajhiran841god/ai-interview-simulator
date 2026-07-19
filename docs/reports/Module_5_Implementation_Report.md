# Implementation Report — Module 5: Logging / Trace Recorder

**Third module with no external provider dependency and a full,
unqualified DoD. First module to import from the new `app.shared.types`
package (Decision #003).**

---

## 1. Files Created

```
backend/app/shared/__init__.py
backend/app/shared/types.py
backend/app/engine/logging/__init__.py
backend/app/engine/logging/schema.py
backend/app/engine/logging/store.py
backend/app/engine/logging/service.py
backend/tests/engine/logging/__init__.py
backend/tests/engine/logging/test_logging.py
```

## 2. Files Modified

None outside this module.

## 3. Public API

```python
from app.engine.logging.service import LoggingService

logger = LoggingService()
logger.record_trace(interview_id, question_id, decision_strategy, confidence_pre,
                     evidence_missing, reason_for_asking, prompt_version, model_version,
                     target_competency_id=None)
logger.update_trace_outcome(interview_id, question_id, confidence_post, evidence_ids_referenced)
logger.get_trace(interview_id, question_id)
logger.get_traces_for_interview(interview_id)
logger.get_traces_for_competency(interview_id, competency_id)
```

`app.shared.types` newly exposes `QuestionType`, `Relation`,
`DecisionStrategy` — the canonical home for these going forward, per
Decision #003. `QuestionType`/`Relation` are defined here matching
Modules 3/4's existing local definitions exactly, so a future retrofit
has an obvious, already-correct target — but Modules 3/4 themselves
were NOT touched.

## 4. External Libraries Introduced

None.

## 5. Design Decisions Made

- **Immutability via `model_copy`, not `frozen=False`.** My first
  draft of `TraceRecord` used `frozen=False` to make
  `update_trace_outcome` simple to implement — caught this myself
  before running tests, since it breaks the immutability pattern
  Conversation Memory and Evidence Graph both established (frozen
  model + replacement via `model_copy`, not in-place mutation).
  Corrected before any test was written against the wrong version.
- **Pydantic `ValidationError` translated into `LoggingError` with
  `CONFIDENCE_OUT_OF_RANGE`** at the service layer for `record_trace`,
  so callers only ever deal with this module's own error contract, not
  Pydantic internals leaking through. `update_trace_outcome` checks
  the bound directly before calling the store, for the same reason.
- **`OUTCOME_ALREADY_RECORDED` detected via `confidence_post is not
  None`** on the existing record, rather than a separate status field
  — simpler than introducing another enum, and correct given
  `confidence_post` has no other legitimate reason to be set once.

## 6. Real Bugs Found

**One ruff finding**, cosmetic — an unused `outcome` variable in the
full-lifecycle integration test. Fixed.

**No mypy findings this time** — worth noting directly: Modules 3 and
4 both had a real `str`-vs-`Literal` type error caught by mypy. Module
5, built with `DecisionStrategy` imported from the new shared
`app.shared.types` module from the start, had none. This is one data
point, not proof the pattern is fixed — but it's consistent with
Decision #003's hypothesis, and a test (`test_uses_shared_decision_strategy_type`)
explicitly confirms the field's type annotation traces back to the
shared module, not a local redefinition.

## 7. Contract Ambiguities Encountered

None requiring a stop-and-flag.

## 8. Acceptance Criteria Checklist

| # | Criterion | Status |
|---|---|---|
| 1 | Initial state correct | ✅ Pass |
| 2 | Update populates outcome fields | ✅ Pass |
| 3 | Duplicate question_id rejected | ✅ Pass |
| 4 | Update on nonexistent trace rejected | ✅ Pass |
| 5 | Double outcome update rejected, first preserved | ✅ Pass |
| 6 | Update cannot alter non-outcome fields | ✅ Pass |
| 7 | Empty interview returns empty list | ✅ Pass |
| 8 | Competency filtering | ✅ Pass |
| 9 | Interview isolation (merge blocker) | ✅ Pass |
| 10 | sequence_number monotonic, immutable | ✅ Pass |
| 11 | No full content duplicated (structural check) | ✅ Pass |
| 12 | confidence_pre out of range rejected, both directions | ✅ Pass |
| 13 | confidence_post out of range rejected | ✅ Pass |
| 14 | contract_version populated automatically | ✅ Pass |

**14/14, plus the full lifecycle integration test and the shared-type
usage test — 16 total, all passing.**

## 9. Test Summary

**18 new tests, all passing. Combined with Modules 1–4: 83 tests, 83
passing, actually executed.**

```
PYTHONPATH=. python -m pytest tests/engine/ -v
...
83 passed, 1 warning in 1.68s
```

## 10. Full Lifecycle Integration Test (per reviewer's specific request)

`test_full_lifecycle_record_then_update` exercises `record_trace()`
followed by `update_trace_outcome()` as a single sequence, then
re-fetches the record fresh via `get_trace()` to confirm both stages
persisted correctly together — not just that each function works in
isolation. This is the seam the reviewer flagged as highest-risk for
future bugs once Module 6 (Evaluation Engine) starts actually writing
outcomes; it passed cleanly on the first real run.

## 11. Tooling

```
black app/shared/ app/engine/logging/ tests/engine/logging/
  → 4 files reformatted (first run)

ruff check ... --fix
  → 1 real finding (unused variable), fixed

mypy app/shared/*.py app/engine/logging/*.py --ignore-missing-imports --follow-imports=silent
  → Success: no issues found in 6 source files (first clean mypy run
    across all five modules)
```

## 12. Known Limitations

- **`InMemoryTraceStore` is not persistent**, same caveat as
  Conversation Memory and Evidence Graph.
- **This module has no writers yet** — Evaluation Engine (Module 6)
  and Reasoning Engine (Module 8) are the intended callers of
  `record_trace`/`update_trace_outcome`, and neither exists yet. The
  API's usability by those future modules is a design bet, not yet
  proven by a real caller — same relationship Conversation Memory and
  Evidence Graph had before their eventual (and, so far, successful)
  integration.

## 13. Future Improvements (Not Implemented)

- Persistent `TraceStore` backend
- Aggregation/analytics over trace data (explicitly out of scope per
  the contract's Non-Responsibilities)

---

## Definition of Done — Self-Check

| Requirement | Met? |
|---|---|
| All Acceptance Criteria pass | ✅ 14/14 |
| No contract violations | ✅ |
| No TODO/FIXME comments | ✅ |
| Public interfaces documented | ✅ |
| Unit tests pass | ✅ (83/83 combined, actually run) |
| Type checking passes | ✅ (clean on first run) |
| Linting passes | ✅ (after 1 cosmetic fix) |
| Formatting passes | ✅ |
| Only documented public API exposed | ✅ |
| No functionality outside Logging added | ✅ |

**Honest verdict: full, unqualified 🟢 — third consecutive module in
this category.** Platform layer (Modules 1–5) is now complete per the
reviewer's framing. Next is Module 6, Evaluation Engine — the first
module in the "reasoning" family, and the first real test of whether
this module's API design actually works for a caller that wasn't
built alongside it.
