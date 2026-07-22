# Session Report — Phase 2 (Design System) & Phase 3 (Voice Infrastructure)

**Status: Phase 2 complete and verified. Phase 3 infrastructure built
and confirmed working end-to-end via a real live voice conversation —
but with three real, substantive quality problems found in that first
successful run: question naturalness, response latency, and a sparse
feedback report at session end.** This report is honest about all
three, not just the fact that voice technically worked.

---

## Phase 2 — Design System & Redesign: COMPLETE

All 8 frontend pages redesigned against a locked design system
(`docs/PlacementOS_Design_System.md`) and verified with real clean
builds on your actual machine at every step:

- Design tokens locked (`tailwind.config.ts`): Ink/Paper/Evidence
  gold/Sage/Clay palette, Fraunces/Source Sans 3/IBM Plex Mono type
- Feedback Report — the "Evidence Margin" signature element
- Dashboard, Interview Setup, Interview Session, Lobby, Login, Signup
- A genuine, permanent bug found and fixed along the way: the
  Supabase client was constructed eagerly at module load, crashing
  any build without real credentials present — fixed via a lazy
  `Proxy`-based client

**Governance:** Decision Log #005 (pilot-premium-experience-first) and
#006 (engine freeze exception boundary — presentation-only changes)
both logged with full reasoning and falsification conditions.

## Phase 3 — Voice Infrastructure: BUILT, PARTIALLY LIVE-VERIFIED

### What was built and verified

1. **Voice token endpoint** (`/api/interviews/{id}/voice-token`) — real
   LiveKit JWT generation, verified by decoding actual issued tokens
   and confirming correct room-scoping. 176/176 tests.
2. **Frontend voice page** — real LiveKit React SDK integration
   (`useVoiceAssistant`, `LiveKitRoom`), verified with a clean 11/11
   page build including real Google Fonts fetch.
3. **Persistent Postgres storage** for all 5 engine stores
   (Conversation Memory, Evidence Graph, Logging, Competency Model,
   Session) — replacing in-memory storage that couldn't be shared
   between the FastAPI backend and the separate LiveKit voice worker
   process. 177/177 tests, verified against your real Supabase
   database (not just mocks).

### Real bugs found and fixed during live testing tonight

This is the substantive part of tonight's work — every one of these
was found only because live testing was actually attempted, not
because of a code review:

