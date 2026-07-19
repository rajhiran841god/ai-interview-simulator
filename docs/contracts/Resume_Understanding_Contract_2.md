# Module Contract — Resume Understanding (v2)

**Status:** Draft — pending final approval before implementation
**Supersedes:** Resume_Understanding_Contract.md (v1)
**Milestone:** 3, Module 1 of 10 (see Milestone_2_Architecture.md Section 11)

**Changes from v1:** Removed the `"inferred"` confidence state (it
contradicted the no-fabrication rule). Added provenance fields
(`source_text`, `source_location`) to make traceability systematic
rather than dependent on manual review. Added an explicit error
contract. Specified a hybrid extraction pipeline.

---

## Purpose

Convert an uploaded resume into a structured, uncertainty-preserving,
traceable representation that later modules (JD Understanding,
Competency Model, Reasoning Engine) can consume without re-parsing
free text.

## Extraction Approach (Hybrid)

1. **Deterministic extraction** — PDF/DOCX → raw text, with section
   detection and document order preserved. No semantic interpretation
   at this stage.
2. **LLM-backed semantic structuring** — maps extracted raw text into
   the schema below, identifies probe-worthy claims, generates parse
   warnings. Routed through `ProviderAdapter` (Milestone 2 Architecture
   Section 10) — this module never imports an LLM SDK directly.
3. **Validation layer** — every extracted value is checked against the
   raw source text. A value that cannot be located in the source is
   rejected (set to `absent`) rather than kept. This is what makes
   the no-fabrication rule enforceable in code, not just in the prompt.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| file | binary | Yes | The resume file itself |
| file_format | enum | Yes | `pdf`, `docx` — v0.1 supports these two only |
| candidate_id | string | Yes | Links output to the candidate |
| interview_id | string | No | May not exist yet if resume is uploaded before an interview session starts |
| upload_timestamp | ISO 8601 string | Yes | |

## Output — Structured Resume Object

```json
{
  "personal_summary": {
    "value": string | null,
    "confidence": "stated" | "absent",
    "source_text": string | null,
    "source_location": string | null
  },
  "education": [
    {
      "institution": string | null,
      "degree": string | null,
      "field": string | null,
      "dates": string | null,
      "confidence": "stated" | "absent",
      "source_text": string,
      "source_location": string
    }
  ],
  "work_experience": [
    {
      "organization": string | null,
      "role": string | null,
      "dates": string | null,
      "description_raw": string,
      "confidence": "stated" | "absent",
      "source_text": string,
      "source_location": string
    }
  ],
  "projects": [
    { "name": string | null, "description_raw": string, "source_location": string }
  ],
  "skills": [ { "value": string, "source_location": string } ],
  "certifications": [ { "value": string, "source_location": string } ],
  "achievements": [ { "value": string, "source_location": string } ],
  "probe_worthy_claims": [
    {
      "claim_text": string,
      "source_section": "work_experience" | "projects" | "achievements" | "personal_summary",
      "source_location": string,
      "reason_flagged": string
    }
  ],
  "parse_warnings": [ string ],
  "errors": [ { "code": string, "message": string } ],
  "parser_version": string,
  "processing_metadata": {
    "processing_time_ms": number,
    "text_length": number,
    "pages_detected": number,
    "ocr_used": boolean
  }
}
```

`parser_version` (e.g. `"resume_parser_v1.0.0"`) identifies which
version of this module produced the output — required so that when
extraction quality changes over time, past outputs can be traced back
to the version that generated them.

`processing_metadata` is operational, not user-facing — it exists to
help diagnose failures and performance issues, not to inform any
product feature.

`source_location` identifies where in the document the text came from
(e.g. section name + approximate position — exact implementation is an
engineering choice, but it must be enough to let a reviewer manually
verify the claim against the original document).

### Mandatory fields
`personal_summary`, `education`, `work_experience`, `skills`,
`probe_worthy_claims`, `parse_warnings`, `errors` — always present,
even if empty.

### Optional-content fields
`projects`, `certifications`, `achievements` — present as empty arrays
if absent from the resume, never omitted from the object.

### Confidence States (revised)

Only two states — the contradiction in v1 is resolved by removing
`"inferred"` entirely:

- **`stated`** — explicitly present in and traceable to the resume
  text (must have a non-null `source_text`/`source_location`).
- **`absent`** — not present or not confidently extractable. `value`
  is `null`, and there is no `source_text`.

**No inference happens in this module, full stop.** If a future module
needs to estimate or infer something (e.g. approximate graduation year
from work history), that module introduces its own explicit provenance
for doing so — Resume Understanding does not.

