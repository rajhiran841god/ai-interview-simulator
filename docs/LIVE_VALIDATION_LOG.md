# Live Validation Log

**Purpose:** structured, comparable record of every live-LLM validation
test, per the testing order agreed in `PILOT_EXECUTION_PLAN.md`'s
pre-pilot checklist. This is real evidence, not mocked test output —
each entry here is the first time that specific piece of the engine
has ever seen a real model response.

**Provider note:** all entries below (until stated otherwise) use
`aicredits.in`, a third-party validation-only gateway — NOT direct
Anthropic access. Latency numbers include gateway + network overhead
on top of actual model inference, and should be read as "current
baseline via this provider," not "Claude's real speed." This
distinction matters if/when direct Anthropic access is set up
later — re-baseline latency at that point rather than assuming these
numbers transfer.

**Testing order** (increasing risk, per agreed sequence):
1. JD Understanding
2. Resume Understanding
3. Evaluation Engine
4. Question Generator
5. Feedback Generator
6. Full interview session (orchestrated, multi-turn)

---

## Entry 1 — JD Understanding

| Field | Value |
|---|---|
| **Module** | JD Understanding |
| **Input** | `"We need a Marketing Associate with strong consumer insight skills and experience with brand positioning."` |
| **Model used** | `anthropic/claude-sonnet-4.5` (per aicredits.in's Playground example) |
| **Gateway/provider** | aicredits.in (OpenAI-compatible proxy) |
| **Latency** | 3,892 ms (`processing_metadata.processing_time_ms`, end-to-end incl. gateway) |
| **Expected behavior** | Extract role title, seniority, and JD-derived competencies; every `stated` value traceable to real input text; no fabrication |
| **Actual behavior** | `role_title: "Marketing Associate"` (stated, correctly sourced). `seniority_level: "associate"` (stated, inferred from "Associate" in the title — grounded, not fabricated). Two competencies extracted: `consumer_insight_skills`, `brand_positioning`, both `primary` emphasis, both with exact-substring `source_text` matches to the real input. Zero `parse_warnings`, zero `errors`. |
| **Pass/Fail** | ✅ **Pass** |
| **Observations** | First real confirmation that the `is_traceable()` no-fabrication check works correctly against real (not mocked) LLM output — this is the highest-risk architectural guarantee in the project, now verified once, live. `competency_id` normalization (`"Consumer insight skills"` → `consumer_insight_skills`) confirmed correct on real output. |
| **Follow-up action** | Test a JD with a less obvious seniority signal (no "Associate"/"Senior" in the title) to check whether `seniority_level` inference stays grounded or starts guessing on ambiguous input. Not urgent — noted for later, broader JD testing. |

---

## Entry 2 — Resume Understanding

| Field | Value |
|---|---|
| **Module** | Resume Understanding |
| **Input** | `tests/fixtures_real_pdf.pdf` (real PDF fixture from Module 1 — Priya Sharma, MBA Marketing, LBSIM) |
| **Model used** | `anthropic/claude-sonnet-4.5` |
| **Gateway/provider** | aicredits.in |
| **Latency** | 7,238 ms (`processing_metadata.processing_time_ms`) |
| **Expected behavior** | Structured extraction with `stated`/`absent` confidence per field, provenance on every stated value, probe-worthy claims flagged, no fabrication |
| **Actual behavior** | `personal_summary: absent` — correctly declined to fabricate a summary since none exists in the source (just a name/title header, not a summary paragraph). Both education entries extracted correctly, exact `source_text` matches; second entry's `field: null` since "B.Com" is ambiguous as degree-vs-field and the model correctly did not guess "Commerce." Work experience extracted correctly. All 4 skills extracted verbatim. **`probe_worthy_claims` correctly flagged "Drove a successful product launch"** with a specific, well-reasoned justification (no explanation of what "drove" meant, what made it successful, or what actions were taken). Zero `parse_warnings`, zero `errors`. |
| **Pass/Fail** | ✅ **Pass** |
| **Observations** | **This is the strongest single result in the validation log so far.** The probe-worthy-claims mechanism — the "bridge to the reasoning engine" concept from the very first module built in this project — worked correctly against a real model for the first time, unprompted, with well-reasoned justification text. The two "absent"/"null" decisions (personal_summary, B.Com's field) both show the no-fabrication discipline holding under real, ambiguous input, not just clean mocked test cases. |
| **Follow-up action** | Latency (7,238 ms) is notably higher than JD Understanding's 3,892 ms — but this module runs once at upload time, not inside the real-time voice loop, so it's lower-priority than Evaluation Engine/Question Generator's latency for the voice-experience question. Still worth tracking as upload-wait-time UX. Test against a messier, real (non-fixture) resume later to see if extraction quality holds on less clean input. |

---

## Entry 3 — Evaluation Engine

| Field | Value |
|---|---|
| **Module** | Evaluation Engine |
| **Input** | Real answer: *"During my internship at Hindustan Unilever, I led a small team of 3 to launch a new product feature. We hit a major setback when our initial concept tested poorly with consumers, so I organized additional focus groups, redesigned our approach based on that feedback, and we launched two weeks later than planned but with much stronger consumer reception."* (target competency: `leadership`) |
| **Model used** | `anthropic/claude-sonnet-4.5` |
| **Gateway/provider** | aicredits.in |
| **Latency** | Not captured this run — Evaluation Engine doesn't expose `processing_time_ms` the way Resume/JD Understanding do. Follow-up: wrap with a manual timer for future entries so all modules are comparable. |
| **Expected behavior** | Correctly distinguishes substantive/partial/deflection/non_answer; extracts evidence only from real answer text; contradiction detection scoped to same interview; confidence never clamped, rejected if out of range |
| **Actual behavior** | Classified `substantive` (correct — this is a strong, detailed answer). 3 evidence entries created, **all verified as exact substrings of the real answer text** — no fabrication. `confidence_contribution: 0.75` with a specific, calibrated rationale referencing genuine limitations of the answer's scope (small team, internship, single project) — not generic praise. `contradiction_detected: false` (correct, no prior evidence existed to contradict). Logging's `confidence_post` and `evidence_ids_referenced` matched the `EvaluationResult` exactly, confirming the full orchestration chain (evaluate → Evidence Graph → Logging) closed correctly on live data. |
| **Pass/Fail** | ✅ **Pass** |
| **Observations** | **The most important validation result so far.** This is the first live confirmation that the reasoning-quality question (not just extraction) holds up under a real model: the classification was correct, the confidence score was genuinely calibrated rather than a round number, and — critically — every piece of "evidence" the model claimed to have found was independently verified as real, exact, unfabricated text from the actual answer. This is the mechanism Architecture Review Gate #4 was built around, now confirmed working end to end, live. |
| **Follow-up action** | Add manual timing wrapper for latency comparability. Test a deflection and a non-answer example next to confirm the harder classification distinction (the one flagged as "subtlest judgment call in the module" back in Module 6's contract) holds up live, not just in mocked tests. Test a contradiction scenario live (two answers, second one conflicting) since that path hasn't been exercised with a real model yet. |

---

## Entry 4 — Question Generator

| Field | Value |
|---|---|
| **Module** | Question Generator (+ Reasoning Engine, real decision feeding it) |
| **Input** | Real prior answer: *"I led a small team of 3 to launch a new product feature at my internship."* (shorter/less detailed than Entry 3's answer) |
| **Model used** | `anthropic/claude-sonnet-4.5` |
| **Gateway/provider** | aicredits.in |
| **Latency** | Not captured — same gap as Entry 3, follow-up timer needed |
| **Expected behavior** | `question_type` matches deterministic mapping (code, not model-decided); grounding context contains only real evidence; question genuinely references prior context without misattribution |
| **Actual behavior** | Reasoning Engine correctly identified confidence (0.20) below the acceptance floor → `decision_strategy: probe_deeper`. Question Generator correctly mapped this to `question_type: cross_question` (since evidence already existed for the competency — deterministic code path, verified live). Generated question: *"When you led that team of 3 to launch the new product feature, what was the most difficult leadership challenge you faced, and how did you handle it?"* — genuinely references real specifics ("team of 3," "new product feature") from the actual prior answer, not generic phrasing. `generation_method: "llm"` — succeeded on first attempt, no fallback needed. |
| **Pass/Fail** | ✅ **Pass** |
| **Observations** | First live confirmation that cross-questioning grounding works correctly — the model referenced real prior context accurately without inventing or misattributing what the candidate said. Notable secondary finding: this shorter, less detailed answer produced confidence ~0.20, versus Entry 3's fuller answer producing 0.75 — real evidence the model's confidence calibration responds to actual answer quality/detail rather than returning arbitrary values, consistent across two different live inputs. |
| **Follow-up action** | Add timing wrapper (same as Entry 3). Test the `challenge_inconsistency` strategy live once a real contradiction scenario is run (see Entry 3's follow-up) — that specific question-type mapping hasn't been exercised live yet. |

---

## Entry 5 — Feedback Generator

| Field | Value |
|---|---|
| **Module** | Feedback Generator |
| **Input** | Same leadership answer as Entry 3 (setback/focus-groups/relaunch example), full pipeline: evaluate → Competency Model → generate report |
| **Model used** | `anthropic/claude-sonnet-4.5` |
| **Gateway/provider** | aicredits.in |
| **Latency** | Not captured — same gap as Entries 3-4 |
| **Expected behavior** | AC1 (merge-blocking): zero confidence numbers/percentages anywhere in output. Evidence citations verified against real Evidence Graph entries. Natural, student-quality prose. |
| **Actual behavior** | **AC1 held: zero confidence numbers or percentages anywhere in the output** — verified by inspection, no float/percentage appeared. `supporting_evidence_ids` correctly populated with 3 real, verified evidence IDs. **However: the `summary_text` prose contained raw internal `evidence_id` UUIDs embedded inline** — e.g. *"...redesigned our approach based on the feedback received (evidence: c8f16fa5-4b83-40de-9d74-b21e748094d7)."* This is not a confidence leak (AC1 held), but a different real quality bug: internal implementation detail leaking into text a student would actually read. |
| **Pass/Fail** | ⚠️ **Pass on AC1 (the critical criterion), Fail on prose quality — bug found and fixed same session** |
| **Observations** | **This is exactly the kind of bug live testing exists to catch and mocked tests structurally cannot.** Every mocked test in Module 10's original suite supplied hand-written `summary_text` values — none of them could ever reveal that a real model might interpret "cite evidence_ids" as "embed them inline in the prose" rather than "report them only in the separate structured field." Root cause: the system prompt said "cite which evidence_id(s)...support it" without specifying *where* — a genuine, fixable prompt ambiguity, not model misbehavior. **Fixed two ways**: (1) prompt now explicitly states citations belong only in `cited_evidence_ids`, never in `summary_text`, with explicit examples of what NOT to do; (2) a structural, regex-based safeguard (`_scrub_evidence_ids`) now strips any UUID-shaped pattern from `summary_text` regardless of prompt compliance — same "never trust the model alone" discipline already used for `EvidenceVerifier`'s ID checking. Verified against the exact real problematic text from this test; all 3 UUIDs removed, real content and natural sentence flow preserved, no leftover double-spacing or dangling punctuation. Added as a permanent regression test using the literal real text from this incident, not a synthetic approximation. |
| **Follow-up action** | **Re-run this exact same test again with a fresh live call** to confirm the prompt fix actually changes the model's behavior (not just that the structural scrub catches it if it doesn't) — the scrub is a safety net, not a substitute for verifying the root-cause fix works. Add timing wrapper (same gap as Entries 3-4). |


---

## Entry 6 — Full Interview Session (orchestrated, multi-turn)

| Field | Value |
|---|---|
| **Module** | Full pipeline, via `/api/interviews/*` endpoints |
| **Input** | *(pending — real resume + real JD + multiple live Q&A turns)* |
| **Expected behavior** | Complete session: create → resume → JD → multiple question/answer cycles → stop decision → report, all against live model calls |
| **Actual behavior** | |
| **Pass/Fail** | |
| **Observations** | |
| **Follow-up action** | |

---

## Latency Summary (update as entries are added)

| Module | Latency (ms) |
|---|---|
| JD Understanding | 3,892 |
| Resume Understanding | 7,238 |
| Evaluation Engine | — |
| Question Generator | — |
| Feedback Generator | — |

**Running concern:** if Evaluation Engine + Question Generator each take
~4s like JD Understanding did, a single voice turn (which calls both
in sequence) could mean 7-8+ seconds of silence between a student
finishing speaking and the AI responding — directly relevant to
`VOICE_VALIDATION.md`'s Test 2. Keep tracking this as more entries
come in, and treat it as decision-relevant data for whether voice
ships as designed, per Decision #004's falsification condition — not
just a curiosity.
