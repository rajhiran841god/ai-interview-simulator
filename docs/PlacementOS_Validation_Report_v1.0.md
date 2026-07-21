# PlacementOS — Validation Report v1.0

**Date:** July 2026
**Architecture version:** `256f66e` (main branch, github.com/rajhiran841god/ai-interview-simulator)
**Status:** Interview Intelligence Engine complete and frozen. Backend
orchestration, frontend, and voice adapter built. Live-API validation
substantially complete. Not yet piloted with real students.

This document exists so the project's actual engineering history is
reconstructable without re-reading the full development log — for
future reference, and for any external audience (investors, incubators,
recruiters, faculty) who need an accurate picture of what has and
hasn't been proven.

---

## 1. What Was Built

### Interview Intelligence Engine (10 modules, `docs/contracts/` + `docs/reports/`)

| Module | Purpose | LLM-backed? |
|---|---|---|
| Resume Understanding | Structured, provenance-tracked resume extraction | Yes |
| JD Understanding | JD-derived competency extraction, no fixed vocabulary | Yes |
| Conversation Memory | Turn-by-turn interview record | No |
| Evidence Graph | Links evidence to source, tracks contradictions | No |
| Logging / Trace Recorder | Records why each question was asked | No |
| Evaluation Engine | Classifies answers, extracts evidence, detects contradictions | Yes |
| Competency Model | Aggregates evidence into per-competency confidence | No |
| Reasoning Engine | Decides what to ask next and when to stop | No |
| Question Generator | Turns a decision into actual question text | Yes |
| Feedback Generator | Evidence-grounded, confidence-free student report | Yes |

Each module has its own versioned contract, was independently reviewed
before implementation, and has its own Implementation Report
documenting real findings — see `docs/contracts/` and `docs/reports/`.

### Supporting Infrastructure

- **Backend orchestration** (`app/orchestrator/`, `app/api/interviews.py`)
  — real HTTP API (7 endpoints) connecting the engine to the outside
  world, with a concurrency guard protecting interview integrity
- **Frontend** — 7 pages (login, signup, dashboard, resume/JD upload,
  lobby, interview session, report), text-mode, honestly labeled where
  voice isn't wired in
- **Voice adapter** (`app/voice/agent.py`) — LiveKit + Deepgram +
  ElevenLabs integration, engine completely unchanged, isolated and
  independently removable
- **Turn-level latency diagnostics** (`app/shared/turn_timer.py`)
- **Provider abstraction** supporting both direct Anthropic access and
  a validation-only third-party gateway (`app/core/provider_adapter.py`)

### Test Suite

**171 automated tests, 0 failures**, covering all of the above (mocked
LLM calls throughout — see Section 3 for what's been tested against a
*real* model).

---

## 2. Engineering Discipline Applied

Every module went through the same cycle: **Architecture → Contract →
Independent Review → Implementation → Real Test Execution → Tooling →
Implementation Report.** No module was merged without its contract
being reviewed first, and no Implementation Report claimed success
without actually running the relevant tests and pasting real output.

Two formal governance documents anchor this:
- **`docs/05_Decision_Log.md`** — every major architectural decision,
  each with a stated falsification condition (e.g. Decision #002:
  engine-first, text before voice; Decision #004: the deliberate
  override to build voice ahead of full pilot validation, with its own
  named risks)
- **`docs/07_Architecture_Review_Gate.md`** — the 8-criterion gate the
  core architecture had to pass before implementation began

---

## 3. Live Validation — What's Been Tested Against a Real Model

Full detail in `docs/LIVE_VALIDATION_LOG.md`. Summary:

| # | Scenario | Result |
|---|---|---|
| 1 | JD Understanding — real JD text | ✅ Pass |
| 2 | Resume Understanding — real PDF | ✅ Pass (probe-worthy-claim detection confirmed working live) |
| 3 | Evaluation Engine — strong real answer | ✅ Pass |
| 4 | Question Generator — real cross-question, grounded in prior context | ✅ Pass |
| 5 | Feedback Generator — real report generation | ⚠️ Real bug found (evidence IDs leaking into prose) — fixed same session, re-verified clean |
| 6 | Full multi-turn session via real HTTP API — 6 real Q&A turns across 3 competencies, ending in a real report | ✅ Pass — adaptive competency-switching confirmed working live |
| 7 | Deliberate contradiction scenario — two conflicting real answers | ✅ Pass — traced ID-by-ID from Evaluation Engine through Evidence Graph to the final report |

**All testing used `aicredits.in`, a third-party validation-only
gateway — not a direct Anthropic account.** Latency figures below
include gateway/network overhead on top of actual model inference and
should be treated as a current baseline via this specific provider,
not a measurement of Claude's real speed.

---

## 4. Bugs Discovered and Fixed (Project-Wide, Real Instances Only)

This list is restricted to genuine bugs caught during development or
live validation — not stylistic nitpicks.