| # | Bug | How it was found | Fix |
|---|---|---|---|
| 1 | Voice worker process couldn't load `.env` — `.env` loading is automatic for the FastAPI backend (via pydantic-settings) but not for a standalone CLI process | `ValueError: ws_url is required` despite `.env` being correctly set | Added explicit `load_dotenv()` at the top of `agent.py` |
| 2 | `Settings` rejected `DEEPGRAM_API_KEY`/`ELEVEN_API_KEY` as unknown fields (pydantic's `extra_forbidden` default) | Validation error crash, which also **printed both API keys in plaintext in the traceback** — both keys were rotated as a precaution | Added `extra = "ignore"` to `Settings.Config` |
| 3 | `AgentSession` was never given an `llm=` parameter, so LiveKit's pipeline never recognized there was a "generation step" to run — `llm_node` was never invoked at all | Real log showed STT and turn-detection working perfectly (accurate transcripts, correct turn commits) but zero response, ever | Added `llm=anthropic.LLM()` — never actually called for generation, exists only so the pipeline reaches the point of invoking our override |
| 4 | `anthropic==0.34.2` (old Milestone 1 pin) conflicted with the new `livekit-plugins-anthropic` package's requirement of `anthropic>=0.41` | `pip install` dependency resolution failure | Bumped to `anthropic==0.117.0`, verified our existing `AnthropicProvider` class still works correctly against it |
| 5 | **The core cross-process bug**: in-memory storage meant the FastAPI backend and the separate LiveKit voice worker process could never see each other's data | `"No competencies initialized"` even immediately after initializing them via a real HTTP call | Built persistent Postgres-backed stores for all 5 engine components, with a `STORE_BACKEND` switch so the offline test suite still runs without needing real database access |
| 6 | Even after building the Postgres stores, `app/voice/agent.py`'s `entrypoint()` still constructed fresh, disconnected, default in-memory services — never updated to actually use the new persistent stores | Same `"No competencies initialized"` symptom recurred even after the Postgres fix, on a freshly created session | `entrypoint()` now imports and reuses the exact same shared singletons the backend uses (`app.orchestrator.engine_singletons`) |
| 7 | mypy's real, correct complaint about postgrest's generic JSON return type led to a genuinely useful shared `as_json_dict()` helper, used consistently across all 5 new store implementations, instead of scattering type-ignore comments | mypy run after building the stores | Added the helper, verified 0 mypy findings across all 8 touched files |
| 8 | `update_answer()`/`get_turn()` methods had unguarded `Optional` unwraps that would crash on a genuinely missing turn, instead of raising the same explicit error the in-memory version raises | Caught during the mypy cleanup pass, same recurring pattern as earlier in this project (Modules 3, 4, 8, 9, 10) | Added explicit `None` checks raising the correct, existing error codes (`ANSWER_WITHOUT_QUESTION`, `TRACE_NOT_FOUND`, etc.) |

### Setup issues encountered (not code bugs — real friction worth documenting)

- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `.env` were still
  Milestone-1-era placeholder values (`https://your-project.supabase.co`)
  — never actually needed to be real until persistent storage made
  them load-bearing. Fixed by retrieving the real project URL and
  service_role key from the Supabase dashboard.
- The SQL migration (`migrations/001_persistent_stores.sql`) initially
  failed to run because terminal prompt text (`(venv) ... % cat ...`)
  got pasted into the Supabase SQL Editor along with the actual SQL —
  fixed by pasting only the real SQL content.
- `uvicorn --reload` doesn't auto-recover from an import-time crash —
  it needs a manual restart, which caused confusion when the backend
  appeared "stuck" after a credentials error.

### CONFIRMED: The voice pipeline worked end to end

**Update, after the report below was first drafted:** the live retest
succeeded — the AI's voice was actually heard, and it asked real
questions. This confirms every fix above (the `llm=` parameter, the
persistent storage, the shared singletons) genuinely worked together.

**However, three real, substantive problems were found in this first
successful run, not polish items:**

1. **Question quality/naturalness** — the questions didn't feel human;
   quality was reported as poor. Needs investigation: is this about
   phrasing that reads fine as text but sounds awkward spoken aloud,
   or a deeper issue with the actual questions being generated?
2. **Latency** — noticeably slow to respond and ask questions. This
   directly matches the ~7.2s engine-only latency figure already
   measured in `LIVE_VALIDATION_LOG.md` (Evaluation Engine + Question
   Generator combined) — now confirmed as a real, felt problem in an
   actual conversation, not just a number on a page.
3. **Feedback report at session end was sparse** — described as "only
   4 points." Needs clarification: is this the actual `/report`
   endpoint response being thin, a UI rendering issue on the redesigned
   report page, or something specific to how the voice session ended
   the interview.

These three findings are exactly what `VOICE_VALIDATION.md`'s Test 2
(latency) and the broader "does this feel real" question were designed
to surface — this is genuine, valuable pilot-readiness signal, not a
setback.

### What was NOT confirmed (superseded by the above)

**The actual end-to-end voice conversation — student speaks, AI
responds out loud — was never confirmed successful.** The session was
stopped by the user before establishing whether the final retest (with
all 8 fixes above in place) actually produced an audible AI response.

This is the single most important open item. Everything upstream of
it (STT, turn detection, persistent storage, `llm_node` invocation) has
now been individually verified working — but the full chain, end to
end, with actual audio played back to a human, has not.

## Test Suite Status

**177/177 tests passing**, confirmed on the real development machine
against the real Supabase database (not mocks) as of the last
verified run tonight. Tooling (black/ruff/mypy) clean across all
touched files.

## Test Matrix — Isolating Variables Before Further Changes

The "generic questions" complaint from tonight's live test was
diagnosed as likely incomplete rather than a Question Generator flaw:
**no resume was uploaded** in any test tonight, only a JD via curl.
Since the architecture is designed to combine Resume Understanding +
JD Understanding + Evidence Graph → Question Generator, one-third of
the intended input was missing. Before touching any prompt or engine
logic, the following test matrix isolates this properly:

| Test | Resume | JD | Voice | Expected |
|---|---|---|---|---|
| A | ❌ | ✅ | Yes | Generic (this is what tonight actually tested) |
| B | ✅ | ❌ | Yes | Resume-based only |
| C | ✅ | ✅ | Yes | Personalized — the real "Golden Path" |
| D | ✅ | ✅ | Text | Compare voice vs. text experience directly |

**Recommendation: run Test C (the Golden Path) before making any
further changes to the Question Generator, latency, or voice
quality.** If personalization is still poor with both resume and JD
present, that's real evidence the Question Generator needs work. If
it's genuinely better, tonight's diagnosis was correct and no engine
changes are needed for the personalization complaint specifically.

### Four separate problems, not one

Tonight's feedback ("voice isn't good") actually decomposes into four
independent problems, each with a different fix:

| Problem | Cause | Fix path |
|---|---|---|
| A. Generic questions | Resume never uploaded in testing | Retest with Golden Path first |
| B. Voice quality/naturalness | ElevenLabs voice/model choice | Try a different voice/model |
| C. Latency | ~7.2s engine-only (already measured) + STT/TTS overhead | Faster model for Question Generator, streaming, reduced context |
| D. Conversational style/tone | Generic AI phrasing vs. real recruiter tone | Future improvement, informed by placement cell research (see below) |

## Placement Data Research — Separate, Parallel Track

A separate initiative, explicitly NOT touching the engine yet:

**Goal:** understand what real interview data the placement cell can
share, and whether it's rich enough to justify any future engine work
— not to build anything yet.

**Explicit non-goals for this phase:** no engine changes, no new AI
modules, no prompt modifications, no "Recruiter DNA" architecture, no
feature commitments.

**Process:** collect whatever data exists in whatever format (Excel,
PDFs, interview experience write-ups, etc.) → build a "Research
Notebook" with a strict Observation / Evidence / Confidence / Design
Idea (hypothesis, not implemented) / Unknown template → only after
the notebook is complete, decide whether the data justifies an
experiment, a formal proposal, or no engine changes at all.

**Watch-outs flagged for this process:** be precise about what a
"confidence" number actually represents (12 interviews at one company
vs. 12 pooled across many companies are very different strengths of
evidence); watch for survivorship bias (write-ups skew toward
students confident enough to share them); rejected-candidate data
needs real caution, since rejection often reflects factors unrelated
to interview quality (hiring limits, budget, internal candidates), not
a clean "bad interview" signal.

## Immediate Next Step (Revised)

**Before optimizing latency, voice quality, or touching the Question
Generator: run the Golden Path Test (Test C above)** — real resume,
real JD, voice mode, one complete interview — and record: total
latency, question quality, follow-up/cross-referencing quality, voice
quality, and report quality. Only after that result is known should
any further engineering decision be made.

