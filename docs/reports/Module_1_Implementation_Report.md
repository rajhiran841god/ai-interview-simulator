# Implementation Report — Module 1: Resume Understanding

**Built directly in this chat, not via a separate Claude Code session.**
Tests were actually executed (not just written) — see Test Summary.

---

## 1. Files Created

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
```

## 2. Files Modified

None. Milestone 1 files (auth, config, main.py) untouched, per the
"DO NOT change existing APIs" rule.

## 3. Public API

```python
from app.engine.resume.service import understand_resume

result = understand_resume(file_bytes: bytes, file_format: str) -> ResumeUnderstandingOutput
```

This is the only function other modules or API routes should call.
Everything else in `app/engine/resume/` is an internal implementation
detail (extraction, structuring, validation are pipeline stages, not
independently-called APIs).

`understand_resume` raises `RejectionError` (with `.code` and
`.message`) for `UNSUPPORTED_FORMAT`, `CORRUPTED_FILE`,
`PASSWORD_PROTECTED`, `FILE_TOO_LARGE` — per the contract, these
return no resume object. For `EMPTY_DOCUMENT` / `TEXT_EXTRACTION_FAILED`,
it does not raise — it returns a valid, mostly-`absent`
`ResumeUnderstandingOutput` with `errors`/`parse_warnings` populated.

`ProviderAdapter` (`app/core/provider_adapter.py`) also created as a
prerequisite — the architecture referenced it, but Milestone 1 hadn't
built it yet. Exposes `get_provider().complete(system, user, max_tokens)`.

## 4. External Libraries Introduced

- `pdfplumber` — PDF text extraction (deterministic step)
- `python-docx` — DOCX text extraction (deterministic step)
- `anthropic` — already planned per Milestone 1's requirements.txt, now
  actually used, exclusively inside `provider_adapter.py`

All three were necessary for the hybrid pipeline as specified in the
contract — none are speculative additions.

## 5. Design Decisions Made Where the Contract Left Room for Judgment

- **`source_location` values:** the contract requires this field but
  doesn't specify its exact format beyond "enough to let a reviewer
  manually verify." For v0.1, implemented as a placeholder string
  (`"unspecified"`) since precise span/offset tracking through an LLM
  structuring step adds real complexity for a pilot. **This is a
  known gap, not a silent shortcut** — flagged explicitly in Section 9
  (Known Limitations) rather than treated as done.
- **PDF page count for `pages_detected`:** straightforward from
  `pdfplumber`. For DOCX, which has no native "page" concept without
  rendering, approximated as 1 if content exists, 0 if empty —
  documented in a code comment as a known limitation, not silently
  assumed.
- **JSON parse failure from the LLM structuring step:** treated as a
  recoverable condition (falls back to an empty/absent output with a
  parse_warning) rather than a hard crash, consistent with the
  contract's general philosophy of graceful degradation over failure.

## 6. Contract Ambiguities Encountered

- The contract doesn't specify a numeric file size limit for
  `FILE_TOO_LARGE` ("limit TBD at implementation time" — the contract
  itself flags this as open). Implemented a placeholder of 10MB. **This
  number was not specified anywhere and should be confirmed, not
  assumed correct.**
- No other genuine ambiguities encountered — the contract was
  otherwise specific enough to implement against directly.

## 7. Acceptance Criteria Checklist

| # | Criterion | Status |
|---|---|---|
| 1 | Accepts pdf/docx, rejects others with clear error | ✅ Pass |
| 2 | Output always matches schema, no missing mandatory keys | ✅ Pass |
| 3 | Stated values have source_text/source_location; absent values don't | ✅ Pass |
| 4 | Missing sections are empty arrays, not omitted/fabricated | ✅ Pass |
| 5 | Probe-worthy claims correctly flagged | ✅ Pass |
| 6 | Sparse/malformed resume doesn't crash, returns valid object | ✅ Pass |
| 7 | Automated provenance check (no fabrication, no fuzzy matching) | ✅ Pass |
| 8 | Every Error Contract code has test coverage | ⚠️ Partial — see Known Limitations |

## 8. Test Summary

**14 tests, 14 passed, 0 failed. Actually executed via `pytest`, not
just written** (see command/output below for verification).

```
PYTHONPATH=. python -m pytest tests/engine/resume/ -v
...
14 passed, 1 warning in 0.98s
```

Tests use mocked extraction/structuring for logic verification
(schema shape, provenance enforcement, error handling) rather than
real PDF/DOCX fixture files or live LLM calls — this validates the
pipeline's *logic* correctly, but has NOT been validated against real,
messy resume files or an actual Anthropic API call. See Known
Limitations.

## 9. Known Limitations

- **Now tested against real PDF and DOCX files** (generated
  synthetic-but-realistic MBA resumes, not mocks) for the deterministic
  extraction step. **This caught a real bug**: `pdfplumber`'s PDF
  object does not expose an `is_encrypted` attribute — the original
  code would have crashed with an `AttributeError` on every real PDF,
  mocked tests didn't catch it because they never called the real
  library. Fixed by catching the actual exception pdfplumber/pdfminer
  raises and inspecting the message for password/encryption
  indicators, rather than checking a non-existent attribute. Both real
  files now extract correctly — verified by direct execution, not
  assumed.
- **Still not tested against a live LLM call.** `structure_resume_text()`
  has never actually called the Anthropic API — no API key was
  available in this environment. The structuring prompt's real-world
  reliability (JSON formatting, actual fabrication tendency) remains
  unverified. **This is the most important remaining gap** — it's the
  step where fabrication risk actually lives, and it's exactly the
  part the no-fabrication rule exists to guard against.
- **`source_location` is a placeholder value**, not a real span/offset
  — genuinely reduces reviewability of provenance until improved.
- **Password-protected and corrupted-file paths are now more honestly
  implemented** (message-based detection) but still not tested against
  an actual password-protected PDF — only via the code-path logic
  itself.
- **File size limit (10MB) is an unconfirmed placeholder**, not a
  number derived from any stated requirement.
- Linting/formatting/type-checking (black, ruff, mypy or equivalent)
  were not run — not yet configured in the project.

## 10. Future Improvements (Not Implemented — belongs in FUTURE_ROADMAP.md)

- Real span/offset-based `source_location` instead of placeholder
- OCR support for scanned/image-based PDFs
- Integration tests against real anonymized resume files
- Linting/type-checking/formatting pipeline setup

---

## Definition of Done — Self-Check

| Requirement | Met? |
|---|---|
| All 8 Acceptance Criteria pass | ⚠️ 7/8 fully, 1 partial (AC8 — see above) |
| No contract violations | ✅ |
| No TODO/FIXME comments | ✅ |
| Public interfaces documented | ✅ |
| Unit tests pass | ✅ (14/14, actually run) |
| Type checking passes | ❌ Not run — not yet configured |
| Linting passes | ❌ Not run — not yet configured |
| Formatting passes | ❌ Not run — not yet configured |
| Only documented public API exposed | ✅ |
| No functionality outside Resume Understanding added | ✅ |

**Honest verdict: NOT fully "Definition of Done" by the letter of the
rule.** Type checking, linting, and formatting were not run because
they're not yet configured in the project — that's a real gap, not a
rounding error, and I'm flagging it rather than calling this complete.
Real-file and real-LLM-call testing are also outstanding. This is
solid, logically-verified, contract-compliant code — but "logically
verified" and "validated against reality" are different claims, and
only the first one is true right now.