| Bug | Found by | Fixed |
|---|---|---|
| `pdfplumber`'s `is_encrypted` attribute doesn't exist — every real PDF upload would have crashed | Real-file testing (Module 1) | ✅ |
| Password-protected PDF detection failed silently (`str(exception)` was empty for the real exception type) | Real-file testing (Module 1) | ✅ |
| `evaluate_answer()` called before `record_answer()` — Evidence Graph's provenance check silently failed against blank answer text | Own code review during voice adapter build | ✅ |
| `CompetencyModel.update_from_evaluation()` never called in the voice orchestration path — confidence would never update, Reasoning Engine would loop forever | Own code review during voice adapter build | ✅ |
| Recurring `str`-vs-`Literal` typing gaps (5 separate instances across Modules 3, 4, 8, 9, 10) | mypy, after adopting stricter config | ✅ (all instances); stricter `mypy.ini` adopted project-wide to catch this class going forward |
| Real Optional-unwrap gaps in `auth.py` (Supabase `user`/`session` could be `None`, uncaught) | Hardening pass, stricter mypy | ✅ |
| **Feedback Generator embedded raw internal `evidence_id` UUIDs directly in student-facing prose** | **Live validation, Entry 5** | ✅ Fixed two ways: prompt clarified + structural regex safeguard added; re-verified clean on a fresh live call |
| Two chained-assignment test bugs (`x = y = None` silently overwriting a live object's method) | Ran tests for real, didn't just write them (Modules 4, 9) | ✅ |
| Two test-design bugs (fixture text accidentally similar across interviews; checking source text instead of import statements) | Ran tests for real (Module 3) | ✅ |

**Pattern worth naming:** nearly every bug above was caught specifically because of "run it for real, don't just trust it compiles" discipline — mocked unit tests structurally could not have caught most of these.

---

## 5. Known Limitations (Honestly Stated, Not Hidden)

- **No persistence** — all engine state is in-memory, single-process. A backend restart loses every active interview. Architecturally ready for a Postgres swap (every store is behind an abstraction built for this), not yet implemented. See `docs/Session_Lifecycle_And_Persistence.md`.
- **No session cleanup/TTL** — sessions accumulate in memory indefinitely. Fine for a small supervised pilot, not for broader use.
- **Voice pipeline never live-tested** — `VOICE_VALIDATION.md`'s 6 real-world tests (real mic, measured latency, network interruption, long pauses, "let me think" handling, background noise) are all still pending live credentials for LiveKit/Deepgram/ElevenLabs.
- **Latency incompletely measured** — only Resume/JD Understanding expose timing; Evaluation Engine, Question Generator, and Feedback Generator do not yet.
- **Weak-answer / insufficient-evidence / deflection paths untested live** — every live test so far used strong or clearly-conflicting answers. The `insufficient_evidence` and deflection-classification paths are unit-tested with mocks only.
- **`switch_competency` reasoning strategy is genuinely unimplemented** — a known, stated architectural gap from Module 8, not a bug.
- **No real Anthropic account used yet** — all live validation ran through a third-party gateway, chosen deliberately as a low-cost bridge to unblock testing (see Decision Log), not the intended production path.
- **Next.js 14.2.5 has a known security vulnerability** — flagged, not yet upgraded (a deliberate decision, not an oversight, to avoid an untested version bump mid-validation).
- **Two-tab concurrency race condition** — fixed with a lightweight, single-process guard (409 rejection), not distributed locking. Sufficient for a small supervised pilot only.

---

## 6. Metrics Collected

| Module | Latency (via aicredits.in gateway) |
|---|---|
| JD Understanding | 3,892 ms |
| Resume Understanding | 7,238 ms |
| Evaluation Engine | Not captured (no timing wrapper yet) |
| Question Generator | Not captured |
| Feedback Generator | Not captured |

**Test suite:** 171 automated tests, 0 failures, tooling (black/ruff/mypy) clean project-wide.

**Live validation:** 7 scenarios tested, 6 passed cleanly, 1 found a real bug (fixed and re-verified same session).

---

## 7. Open Questions for the Next Phase

1. **Are the stopping-condition thresholds (`MIN_QUESTIONS=6`, 0.85 average confidence, 0.60 floor) well-calibrated?** Live evidence from Entry 6 suggests they may be conservative — 6 consecutive strong answers didn't trigger a stop. Needs several more real sessions before retuning, not a single data point.
2. **Does the engine's questioning genuinely feel adaptive to a real student**, or does it read as generic despite the underlying mechanism working correctly? (Decision #002's original, still-unanswered question.)
3. **Does voice interaction help or hurt the realism goal**, once real latency and turn-detection behavior are known? (Decision #004's stated falsification condition.)
4. **Is the feedback report perceived as trustworthy and specific by a real reader**, not just verified as evidence-grounded by the person who built it?

These four questions are exactly what `docs/PILOT_EXECUTION_PLAN.md` is designed to answer — this report is a snapshot of engineering validation, not product validation. The next phase answers a different kind of question than this one does.

---

## Document History

This is v1.0, written after the live-API validation phase and before
any real student pilot. Treat future versions of this report as a
running record — update after the pilot with real outcomes, not as a
replacement for `LIVE_VALIDATION_LOG.md`'s or `PILOT_EXECUTION_PLAN.md`'s
detailed entries, which this document summarizes but doesn't replace.
