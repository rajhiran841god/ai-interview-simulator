# Implementation Report — Module 2: JD Understanding

**Built directly in this chat, same as Module 1. Tooling (black,
ruff, mypy) run this time, not retrofitted after review — applying
Module 1's lesson from the start.**

---

## 1. Files Created

```
backend/app/engine/shared/__init__.py
backend/app/engine/shared/validator.py       (extracted, shared with Resume Understanding)
backend/app/engine/jd/__init__.py
backend/app/engine/jd/schema.py
backend/app/engine/jd/structurer.py
backend/app/engine/jd/service.py
backend/tests/engine/jd/__init__.py
backend/tests/engine/jd/test_jd_understanding.py
backend/tests/fixtures_jd/marketing_jd.txt
backend/tests/fixtures_jd/finance_jd.txt
```

## 2. Files Modified

`app/engine/resume/validator.py` — converted to a thin re-export of
`app.engine.shared.validator`, per the reviewer's explicit
implementation requirement ("creating a second validator
implementation is considered a contract violation"). Existing imports
elsewhere in the Resume Understanding module keep working unchanged.
Reran all 22 Resume Understanding tests after this change — still
22/22 passing.

## 3. Public API

```python
from app.engine.jd.service import understand_jd

result = understand_jd(jd_text: str) -> JDUnderstandingOutput
```

Raises `RejectionError` only for `JD_TOO_LARGE` (the sole rejection-
tier error per the contract). All other conditions (`EMPTY_JD`,
`JD_TOO_SHORT`, `STRUCTURING_FAILED`) return a valid, mostly-absent
output object.

`app.engine.shared.validator` also newly exposes
`normalize_competency_id()`, used by JD Understanding and available to
any future module needing the same stable-ID derivation.

## 4. External Libraries Introduced

None new — reuses `anthropic` (via `ProviderAdapter`) already
established in Module 1.

## 5. Design Decisions Made Where the Contract Left Room for Judgment

- **`JD_TOO_LARGE` limit set to 20,000 characters, `JD_TOO_SHORT` to
  50 characters** — both implemented as module-level constants
  (`JD_TOO_LARGE_CHARS`, `JD_TOO_SHORT_CHARS`), not hardcoded inline,
  per the contract's "implementation configuration" language. **These
  are unvalidated placeholder values**, same status as Resume
  Understanding's 10MB file limit — flagged, not presented as derived
  from any real requirement.
- **Invalid `emphasis` values are dropped with a warning, not kept
  or defaulted** — the contract requires emphasis to be exactly
  `primary` or `secondary`; if the LLM structuring step ever produces
  something else, that competency is excluded entirely rather than
  guessing which category it belongs in. This mirrors the fail-closed
  philosophy of the provenance validator.
- **`competency_id` normalization** collapses hyphens and multiple
  spaces into single underscores and strips non-word characters,
  directly implementing the reviewer's flagged variants (`"Consumer
  Insight"`, `"Consumer-Insight"`, `"consumer insight"`, `"Consumer
  Insight"` with double space) — all four converge to
  `consumer_insight`, verified by test.

## 6. Contract Ambiguities Encountered

None significant — Contract v2 was specific enough to implement
directly, which is itself notable compared to Module 1's experience
(this is the benefit of the review cycle paying off, not a claim that
this contract is flawless).

## 7. Acceptance Criteria Checklist

| # | Criterion | Status |
|---|---|---|
| 1 | Output always matches schema | ✅ Pass |
| 2 | Stated values have provenance | ✅ Pass |
| 3 | Competencies traceable to JD text (fabrication rejected) | ✅ Pass |
| 4 | Valid emphasis tags + correct competency_id | ✅ Pass |
| 5 | Empty/short JD doesn't crash | ✅ Pass |
| 6 | Tested against 3+ real varied JDs, human-reviewed for fabrication | ⚠️ Partial — see Known Limitations |
| 7 | Every Error Contract code has test coverage | ✅ Pass — all 4 codes |
| 8 | No hardcoded competency vocabulary (marketing vs. finance produce disjoint sets) | ✅ Pass |

## 8. Test Summary

**15 new tests, all passing. Combined with Resume Understanding: 37
tests, 37 passing, actually executed.**

```
PYTHONPATH=. python -m pytest tests/engine/ -v
...
37 passed, 1 warning in 1.20s
```

Two real, distinct JD fixtures created (marketing role, finance role)
— genuinely different content, not variations of one template — used
specifically to test AC8's no-hardcoded-vocabulary requirement.

## 9. Tooling — Configured and Run From the Start This Time

```
black app/engine/jd/ app/engine/shared/ app/engine/resume/validator.py tests/engine/jd/
  → 6 files reformatted (first run on this new code)

ruff check ... --fix
  → All checks passed on first run — no findings this time
    (unlike Module 1, where a real unused import was caught)

mypy app/engine/jd/*.py app/engine/shared/*.py --ignore-missing-imports --follow-imports=silent
  → Success: no issues found in 6 source files
```

Applying Module 1's lesson: this is run now, not deferred to a later
review round.

## 10. Known Limitations

- **AC6 is only partially satisfied.** The contract requires "human
  reviewer" verification with "no fabricated competencies accepted."
  I generated the two JD fixtures and the *simulated* structured
  output myself (since there's no live LLM call — see below), so my
  own check that the fake data "looks reasonable" does not count as
  independent human review of real model output. **This needs your
  eyes on real model output once the live-LLM gap is closed** — the
  same blocker as Module 1.
- **No live LLM call has been made** — same explicit, structural gap
  as Resume Understanding, same reason (no API key available here).
  `structure_jd_text()` has never actually run. This is the more
  important of the two open items, since it's the step where
  fabrication risk lives and where the `role_specific_signals`
  exclusion rules (no "MBA preferred," no location) actually get
  tested against real model behavior, not simulated data.
- The `role_specific_signals` exclusion test
  (`test_role_specific_signals_excludes_qualifications_and_logistics`)
  explicitly notes in its own docstring that it validates the
  pipeline's *handling* of correctly-excluded data, not the live
  model's actual compliance with the exclusion instruction — that
  distinction matters and is easy to miss on a quick read.

## 11. Future Improvements (Not Implemented)

- `emphasis_reason` field (explicitly deferred per reviewer's "not now"
  recommendation)
- JD file upload/parsing (explicitly out of scope per the contract)

---

## Definition of Done — Self-Check

| Requirement | Met? |
|---|---|
| All 8 Acceptance Criteria pass | ⚠️ 7/8 fully, AC6 partial (same category of gap as Module 1) |
| No contract violations | ✅ |
| No TODO/FIXME comments | ✅ |
| Public interfaces documented | ✅ |
| Unit tests pass | ✅ (37/37 combined, actually run) |
| Type checking passes | ✅ |
| Linting passes | ✅ |
| Formatting passes | ✅ |
| Only documented public API exposed | ✅ |
| No functionality outside JD Understanding added | ✅ (validator extraction touched Resume Understanding, but only as a refactor explicitly required by this module's contract review — not scope creep) |

**Honest verdict: Module DoD is essentially met — 9/10 items clean,
tooling passes on first run this time.** The remaining gap (AC6 /
live LLM validation) is the same structural, credential-dependent item
carried over from Module 1, not a new problem. Per the "Module DoD vs.
deployment validation" distinction established in Module 1's review,
I'd call this **engineering-complete, integration-validation-pending**
— same honest category as Module 1, now batched together rather than
duplicated.
