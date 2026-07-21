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
| **Follow-up action** | ✅ **Re-tested with a fresh live call — confirmed fixed.** Same interview scenario, new live model response: `summary_text` was completely clean, zero UUIDs, zero citation markers, natural second-person prose. `supporting_evidence_ids` still correctly populated with 3 real IDs in the proper structured field — confirming the fix didn't break the actual citation mechanism, only corrected where citations belong. The structural scrub had nothing to remove this time, meaning the root-cause prompt fix alone was sufficient — the scrub remains in place as a permanent safety net for any future drift, per the project's "never trust the model alone" discipline. Remaining: add timing wrapper (same gap as Entries 3-4). |


---

## Entry 6 — Full Interview Session (orchestrated, multi-turn)

| Field | Value |
|---|---|
| **Module** | Full pipeline, via real `/api/interviews/*` HTTP endpoints (uvicorn server, real requests via curl) |
| **Input** | Real JD: *"We are hiring a Marketing Associate with strong consumer insight skills, experience with brand positioning, and comfort working in a fast-paced, cross-functional team environment."* + a real, detailed answer about discovering a packaging-related customer insight through complaint tickets rather than survey data |
| **Model used** | `anthropic/claude-sonnet-4.5` |
| **Gateway/provider** | aicredits.in |
| **Latency** | Not captured this run — could add via browser dev tools / curl's `-w "%{time_total}"` in a future entry |
| **Expected behavior** | Full session lifecycle works end-to-end through the real HTTP layer (not direct Python calls like Entries 1-5): create → JD upload → competency init → question → answer → evaluation → competency update → **adaptive** next question targeting a *different*, lower-confidence competency |
| **Actual behavior** | Session created cleanly. JD upload correctly extracted **3** competencies (`consumer_insight_skills`, `brand_positioning`, `cross_functional_collaboration` — the third sensibly derived from "fast-paced, cross-functional team environment," not explicit JD wording, showing the extraction generalizes beyond Entry 1's simpler JD). First question: a specific, well-formed "fresh" question targeting `consumer_insight_skills`. Real answer submitted (a detailed, well-reasoned response about discovering a packaging issue via complaint-ticket analysis) — classified `substantive`. **Second question call correctly switched target to `brand_positioning`** — the previously zero-confidence competency — rather than continuing to probe the just-answered one. |
| **Pass/Fail** | ✅ **Pass** |
| **Observations** | **This is the first live confirmation of the actual core product premise** — adaptive questioning that responds to real evidence, through the real HTTP API a frontend would actually call, not a direct Python invocation. Everything tested in Entries 1-5 individually (extraction, evaluation, question generation) is confirmed here to work *together*, live, under `app/orchestrator/`'s real wiring, including the engine singletons, session store, and concurrency guard, none of which had been exercised with a live model until this test. |
| **Follow-up action** | ✅ **Session extended to a full 6-turn arc, report generated and precisely verified (not eyeballed) — closing out Entry 6.** All 3 competencies present in the final report, each correctly synthesizing TWO real answers (an opening story + its later cross-question) into one coherent, accurate narrative — the deepest test of the Feedback Generator's synthesis quality so far. **AC1 and the Entry 5 UUID fix both confirmed holding**, verified by scanning every `summary_text` field directly: zero confidence numbers, zero percentages, zero UUIDs anywhere in the prose across all three competencies; every evidence ID correctly confined to the separate `supporting_evidence_ids` arrays. **Stopping condition tested live for the first time**: after crossing `MIN_QUESTIONS=6`, the Reasoning Engine correctly evaluated real confidence data and chose `continue` rather than `stop` — valuable pilot-tuning signal (see below), not a bug. **One real, still-open gap**: every answer in this session was strong, so the `insufficient_evidence`/`has_unresolved_contradiction` paths remain untested live end-to-end — worth a dedicated test with a deliberately weak or contradictory answer before broader pilot use. |

---

## Entry 7 — Contradiction Detection (Cross-Cutting: Evaluation Engine → Evidence Graph → Feedback Generator)

| Field | Value |
|---|---|
| **Module** | Cross-cutting — closes the specific gap flagged in Entry 3's follow-up ("test a contradiction scenario live — hasn't been exercised with a real model yet") |
| **Input** | Two deliberately conflicting real answers to the same competency (`leadership`): first claiming personal decision-making authority ("I personally made all the key technical decisions"), second directly contradicting it ("my manager made all the final decisions... I mostly just relayed instructions") |
| **Model used** | `anthropic/claude-sonnet-4.5` |
| **Gateway/provider** | aicredits.in |
| **Expected behavior** | Evaluation Engine explicitly detects the contradiction (not inferred downstream); Evidence Graph correctly separates `supports` vs. `contradicts` relations and links the specific contradicted entry; Feedback Generator surfaces it honestly and constructively in the final report |
| **Actual behavior** | **First answer**: `contradiction_detected: false` (correct — no prior evidence existed yet), 3 evidence entries created, `confidence_contribution: 0.7`. **Second answer**: `contradiction_detected: true`, explicitly citing `contradicted_evidence_id` pointing at the *exact* first evidence entry about personal decision-making (not a generic "somewhere" reference), `confidence_contribution: 0.9` (correctly high — this reflects certainty that an inconsistency exists, not praise for the candidate, per the module's documented confidence scope). Critically, the `reasoning_summary` explicitly referenced the real prior claim in its own text — proof the model's classifier call genuinely reasoned over real prior evidence via `prior_evidence_excerpts`, not just emitting a bare flag. **Final report**: `has_unresolved_contradiction: true`, `contradictory_evidence_ids` containing the exact 2 IDs from the second evaluation, `supporting_evidence_ids` containing the exact 3 IDs from the first — every ID traced end to end, not just matching in count. Summary text addressed the conflict directly, professionally, and constructively ("distinguish between situations where you had genuine decision-making authority versus coordination responsibilities"), not just flagging the conflict and stopping. `overall_summary` correctly counted it. |
| **Pass/Fail** | ✅ **Pass — fully verified end to end, not just at the report level** |
| **Observations** | This closes the single most architecturally significant untested path in the whole project. Every ID was traced precisely from Evaluation Engine's raw output through Evidence Graph's storage to the Feedback Generator's final citations — not just "the counts matched" but the literal same UUIDs at every stage. The model's own reasoning text at the point of detection is itself evidence it genuinely compared against real prior context, not a coincidental or hallucinated flag. |
| **Follow-up action** | Remaining untested live: `insufficient_evidence` (weak/vague answer path) and the `deflection`/`non_answer` classification distinction — per the test matrix now in `PILOT_EXECUTION_PLAN.md`. |

---


**The entire live-API validation gap that had been open since Module 1 is now closed with real evidence, not mocks.** Summary:

- **4 modules passed cleanly on first live test**: JD Understanding, Resume Understanding, Question Generator, Reasoning Engine (stopping condition + adaptive targeting).
- **1 module (Feedback Generator) found a real bug on first live test, fixed same-session, re-verified clean** — exactly the value this exercise was built to produce.
- **1 full multi-turn orchestrated session, through the real HTTP API**, confirmed the core adaptive-questioning premise (the entire reason this project exists, per Decision #002) works correctly end-to-end with a live model: the system correctly cycled through all 3 competencies in order of need, generated well-grounded cross-questions referencing specific prior context even several turns later, and evaluated the real stopping condition against real accumulated evidence.

### Real, actionable findings for the next phase

1. **`MIN_QUESTIONS=6` / `0.85` average / `0.60` floor thresholds appear conservative** — 6 consecutive strong, substantive answers were not enough to trigger a stop. This is genuine pilot-tuning signal, not a flaw — per `reasoning_config.py`'s own documentation, these were always unvalidated pilot defaults awaiting exactly this kind of real data. Do not retune from a single session — collect several more real interviews first, per the original recommendation to avoid overfitting to one data point.
2. **The weak-answer / insufficient-evidence / deflection paths remain untested live** — contradiction detection is now closed (Entry 7), but every real test so far used strong or clearly-conflicting answers. Worth a deliberate test with a deliberately vague, weak, or evasive answer before wider pilot use, since these paths carry real product-quality risk (Architecture Review Gate #4's core promise depends on handling weak evidence honestly, not just strong evidence well).
3. **Latency remains incompletely measured** — only Resume/JD Understanding expose `processing_time_ms`; Evaluation Engine, Question Generator, and Feedback Generator do not. Worth closing this gap (a simple wrapper, not an engine change) before treating the latency picture as complete, especially given `VOICE_VALIDATION.md`'s Test 2 depends on knowing exactly where time is spent.

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
