# Module Contract — JD Understanding

**Status:** Draft — pending review before implementation
**Milestone:** 3, Module 2 of 10 (see Milestone_2_Architecture.md Section 11)

**Lessons carried forward from Resume Understanding's review cycle**
(applied from the start this time, not retrofitted):
- No "unspecified" placeholders — coarse section labels from day one.
- No `"inferred"` confidence state — only `stated`/`absent`.
- Provenance (`source_text`, `source_location`) required from the start.
- Explicit Error Contract, not implicit.
- Acceptance Criteria written to be testable in CI, including against
  real fixture files, not just mocks.

**Enforceable rule (same as Resume Understanding — Milestone 2
Architecture Section 10):** `ProviderAdapter` is the only module
permitted to communicate directly with an LLM provider SDK. No
exceptions for this module.

**Implementation note:** the provenance validator built for Resume
Understanding should be extracted into a shared internal library and
reused here, not copied — same normalized-exact-substring matching
logic, same `ValidationResult` pattern. This is an implementation
detail, not a contract requirement, but stated here so it isn't lost.

---

## Purpose

Extract the target role's actual requirements from a job description,
producing the competency set that the rest of the engine (starting
with the Competency Model) will use for this specific interview. Per
Milestone 2 Architecture Section 2.2: this module determines which
competencies matter and their relative emphasis for this session — the
competency set is **derived per JD, never hardcoded**.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| jd_text | string | Yes | Raw job description text (already extracted — JD is assumed to arrive as plain text/pasted text for v0.1, not a file upload; see Non-Responsibilities) |
| interview_id | string | No | May not exist yet if JD is provided before an interview session starts |
| upload_timestamp | ISO 8601 string | Yes | |

**Note:** unlike Resume Understanding, this module does not itself
handle file parsing in v0.1 — JD text is assumed to be pasted or
already extracted as plain text by the calling layer (e.g. a text box
in the UI). This is a deliberate scope reduction, not an oversight —
see Non-Responsibilities.

## Output — Structured JD Object

```json
{
  "role_title": {
    "value": string | null,
    "confidence": "stated" | "absent",
    "source_text": string | null,
    "source_location": string | null
  },
  "seniority_level": {
    "value": "entry" | "associate" | "mid" | "senior" | "leadership" | null,
    "confidence": "stated" | "absent",
    "source_text": string | null,
    "source_location": string | null
  },
  "required_competencies": [
    {
      "competency_id": string,
      "competency_name": string,
      "emphasis": "primary" | "secondary",
      "source_text": string,
      "source_location": string
    }
  ],
  "role_specific_signals": [
    {
      "signal_text": string,
      "interpretation": string,
      "source_text": string,
      "source_location": string
    }
  ],
  "parse_warnings": [ string ],
  "errors": [ { "code": string, "message": string } ],
  "parser_version": string,
  "processing_metadata": {
    "processing_time_ms": number,
    "text_length": number
  }
}
```

### Mandatory fields
`role_title`, `required_competencies`, `parse_warnings`, `errors` —
always present, even if empty/absent.

### Optional-content fields
`seniority_level`, `role_specific_signals` — present but may be
`null`/empty if not determinable from the JD text.

### Confidence States

Same two-state model as Resume Understanding — **no `"inferred"`
state.** `stated` requires non-null `source_text`/`source_location`.
`absent` means `value: null`, no `source_text`.

### `required_competencies` — the critical output

This is what the Competency Model (downstream) consumes directly to
seed which competencies get tracked for this interview (Milestone 2
Architecture, Section 2.3). Each entry must be:
- Traceable to specific JD text (same provenance rule as Resume
  Understanding — no fabricating a competency the JD doesn't actually
  emphasize).
- Tagged `primary` or `secondary` emphasis, per this precise
  definition (fixed now so implementers don't each define it
  differently):
  - **`primary`** — explicitly required, or emphasized more than once
    across the JD (e.g. appears in both a "requirements" section and
    a role summary).
  - **`secondary`** — mentioned as desirable, supportive, or a "nice
    to have," not central to the role's core requirements.
- **Competency names are not from a fixed enum.** Per the architecture,
  competency sets are JD-derived. A marketing JD might emphasize
  "Consumer Insight" and "Brand Storytelling"; a consulting JD might
  emphasize "Structured Problem Solving" and "Client Communication."
  This module does not constrain the vocabulary — it extracts what the
  JD actually signals.
- Includes a `competency_id`: a normalized, stable identifier derived
  from `competency_name` (lowercase, spaces replaced with underscores
  — e.g. "Consumer Insight" → `consumer_insight`). Not needed by this
  module itself, but downstream modules (Competency Model, Evidence
  Graph, Reasoning Engine) need a stable key to reference the same
  competency consistently across the interview, rather than
  re-matching on display strings.

### `role_specific_signals`

