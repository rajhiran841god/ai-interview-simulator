# Module Contract — Resume Understanding

**Status:** Draft — pending approval before implementation
**Milestone:** 3, Module 1 of 10 (see Milestone_2_Architecture.md Section 11)

---

## Purpose

Convert an uploaded resume into a structured, uncertainty-preserving
representation that later modules (JD Understanding, Competency Model,
Reasoning Engine) can consume without needing to re-parse free text.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| file | binary | Yes | The resume file itself |
| file_format | enum | Yes | `pdf`, `docx` — v0.1 supports these two only; anything else is rejected with a clear error (see Acceptance Criteria) |
| candidate_id | string | Yes | Links output to the candidate |
| interview_id | string | No | May not exist yet if resume is uploaded before an interview session starts |
| upload_timestamp | ISO 8601 string | Yes | |

## Output — Structured Resume Object

Top-level object, all sections present even if empty (see "Handling
Missing Data" below):

```json
{
  "personal_summary": { "value": string | null, "confidence": "stated" | "inferred" | "absent" },
  "education": [
    {
      "institution": string | null,
      "degree": string | null,
      "field": string | null,
      "dates": string | null,
      "confidence": "stated" | "absent"
    }
  ],
  "work_experience": [
    {
      "organization": string | null,
      "role": string | null,
      "dates": string | null,
      "description_raw": string,
      "confidence": "stated" | "absent"
    }
  ],
  "projects": [ { "name": string | null, "description_raw": string } ],
  "skills": [ string ],
  "certifications": [ string ],
  "achievements": [ string ],
  "probe_worthy_claims": [
    {
      "claim_text": string,
      "source_section": "work_experience" | "projects" | "achievements" | "personal_summary",
      "reason_flagged": string
    }
  ],
  "parse_warnings": [ string ]
}
```

### Mandatory fields
`personal_summary`, `education`, `work_experience`, `skills`,
`probe_worthy_claims`, `parse_warnings` — always present in the output
object, even if their value is an empty array/null. Downstream modules
should never need to check "does this key exist."

### Optional fields
`projects`, `certifications`, `achievements` — present as empty
arrays if the resume doesn't include them, not omitted from the
object.

### Handling Missing / Ambiguous Values (critical rule)

**The module must never infer or invent information that is not
present in the resume text.** If a field can't be determined:
- Use `null` for the value.
- Set `confidence: "absent"` rather than guessing.
- Do not fill in a plausible date range, a plausible institution name,
  or a plausible skill level.

This applies even when a guess would be "reasonable" — e.g. if
graduation year is missing but could be estimated from work history
dates, the module does **not** estimate it. That kind of inference, if
ever wanted, belongs to a later module that can be explicit about
doing it — not silently baked into extraction.

### Probe-Worthy Claims (the bridge to the reasoning engine)

A claim is flagged when it asserts an outcome or role without
supporting detail — e.g. "Led a team of 5" with no mention of what
leading involved, or "Increased revenue by 30%" with no context on
how. This module only **flags** these; it does not evaluate,
score, or judge them. That's the Reasoning/Evaluation Engine's job
downstream.

## Responsibilities

- Parse PDF and DOCX resume files into the structured object above.
- Normalize obvious formatting variance (e.g. "B.Tech" vs "Bachelor of
  Technology" can be preserved as-is; no responsibility to canonicalize
  further in v0.1).
- Preserve uncertainty explicitly rather than resolving it.
- Flag vague or unsupported claims as probe-worthy.
- Record parse warnings when text extraction is incomplete or the
  document structure is unusual (e.g. a resume that's mostly an image/
  scanned PDF with little extractable text).

## Explicit Non-Responsibilities

- Does not judge, score, or rank the candidate.
- Does not calculate competency confidence (Competency Model's job).
- Does not generate interview questions (Question Generator's job).
- Does not compare the resume against a JD (JD Understanding + later
  modules' job).
- Does not resolve or "fix" probe-worthy claims — only flags them.

## Acceptance Criteria

1. Accepts `.pdf` and `.docx` files; rejects any other format with a
   clear, specific error (not a generic failure).
2. Produces output matching the schema above for every accepted file
   — no missing mandatory keys.
3. For a resume with clearly stated fields (name, education, work
   history), all corresponding fields are populated with
   `confidence: "stated"`.
4. For a resume missing a section entirely (e.g. no certifications),
   that field is an empty array — not omitted, not fabricated.
5. At least one probe-worthy claim is correctly flagged on a test
   resume containing an unsupported outcome claim (e.g. "led a
   successful product launch" with no further detail).
6. A sparse or malformed resume (very short, poorly formatted, or
   partially unreadable) does not crash the module — it returns a
   valid output object with `parse_warnings` populated and heavy use
   of `confidence: "absent"`, rather than failing outright.
7. No field in the output contains information that cannot be traced
   back to actual resume text — verified by manual spot-check during
   review, since this is the one rule most likely to be silently
   violated by an LLM-based extractor "helpfully" filling gaps.

## Review Checklist (before merge)

- [ ] Schema matches this contract exactly (no undocumented fields)
- [ ] Manually tested against at least 3 real (anonymized) resumes of
      varying completeness/quality
- [ ] Confirmed no inference/fabrication on at least one deliberately
      sparse test resume
- [ ] Parse warnings are human-readable, not raw exceptions
- [ ] Does not import any LLM provider SDK directly (routes through
      ProviderAdapter per Milestone 2 Architecture Section 10, if an
      LLM is used for extraction)
