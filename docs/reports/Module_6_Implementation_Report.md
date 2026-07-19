# Implementation Report — Module 6: Evaluation Engine

**First module in the "reasoning" family. First real end-to-end
integration test spanning four modules (Conversation Memory, Evidence
Graph, Logging, Evaluation Engine) together. Has a live-LLM dependency,
same category as Resume/JD Understanding — will batch with those for
live-API validation once unblocked.**

---

## 1. Files Created

```
backend/app/engine/evaluation/__init__.py
backend/app/engine/evaluation/schema.py
backend/app/engine/evaluation/classifier.py
backend/app/engine/evaluation/service.py
backend/tests/engine/evaluation/__init__.py
backend/tests/engine/evaluation/test_evaluation_engine.py
```

## 2. Files Modified

`app/shared/types.py` — added `AnswerClassification` alongside the
existing `QuestionType`, `Relation`, `DecisionStrategy`, per Decision
#003's established pattern. No modification to Modules 1-5's own code.

## 3. Public API

```python
from app.engine.evaluation.service import EvaluationEngineService

ee = EvaluationEngineService(evidence_graph=eg, logging_service=logging_svc)
result = ee.evaluate_answer(interview_id, question_id, turn_id, evidence_missing,
                              answer_text, target_competency_id=None)
```

Implemented as the discrete pipeline the reviewer recommended: input
validation, provider call (`classifier.py`), response parsing,
confidence domain validation (reject-not-clamp), evidence extraction,
Evidence Graph writes, Logging update, result assembly — each a
distinct, separately-reasoned-about step in `service.py`, not one
undifferentiated function.

## 4. External Libraries Introduced

None new — reuses `anthropic` via the existing `ProviderAdapter`.

## 5. Design Decisions Made

- **The `EMPTY_ANSWER` and `EVALUATION_FAILED` and
  `CONFIDENCE_OUT_OF_RANGE` paths all converge on the same
  `degraded_result()` helper** — one consistent shape for every
  recoverable failure, rather than three slightly different degraded
  results. Simplifies both the implementation and what a caller needs
  to handle.
- **Contradiction handling only ever targets `prior_evidence[0]`** in
  this implementation — a real simplification worth being explicit
  about. The contract doesn't specify *which* prior evidence entry a
  new contradiction should target when multiple exist; picking the
  first one is a reasonable v0.1 default, but a more sophisticated
  approach (e.g. asking the LLM which specific prior evidence is being
  contradicted) is a real future improvement, not implemented here.