**Definition:** role-specific signals capture contextual expectations
that influence how competencies should be interpreted during the
interview, but are not themselves competencies or qualifications. This
category explicitly does NOT include: required qualifications (e.g.
"MBA preferred"), logistical details (e.g. "Remote work," "Based in
Mumbai"), or anything that belongs in `required_competencies` instead.
Example of a genuine signal: JD says "fast-paced startup environment"
→ `signal_text`: that phrase, `interpretation`: "candidate should
demonstrate comfort with ambiguity and rapid iteration."

**Grounding rule:** `interpretation` must remain directly supported by
the cited `signal_text` and must not introduce any new requirement,
competency, or claim not present in the source. This module only
records the signal and a brief interpretation — it does not decide how
the Reasoning Engine should act on it, and it must not use
`interpretation` as a backdoor to smuggle in fabricated requirements
under a softer label than `required_competencies`.

## Error Contract

| Code | Meaning | Behavior |
|---|---|---|
| `EMPTY_JD` | jd_text is empty or whitespace-only | Return a valid output object, all fields absent, parse_warnings populated |
| `JD_TOO_SHORT` | Text present but too short to meaningfully extract competencies (e.g. under ~50 characters) | Return valid output, mostly absent, parse_warnings explaining why |
| `JD_TOO_LARGE` | Exceeds a defined length limit (limit defined in implementation configuration, not hardcoded — mirroring the configurable-thresholds approach adopted in Milestone 2 Architecture Section 4) | Reject — no output object |
| `STRUCTURING_FAILED` | LLM structuring step returned unparseable output | Return valid output, mostly absent, parse_warnings populated — same recoverable pattern as Resume Understanding, not a crash |

Only `JD_TOO_LARGE` is a rejection error (no output object at all).
The others are recoverable, consistent with the philosophy established
in Resume Understanding's Error Contract.

## Responsibilities

- Extract role title, seniority level, and required competencies from
  JD text via the same hybrid-style approach as Resume Understanding:
  LLM semantic extraction, followed by provenance validation against
  the raw JD text (no separate "deterministic extraction" step is
  needed here since there's no file parsing involved — extraction
  starts directly from provided text).
- Preserve uncertainty explicitly (`stated`/`absent`).
- Provide provenance for every `stated` value, using coarse section-
  or sentence-level labels (e.g. "Requirements section," "Role
  Summary") — same standard as Resume Understanding's revised
  contract, not a placeholder.
- Tag each required competency's emphasis (primary/secondary).
- Record role-specific interpretive signals separately from hard
  competency requirements.

## Explicit Non-Responsibilities

- Does not parse JD files (PDF/DOCX/etc.) — assumes plain text input
  in v0.1. **This is a deliberate scope reduction**, not an oversight:
  most placement-context JDs are pasted from portals/emails rather
  than uploaded as separate files. If file-upload JD support is wanted
  later, it belongs in `docs/FUTURE_ROADMAP.md`, not folded in here
  silently.
- Does not compare the JD against a candidate's resume (that's a
  downstream concern once both Resume Understanding and JD
  Understanding outputs exist — likely Competency Model or Reasoning
  Engine territory, not this module's).
- Does not decide interview length, question count, or stopping
  conditions.
- Does not generate interview questions.
- Does not judge whether a JD is "good" or "well-written" — only
  extracts what it says.
- Does not infer or estimate competencies not textually signaled by
  the JD, under any circumstance — same hard rule as Resume
  Understanding.

## Acceptance Criteria

1. Given non-empty JD text, output always matches the schema — no
   missing mandatory keys.
2. Every `stated` value has non-null `source_text`/`source_location`;
   every `absent` value has `null` value and no `source_text`.
3. `required_competencies` entries are traceable to JD text — no
   competency appears that isn't textually supported (automated
   provenance check, same normalized-exact-substring rule as Resume
   Understanding's Contract v3, Acceptance Criterion 7 — reused, not
   reinvented).
4. Each competency entry has a valid `emphasis` tag (`primary` or
   `secondary`, per the precise definitions above) — never missing,
   never an invented third value. Each entry also has a
   `competency_id` correctly derived from `competency_name`
   (lowercase, spaces replaced with underscores).
5. Empty or near-empty JD text does not crash the module — returns a
   valid, mostly-absent object with `parse_warnings`/`errors`
   populated per the Error Contract.
6. Tested against at least 3 real, varied JD texts (different roles —
   e.g. marketing, consulting, finance — reflecting the range of MBA
   placement roles), **independently reviewed by a human reviewer with
   no fabricated competencies accepted** — i.e. every extracted
   competency and every `role_specific_signals` interpretation is
   checked against the source JD by a person, not just verified for
   schema-shape correctness.
7. Each Error Contract code has test coverage.
8. **No hardcoded competency vocabulary anywhere in the implementation**
   — verified by testing against JDs from at least two different
   functional areas (e.g. marketing and finance) and confirming the
   extracted competency names differ meaningfully rather than
   converging on a fixed list.

## Review Checklist (before merge)

- [ ] Schema matches this contract exactly, including `competency_id`
- [ ] Manually tested against at least 3 real (anonymized) JD texts
      spanning different functional areas
- [ ] Automated provenance test (AC3) passes, reusing the validator
      logic already proven in Resume Understanding (extracted into a
      shared library, not copy-pasted)
- [ ] All Error Contract codes have test coverage
- [ ] Confirmed no hardcoded competency list anywhere (AC8)
- [ ] `primary`/`secondary` classification matches the precise
      definitions in this contract, not an implementer's own judgment
- [ ] `role_specific_signals` entries are genuinely contextual signals,
      not misfiled qualifications or logistics
- [ ] Every `interpretation` field is grounded in its cited
      `signal_text` — spot-checked for fabrication risk
- [ ] Does not import an LLM provider SDK directly — routes through
      `ProviderAdapter`
- [ ] `source_location` uses real coarse labels, never a placeholder
      string like "unspecified"
- [ ] Length limit for `JD_TOO_LARGE` is a configurable value, not
      hardcoded
