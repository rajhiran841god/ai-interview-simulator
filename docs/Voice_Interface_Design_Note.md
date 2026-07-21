# Voice Interface — Design Note

**Status:** Implemented, verified with a real integration simulation
(not a live voice session). Live testing requires real LiveKit,
Deepgram, ElevenLabs, and Anthropic credentials — none available in
this environment. See Decision Log #004 for the full rationale.

## What this is

A new presentation-layer adapter — `backend/app/voice/agent.py` — that
lets a student speak to the interview instead of typing. **The
Interview Intelligence Engine (all 10 modules) is completely
unchanged.** This file only orchestrates existing services.

## How it works

LiveKit Agents provides one integration hook: `Agent.llm_node()` — the
point where the framework would normally call a generic chat LLM. We
override it instead to run our own engine:

```
Student speaks
    -> LiveKit's STT (Deepgram) transcribes it in real time
    -> llm_node receives the transcript via chat_ctx
    -> record_answer() [Conversation Memory — unchanged]
    -> evaluate_answer() [Evaluation Engine — unchanged]
    -> update_from_evaluation() [Competency Model — unchanged]
    -> decide_next_action() [Reasoning Engine — unchanged]
    -> generate_question() [Question Generator — unchanged]
    -> question text yielded from llm_node
    -> LiveKit's TTS (ElevenLabs) speaks it
    -> LiveKit's turn detector decides when the student starts/stops speaking
```

Everything in **bold-equivalent "unchanged"** above is literally the
same code, same classes, same tests as the text interface. Nothing in
`app/engine/` was modified for this.

## What was verified (and what wasn't)

**Verified, via direct code inspection and a scripted simulation (not
a live session):**
- The package (`livekit-agents==1.6.6`) installs cleanly and every
  class/method used (`Agent`, `AgentSession`, `llm_node`, `ChatContext`,
  `JobContext`, `WorkerOptions`, `cli`) is real and matches the
  installed version — checked via direct introspection, not assumed
  from documentation alone.
- A simulated two-turn conversation (fake transcript in, real engine
  calls, mocked only at the two LLM call sites) correctly: recorded
  both turns in Conversation Memory, wrote real evidence to Evidence
  Graph, updated Competency Model's confidence from 0.0 to 0.8, and
  produced a sensible follow-up question — end to end, through the
  real engine, not a stub.
- **Two real bugs were found and fixed during this verification**,
  not left for live testing to discover:
  1. `evaluate_answer()` was originally called before
     `record_answer()`. Evaluation Engine looks up the turn's
     `answer_text` via Conversation Memory internally (for Evidence
     Graph's provenance check) — calling it before the answer was
     recorded meant every evidence excerpt silently failed
     traceability against blank text. Fixed by recording the answer
     first.
  2. `CompetencyModel.update_from_evaluation()` was never called at
     all. Evaluation Engine deliberately does not update
     competency-level confidence itself (this was an explicit,
     documented scope boundary from Evaluation Engine's own
     contract) — some orchestrator has to do it. In the text-based
     test suites, the test itself played that role; here, the voice
     agent needed to do it and initially didn't. Without this fix,
     confidence would never move and Reasoning Engine would loop on
     the same competency indefinitely.

**NOT verified — cannot be, without live credentials:**
- Real speech-to-text accuracy on real student voices/accents
- Real turn-detection behavior (does it cut students off, or wait too
  long) — this is the single highest real-world risk named in
  Decision #004
- Real end-to-end latency (student stops talking -> AI starts
  speaking) — the two LLM calls in the loop (Evaluation Engine,
  Question Generator) are the parts most likely to make this feel
  slow, and this has never been measured
- Real TTS voice quality/naturalness

## What's needed to actually run this live

1. A LiveKit Cloud account (or self-hosted LiveKit server) + API keys
2. A Deepgram API key (STT)
3. An ElevenLabs API key (TTS)
4. A real Anthropic API key (same one blocked by the billing issue —
   this voice path has the exact same dependency)
5. A frontend page that joins the LiveKit room (replaces the "Voice
   Interview Screen" from the original product spec) — not yet built;
   this design note covers only the backend agent

## Explicit scope boundary (per Decision #004)

No custom STT, TTS, or turn-detection logic exists anywhere in this
codebase. If LiveKit's default turn detector proves unreliable in
practice, the fix is to tune its configuration or swap providers —
not to build a custom solution, per the decision's implementation
constraint.