- **A broad `except Exception` around each individual evidence-write
  attempt** (Evidence Graph's `add_evidence` call) — deliberately
  broad, not narrowed to `EvidenceGraphError` specifically, because
  the contract's AC10 requires that ANY failure to write a specific
  evidence entry gets dropped gracefully, not just the expected
  `EXCERPT_NOT_TRACEABLE` case. This is a considered choice, not
  carelessness — flagging it because "except Exception" is usually a
  smell, and here it's deliberate.

## 6. Real Bugs Found

**One ruff finding**, auto-fixed by `--fix` — did not require manual
inspection to confirm safety (checked the diff after the fact; it was
a genuinely cosmetic fix).

**No mypy findings** — third consecutive module with zero mypy issues
since `app.shared.types` came into use (Modules 5 and 6 both clean;
Modules 3 and 4, built before the shared types package existed, both
had real findings). This is now a reasonably strong pattern, not just
a hopeful one.

**No test-design bugs this time** (unlike Module 3's two and Module
4's one) — possibly because this test suite was built with real
end-to-end wiring from the start (the `wired_system` fixture) rather
than constructed and then debugged into that shape.

## 7. Contract Ambiguities Encountered

One, documented in Section 5: which prior evidence entry a
contradiction targets when multiple exist for a competency. Resolved
pragmatically (first entry) rather than over-engineering a v0.1
solution to a case that may not come up often in a single-pass pilot
interview.

## 8. Acceptance Criteria Checklist

| # | Criterion | Status |
|---|---|---|
| 1 | Substantive answer → traceable evidence | ✅ Pass |
| 2 | Deflection vs. non-answer distinguished | ✅ Pass |
| 3 | Empty answer skips LLM call | ✅ Pass |
| 4 | LLM failure handled gracefully | ✅ Pass |
| 5 | Contradiction written end-to-end through Evidence Graph | ✅ Pass |
| 6 | No trace → TRACE_NOT_FOUND | ✅ Pass |
| 7 | Logging updated, verified via fresh query | ✅ Pass |
| 8 | Out-of-range confidence rejected, never clamped | ✅ Pass |
| 9 | Null competency → no evidence writes, no raise | ✅ Pass |
| 10 | Fabricated evidence never bypasses Evidence Graph's check | ✅ Pass |
| 11 | Orchestration deterministic given fixed mocked response | ✅ Pass |
| 12 | Contradiction detection never crosses interviews | ✅ Pass |

**12/12, plus a provider-isolation check — 13 total, all passing.**

## 9. Test Summary

**13 new tests, all passing. Combined with Modules 1–5: 96 tests, 96
passing, actually executed.**

```
PYTHONPATH=. python -m pytest tests/engine/ -v
...
96 passed, 1 warning in 1.11s
```

## 10. End-to-End Integration (four modules together)

The `wired_system` fixture constructs real instances of Conversation
Memory, Evidence Graph, and Logging, wired together exactly as they'd
be used in practice, and Evaluation Engine on top of all three. Every
test in this suite (except the provider-isolation check) exercises
this real integration — turns are actually recorded, traces are
actually logged, evidence is actually written and read back through
each module's own public API, not mocked at the module boundary. Only
the LLM call itself is mocked. This is the deepest integration test in
the project so far, spanning four modules rather than two (Module 4's
precedent).

## 11. Tooling

```
black app/engine/evaluation/ tests/engine/evaluation/ app/shared/types.py
  → 4 files reformatted (first run)

ruff check ... --fix
  → 1 finding, auto-fixed, confirmed cosmetic

mypy app/engine/evaluation/*.py --ignore-missing-imports --follow-imports=silent
  → Success: no issues found in 4 source files (clean on first run)
```

## 12. Known Limitations

- **No live LLM call has been made.** Same structural gap as Resume/JD
  Understanding — `classify_answer()` has never called the real
  Anthropic API. This is arguably the highest-stakes untested LLM call
  in the project so far, since it's the first one making a judgment
  (classification) rather than pure extraction — worth prioritizing
  once the billing issue clears.
- **Contradiction targeting picks the first prior evidence entry**,
  not necessarily the most relevant one when multiple exist (Section 5).
- **The `deflection` vs. `non_answer` distinction is entirely
  LLM-dependent** — the mocked tests prove the orchestration code
  correctly *handles* both classifications when told which is which,
  but say nothing about whether a real model reliably tells them
  apart. This is exactly the kind of thing only the live-API
  validation can actually test.

## 13. Future Improvements (Not Implemented)

- Smarter contradiction targeting (LLM-assisted disambiguation among
  multiple prior evidence entries)
- Structured logging of dropped/fabricated evidence attempts (AC10
  currently drops silently at the result level; a `parse_warnings`-
  style field, consistent with earlier modules, could make this more
  visible for debugging)

---

## Definition of Done — Self-Check

| Requirement | Met? |
|---|---|
| All Acceptance Criteria pass | ✅ 12/12 |
| No contract violations | ✅ |
| No TODO/FIXME comments | ✅ |
| Public interfaces documented | ✅ |
| Unit tests pass | ✅ (96/96 combined, actually run) |
| Type checking passes | ✅ (clean on first run) |
| Linting passes | ✅ (after 1 auto-fix) |
| Formatting passes | ✅ |
| Only documented public API exposed | ✅ |
| No functionality outside Evaluation Engine added (except the shared types addition, explicitly noted) | ✅ |

**Honest verdict: engineering-complete, live-API validation pending —
same category as Resume/JD Understanding, now three modules sharing
that one outstanding gap.** Unlike those two modules, this one's
untested LLM behavior (reliable classification, not just structured
extraction) is a meaningfully higher-stakes unknown — worth flagging
as the top priority once the Anthropic billing issue is resolved.
