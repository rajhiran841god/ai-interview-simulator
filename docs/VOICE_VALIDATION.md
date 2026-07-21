# Voice Interface — Validation Document

**Status: Offline/simulated verification complete. Live integration
verification NOT done — requires live credentials this environment
does not have.** This document exists so the distinction between
those two states never gets blurred, six months from now or six days
from now.

---

## Architecture

```
Student's browser (mic)
    │  WebRTC audio
    ▼
LiveKit room
    │
    ▼
LiveKit Agent process (backend/app/voice/agent.py)
    │
    ├─► Deepgram STT (streaming) ──► transcript text
    │
    ├─► InterviewVoiceAgent.llm_node()  [THE ONLY CUSTOM HOOK]
    │       │
    │       ├─► ConversationMemoryService.record_answer()   [unchanged engine]
    │       ├─► EvaluationEngineService.evaluate_answer()    [unchanged engine]
    │       ├─► CompetencyModelService.update_from_evaluation() [unchanged engine]
    │       ├─► ReasoningEngineService.decide_next_action()  [unchanged engine]
    │       └─► QuestionGeneratorService.generate_question() [unchanged engine]
    │
    └─► ElevenLabs TTS ──► synthesized audio ──► back through LiveKit ──► student hears it
```

The Interview Intelligence Engine (all 10 modules) is untouched. This
file is a **presentation-layer adapter only** — see Decision Log #004.

## Dependencies