### Probe-Worthy Claims

Flagged when a claim asserts an outcome or role without supporting
detail (e.g. "Led a team of 5" with no detail on what leading
involved). This module only flags — it does not evaluate, score, or
judge. That belongs to the Evaluation Engine downstream.

## Error Contract

| Code | Meaning | Behavior |
|---|---|---|
| `UNSUPPORTED_FORMAT` | File is not `.pdf` or `.docx` | Reject immediately, no partial output |
| `CORRUPTED_FILE` | File can't be opened/parsed at all | Reject with clear message |
| `PASSWORD_PROTECTED` | File requires a password | Reject with clear message |
| `EMPTY_DOCUMENT` | File opens but contains no extractable text | Return a valid output object, all fields `absent`, `parse_warnings` populated |
| `TEXT_EXTRACTION_FAILED` | Partial extraction failure (e.g. scanned/image-based PDF with no OCR in v0.1) | Return a valid output object with `parse_warnings` describing the limitation; do not silently produce empty output without explanation |
| `FILE_TOO_LARGE` | Exceeds size limit (limit TBD at implementation time) | Reject with clear message stating the limit |

Rejection errors (`UNSUPPORTED_FORMAT`, `CORRUPTED_FILE`,
`PASSWORD_PROTECTED`, `FILE_TOO_LARGE`) return no resume object at
all — just the error. Non-rejection errors (`EMPTY_DOCUMENT`,
`TEXT_EXTRACTION_FAILED`) return a valid, mostly-`absent` object so
downstream modules always get a consistently shaped response when the
upload itself succeeded.

## Responsibilities

- Parse PDF and DOCX resume files via the hybrid pipeline above.
- Preserve uncertainty explicitly (`stated`/`absent`) rather than
  resolving it.
- Provide provenance (`source_text`, `source_location`) for every
  `stated` value.
- Flag vague or unsupported claims as probe-worthy.
- Record parse warnings and structured errors per the Error Contract.

## Explicit Non-Responsibilities

- Does not judge, score, or rank the candidate.
- Does not calculate competency confidence (Competency Model's job).
- Does not generate interview questions (Question Generator's job).
- Does not compare the resume against a JD (JD Understanding's job).
- Does not resolve or "fix" probe-worthy claims — only flags them.
- Does not infer or estimate missing values under any circumstance.

## Acceptance Criteria

1. Accepts `.pdf` and `.docx`; all other formats return
   `UNSUPPORTED_FORMAT` per the Error Contract.
2. Output always matches the schema — no missing mandatory keys,
   regardless of input quality.
3. Every `stated` value has non-null `source_text` and
   `source_location`; every `absent` value has `null` value and no
   `source_text`.
4. A resume missing a section entirely produces an empty array for
   that field — not omitted, not fabricated.
5. At least one probe-worthy claim is correctly flagged on a test
   resume containing an unsupported outcome claim.
6. A sparse or malformed resume does not crash the module — returns a
   valid object with `parse_warnings`/`errors` populated and heavy use
   of `absent`, per the Error Contract.
7. **Systematic provenance check (not just manual spot-check):** an
   automated test verifies that for every `stated` field in the
   output, `source_text` matches the original extracted document text
   under this precise definition of "close match" (fixed now so
   implementers don't each define it differently):
   - Normalize both strings: collapse whitespace, strip leading/
     trailing punctuation, lowercase.
   - After normalization, `source_text` must appear as an exact
     substring of the original extracted text.
   - No fuzzy/similarity matching (e.g. no edit-distance thresholds)
     in v0.1 — if normalized substring matching fails, the value is
     rejected and set to `absent` rather than kept on a "probably
     close enough" basis. Stricter is safer than lenient for this
     specific rule.
   This is the enforcement mechanism for the no-fabrication rule — it
   must be testable in CI, not just reviewable by eye.
8. Each Error Contract code is triggered by at least one corresponding
   test case (corrupted file, password-protected file, empty document,
   etc.).

## Review Checklist (before merge)

- [ ] Schema matches this v2 contract exactly (no `"inferred"` state,
      no undocumented fields)
- [ ] Manually tested against at least 3 real (anonymized) resumes of
      varying completeness/quality
- [ ] Automated provenance test (Acceptance Criterion #7) passes
- [ ] All Error Contract codes have test coverage
- [ ] Parse warnings and errors are human-readable, not raw exceptions
- [ ] No module code imports an LLM provider SDK directly — routes
      through `ProviderAdapter`
