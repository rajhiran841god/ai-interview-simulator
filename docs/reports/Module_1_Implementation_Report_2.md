# Implementation Report — Module 1: Resume Understanding (Revision 2)

**Source of truth:** `docs/contracts/Resume_Understanding_Contract_3.md`
(no other version referenced anywhere in this module's code or tests).

**Revision 2 changes, made directly in response to reviewer feedback:**
1. Replaced `source_location="unspecified"` with real coarse section
   labels ("Education", "Work Experience", "Personal Summary",
   "Skills", "Certifications", "Achievements", "Projects") — both from
   the LLM structuring step (prompted to supply them) and as a
   guaranteed fallback in the validator if the model omits one.
2. `validate_value()` now returns a structured `ValidationResult`
   (`accepted`, `value`, `warnings`) instead of silently mutating a
   dict — implements the reviewer's architectural suggestion directly.
3. Added real, non-mocked integration tests against the actual PDF and
   DOCX fixture files.
4. Completed AC8: generated a real password-protected PDF and a real
   corrupted file, and tested both. **This caught two real bugs**
   (Section 6 below) that mocked tests had not and could not catch.

---

## 1. Files Created (cumulative, including Revision 2)

```
backend/app/core/provider_adapter.py
backend/app/engine/__init__.py
backend/app/engine/resume/__init__.py
backend/app/engine/resume/schema.py
backend/app/engine/resume/extractors.py
backend/app/engine/resume/structurer.py
backend/app/engine/resume/validator.py
backend/app/engine/resume/service.py
backend/tests/engine/__init__.py
backend/tests/engine/resume/__init__.py
backend/tests/engine/resume/test_resume_understanding.py
backend/tests/fixtures_real_pdf.pdf
backend/tests/fixtures_real_docx.docx
backend/tests/fixtures_corrupted.pdf
backend/tests/fixtures_password_protected.pdf
```

## 2. Files Modified in Revision 2

- `validator.py` — rewritten to return `ValidationResult`, real
  section labels instead of "unspecified"
- `service.py` — updated to consume `ValidationResult`, pass real
  fallback location labels per field
- `structurer.py` — prompt updated to request `source_location` per
  extracted value
- `extractors.py` — **two real bugs fixed** (Section 6)
- `test_resume_understanding.py` — added real-file integration tests,
  completed AC8 coverage, fixed existing mocked tests for the new
  `validate_value` signature

## 3. Public API

Unchanged: `understand_resume(file_bytes: bytes, file_format: str) ->
ResumeUnderstandingOutput`. `ValidationResult` is an internal type
(used by `validate_value`, not exposed outside the `resume` package).

## 4. External Libraries Introduced

Same as Revision 1 (`pdfplumber`, `python-docx`, `anthropic`), plus
`pypdf` and `reportlab` — **test-only dependencies**, used to generate
the real fixture files (password-protected PDF, blank PDF). Not
required at runtime; should be added to a test-only requirements file,
not the main `requirements.txt`, before merge.

## 5. Design Decisions Made Where the Contract Left Room for Judgment

- **Coarse `source_location` granularity:** implemented as section-name
  labels (e.g. "Work Experience"), not character offsets or page
  numbers, per reviewer's explicit suggestion that this is sufficient
  for v0.1 and doesn't require token-offset tracking.
- **`ValidationResult` as a dataclass**, not a Pydantic model — it's
  purely internal to the validation step and never serialized, so a
  lighter-weight dataclass was chosen over adding another schema type.

## 6. Real Bugs Found and Fixed (via real-file testing, not mocks)

**Bug 1 — `is_encrypted` attribute does not exist.** Original code
checked `pdf.is_encrypted` on a `pdfplumber` PDF object. This attribute
does not exist on the actual object (confirmed via `dir()` on a real
opened PDF) — every real PDF upload would have crashed with an
`AttributeError` before ever reaching the "is this encrypted" check it
was trying to perform. Fixed by removing the check and instead
catching the actual exception pdfplumber/pdfminer raise.

**Bug 2 — password detection via `str(exception)` silently fails.**
First fix attempt checked `"password" in str(e).lower()`. Tested
against a real password-protected PDF (generated with `pypdf`) and
found `str(e)` is an **empty string** for pdfminer's
`PDFPasswordIncorrect` exception — the check never matched, and every
real password-protected PDF was misclassified as `CORRUPTED_FILE`
instead of `PASSWORD_PROTECTED`. Fixed by checking
`f"{type(e).__name__} {repr(e)}"` instead, which reliably contains
"password". Verified against the real encrypted fixture — now
correctly returns `PASSWORD_PROTECTED`.

Both bugs would have shipped silently if only mocked tests were run,
since mocks don't exercise the real library's actual exception
behavior. This is the concrete argument for why the reviewer's
integration-test requirement mattered, not a hypothetical one.

## 7. Contract Ambiguities Encountered

Same as Revision 1 — file size limit (10MB) remains an unconfirmed
placeholder; no other genuine ambiguities found.

## 8. Acceptance Criteria Checklist

| # | Criterion | Status |
|---|---|---|
| 1 | Accepts pdf/docx, rejects others with clear error | ✅ Pass |
| 2 | Output always matches schema, no missing mandatory keys | ✅ Pass |
| 3 | Stated values have source_text/source_location (real labels, not "unspecified"); absent values don't | ✅ Pass |
| 4 | Missing sections are empty arrays, not omitted/fabricated | ✅ Pass |
| 5 | Probe-worthy claims correctly flagged | ✅ Pass |
| 6 | Sparse/malformed resume doesn't crash, returns valid object | ✅ Pass |
| 7 | Automated provenance check (no fabrication, no fuzzy matching) | ✅ Pass |
| 8 | Every Error Contract code has test coverage | ✅ **Now Pass** — all 6 codes tested, 5 against real files |

## 9. Test Summary

**22 tests, 22 passed, 0 failed.** Up from 14 in Revision 1. New tests:
2 real integration tests (PDF/DOCX extraction, no mocking), 2 new
validator-behavior tests, 4 additional AC8 tests against real
generated files (corrupted, password-protected, blank/empty).

```
PYTHONPATH=. python -m pytest tests/engine/resume/ -v
...
22 passed, 1 warning in 0.95s
```

One test (`test_ac8_empty_document_real_pdf`) initially failed due to
a bug in the *test itself* (leftover dead code from editing, not an
implementation bug) — fixed and reran; noting this for transparency
rather than omitting it.

## 10. Known Limitations (Updated)

- **Still not tested against a live LLM call.** This remains the
  single most important open gap — `structure_resume_text()` has never
  called the real Anthropic API. No amount of extraction-layer testing
  substitutes for this; it's the step where fabrication risk actually
  lives.
- **`pypdf`/`reportlab` are test-only dependencies** not yet separated
  into a test-specific requirements file — minor packaging cleanup
  needed before merge.
- Linting/formatting/type-checking still not run — tooling not yet
  configured in the project (unchanged from Revision 1).
- File size limit (10MB) remains an unconfirmed placeholder.

## 11. Future Improvements (Not Implemented)

Unchanged from Revision 1 — OCR support, real span-based
`source_location` (beyond coarse section labels), a configured
linting/type-checking pipeline.

---

## Definition of Done — Self-Check (Revision 2)

| Requirement | Met? |
|---|---|
| All 8 Acceptance Criteria pass | ✅ **8/8 now**, up from 7/8 |
| No contract violations | ✅ |
| No TODO/FIXME comments | ✅ |
| Public interfaces documented | ✅ |
| Unit tests pass | ✅ (22/22, actually run) |
| Type checking passes | ❌ Not run — not yet configured |
| Linting passes | ❌ Not run — not yet configured |
| Formatting passes | ❌ Not run — not yet configured |
| Only documented public API exposed | ✅ |
| No functionality outside Resume Understanding added | ✅ |

**Honest verdict: closer to done, still not fully there.** All 4
reviewer-required fixes are complete and verified with real test
execution, including two real bugs found and fixed along the way.
Tooling gaps (lint/type-check/format) remain unaddressed — those are
the one category of Definition-of-Done item genuinely untouched by
this revision. The live-LLM-call gap also remains and is, if anything,
now the clearest single blocker to a full PASS.