| Component | Provider | Role | Status |
|---|---|---|---|
| Room/transport | LiveKit (Cloud or self-hosted) | WebRTC audio streaming, room lifecycle | Configured, not live-tested |
| STT | Deepgram (nova-3 model) | Real-time speech-to-text | Configured, not live-tested |
| TTS | ElevenLabs | Text-to-speech | Configured, not live-tested |
| Turn detection | LiveKit's built-in semantic model | Deciding when the student has finished speaking | Default config, not tuned |
| LLM (for the engine's own calls) | Anthropic Claude, via existing `ProviderAdapter` | Evaluation Engine + Question Generator's actual reasoning | **Blocked on Anthropic billing — same gap as every other LLM-backed module** |

## Audio Pipeline — What's Actually Verified vs. Not

**Verified (offline, via `tests/voice/test_voice_agent.py`, 6 tests, all passing):**
- `llm_node`'s orchestration logic correctly sequences calls into the
  real engine given a fake transcript.
- Evidence is correctly recorded, traceable, and rejected when
  fabricated (reusing Evidence Graph's existing guarantees).
- Competency confidence correctly updates after an evaluated answer.
- A "stop" decision correctly yields a stop reason, not another question.
- The adapter is structurally independent — doesn't modify or import
  engine internals beyond calling their public APIs.

**NOT verified — cannot be, without live credentials and hardware:**
- Real STT accuracy on real speech (accents, speaking pace, filler words)
- Real turn-detection behavior under real pauses, hesitation, "let me think"
- Real TTS voice quality and naturalness
- Real end-to-end latency
- Real network failure recovery
- Real background noise robustness

## Known Failure Modes (Designed For, Not Yet Observed Live)

| Scenario | Current behavior | Verified? |
|---|---|---|
| Evaluation Engine's LLM call fails | Returns degraded `EvaluationResult` (non_answer, 0 confidence), does not crash the turn | ✅ Unit-tested (Module 6) |
| Question Generator's LLM call fails | Falls back to a templated question after one retry | ✅ Unit-tested (Module 9) |
| Reasoning Engine has no competencies initialized | Raises `NO_COMPETENCIES_INITIALIZED` — an orchestration bug upstream, not recoverable here | ✅ Unit-tested (Module 8) |
| Network drops mid-interview | **Unknown.** LiveKit has reconnection handling by default, but this agent's session-recovery behavior (does `_pending_question_id` state survive a reconnect?) has not been tested | ❌ Open — Test 3 below |
| Student pauses to think (several seconds of silence) | Depends entirely on LiveKit's turn-detection model's tuning — not customized, using defaults | ❌ Open — Test 4 below |
| Background noise (fan, keyboard, other voices) | Depends entirely on Deepgram's real-world accuracy — not tested against any real audio | ❌ Open — Test 6 below |

## Latency Budget (Target, Not Measured)

No real measurement exists yet. Rough budget reasoning, to be
validated against Test 2 below:

| Stage | Rough expectation | Confidence |
|---|---|---|
| STT transcription | ~200-500ms (streaming, mature provider) | Reasonable, based on provider claims |
| Evaluation Engine's LLM call | Unmeasured — same call as the text pipeline's live-API gap | **Unknown — this is the real risk** |
| Reasoning Engine + Question Generator | Reasoning Engine: ~instant (deterministic). Question Generator: one more LLM call, unmeasured | **Unknown** |
| TTS synthesis | ~200-500ms for short text (mature provider, streaming) | Reasonable, based on provider claims |
| **Total, rough estimate** | **1.5-3+ seconds**, dominated by the two LLM calls | **Not validated — could be meaningfully worse** |

**This is the single most important open question before calling voice
production-ready.** A 1.5-3 second pause between "student stops
talking" and "AI starts speaking" may already feel unnatural — real
measurement (Test 2) is not optional polish, it's the test that tells
you whether this entire approach works as intended.

## Configuration

- `backend/app/voice/agent.py` — the adapter itself
- Environment variables needed at deploy time (not yet added to
  `.env.example` — do this before deploying): `LIVEKIT_URL`,
  `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`,
  `ELEVENLABS_API_KEY`, plus the existing `ANTHROPIC_API_KEY`
- `pytest.ini` — added to enable `pytest-asyncio` for this module's tests
- Room naming convention: `ctx.room.name` is used directly as
  `interview_id` — this is a placeholder convention, not yet connected
  to a real session-creation flow (Phase 1's backend session endpoints
  don't exist yet)

## Deployment (Not Yet Done)

This agent needs to run as a long-lived LiveKit worker process,
separate from the FastAPI backend — not a request-handler endpoint.
Typical deployment is a dedicated process/container that registers
with LiveKit and receives one "Job" per interview room. No deployment
configuration exists yet for this.

## Pending Live Validation Checklist (run once Anthropic billing clears)

These are the 6 tests specifically requested, kept as an explicit,
checkable list rather than prose, so nothing gets skipped:

- [ ] **Test 1 — Full real pipeline**: real mic → LiveKit → Deepgram →
      engine → Claude → Question Generator → ElevenLabs → speaker.
      Confirm it works at all, end to end, once.
- [ ] **Test 2 — Latency measurement**: timestamp "student stopped
      speaking" and "AI started speaking" for every turn across a full
      interview. Report average, max, and 95th percentile — not a
      subjective "feels fast/slow."
- [ ] **Test 3 — Network interruption**: disconnect mid-interview.
      Document actual behavior (crash / silent hang / recovers /
      shows an error) — do not assume LiveKit's default reconnection
      handling is sufficient without observing it.
- [ ] **Test 4 — Long pause tolerance**: student pauses ~4 seconds
      mid-thought. Does the AI interrupt, or wait appropriately?
- [ ] **Test 5 — "Let me think" handling**: student says a filler
      phrase indicating they're not done. Does turn detection
      correctly keep waiting, or prematurely conclude the turn ended?
- [ ] **Test 6 — Background noise robustness**: real fan/keyboard/
      background conversation noise. Does STT transcription degrade
      gracefully or badly?

**None of these six can be simulated credibly — they require the real
services and, ideally, a real person speaking naturally, not a
scripted test utterance.**

## Known Limitations (Restated Plainly)

- No custom STT/TTS/turn-detection exists or should be built, per
  Decision #004 — if the above tests reveal problems, the fix is
  configuration/provider-tuning, not custom engineering.
- Session/room creation, resume/JD upload wiring, and the actual
  frontend "Voice Interview Screen" (Phase 1/2 of the original product
  spec) do not exist yet — this document covers only the backend
  voice agent.
- `interview_id` derivation from `ctx.room.name` is a placeholder
  convention that needs a real session-management design once Phase 1
  backend work happens.

## Future Improvements (Not Now)

- Real latency optimization (streaming partial LLM output into TTS
  before the full response is ready — LiveKit supports this, not yet
  implemented here)
- Persistent session recovery after a network drop
- Tuning turn-detection sensitivity based on real observed behavior
  from the pending validation checklist above, not guessed in advance
