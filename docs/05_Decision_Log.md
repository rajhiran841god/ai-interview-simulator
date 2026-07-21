# Decision Log

> Every significant product or research decision gets an entry. The goal:
> six months from now, nobody has to argue from memory — they go back to
> the evidence. Every entry needs a stated falsification condition, not
> just a rationale, so decisions stay revisable rather than calcified.

---

## Decision #001 — Group Discussion (GD) is out of scope for v1

**Decision:** The product will focus exclusively on Personal Interview
(PI) simulation for v1. Group Discussion and Written Ability Test (WAT)
are treated as potential future modules, not part of the current problem
statement or MVP.

**Evidence:**
- GD involves fundamentally different communication dynamics (reading a
  room, competing for airtime, timing interjections) than a one-on-one
  interview — a different simulation problem, not a variant of the same
  one.
- Competitor research showed that Indian platforms which span many
  formats and exam types (engineering, MBA, government, teaching, GD,
  PI) tend to produce shallow, generic question banks — breadth
  correlated with a recurring user complaint across the market.

**Confidence:** Medium — based on reasoning and competitor pattern, not
yet on direct MBA student interview data.

**Owner:** Raj

**Falsification Condition:** If Phase 1 discovery interviews show that
GD performance is cited as an equal or greater source of placement
anxiety/failure than PI, this decision should be revisited before MVP
lock.

**Date:** July 2026
**Status:** Locked (pending Phase 1 results)

---

## Decision #002 — Engine-first architecture with a replaceable presentation layer

**Decision:** Adopt an engine-first architecture. The Interview
Intelligence Engine (resume/JD understanding, interview planning,
adaptive question generation, cross-questioning, competency tracking,
conversation memory, evaluation, feedback generation) is the core
product and the company's IP. Text, voice, and avatar are treated as
interchangeable presentation-layer interfaces sitting on top of the same
engine — not separate products.

**Context — how this decision was reached:** This followed a real
strategic back-and-forth, worth recording honestly rather than smoothing
over:
1. Original plan was research-first (interviews before any build).
2. Shifted toward a build-and-learn approach (ship v0.1, learn from real
   usage) as a legitimate alternative strategy.
3. Debate emerged specifically over whether a realistic avatar/voice
   interviewer belongs in v0.1, or whether "realism" is actually being
   driven by the quality of the questioning/reasoning rather than the
   presence of an avatar.
4. Resolved by separating the disagreement into an empirical question
   (does realism come from interface or from engine quality?) rather
   than settling it by argument.

**Validation Plan:**
- **Stage 1 (pilot usability study, ~20 students, text interface):**
  Test whether the engine itself — adaptive questioning,
  cross-questioning, evaluation — produces a "this felt like a real
  interview" reaction, using the cheapest interface (text) as the
  delivery mechanism. Questions: Did it feel like a real interview? Why
  or why not? Which moments felt most realistic / most artificial?
  Would you practice again tomorrow? What frustrated you? No pricing
  questions in this stage.
- **Important scoping note:** Stage 1 tests "engine + text interface,"
  not "engine in the abstract." A successful Stage 1 proves text is
  *sufficient* to validate the engine — it does not prove that voice or
  avatar wouldn't make the experience meaningfully better. Do not
  over-read a Stage 1 success as evidence that interface doesn't
  matter at all.
- **Stage 2 (only after Stage 1 shows the engine consistently produces
  "it actually challenged me" / "the follow-ups were sharp" type
  reactions):** Test interface variants — text vs. voice vs.
  voice+avatar — as a separate, later study, to learn whether richer
  presentation adds further value on top of an already-validated
  engine.

**Design Principle (adopted alongside this decision):** Never use
presentation quality to compensate for weak interview intelligence. A
polished avatar asking shallow questions is still a shallow interviewer;
a plain interface with excellent reasoning is far easier to improve
over time than the reverse.

**Confidence:** Medium — architecturally sound reasoning, not yet
tested against real users.

**Owner:** Raj

**Falsification Condition:** If Stage 1 users consistently report the
interview did not feel realistic *because of weak questioning or
reasoning* (not because of a flat interface), the engine needs rework
before any investment in richer presentation layers. Conversely, if
users say the questioning was sharp but a flat text interface broke the
illusion, that becomes real evidence to invest in Stage 2 (voice/avatar)
sooner rather than later.

**Date:** July 2026
**Status:** Locked (pending Stage 1 pilot results)

---

## Decision #003 — Shared type aliases: adopt going forward, defer retrofitting Modules 1–4

**Decision:** Going forward from Module 5 onward, enum-like fields
(e.g. `Relation`, `QuestionType`, `DecisionStrategy`) should be defined
once as shared type aliases and imported everywhere they're used,
rather than redefined per-module. Modules 1–4 (Resume Understanding,
JD Understanding, Conversation Memory, Evidence Graph) are NOT
retrofitted to this pattern now — they remain as-is, approved and
green.

**Evidence:** The same class of bug (a field typed as plain `str` in a
function signature when the schema defines it as a narrower
`Literal[...]`) was caught by mypy independently in both Module 3
(`question_type`) and Module 4 (`relation`) — a repeated pattern, not
an isolated incident, strongly suggesting it will recur in Module 5+
without a structural fix.

**Confidence:** High — this is a real, observed pattern (2 independent
occurrences), not a hypothetical risk.

**Owner:** Raj

**Falsification Condition:** If a shared-alias approach turns out to
create more friction than it saves (e.g. import cycles between
modules that should stay independent), revert to per-module type
definitions and note why in a follow-up entry.

**Why the refactor of Modules 1–4 is deferred, not skipped:** all four
are currently approved, tested green, and have frozen interfaces per
the schema-freeze discipline established after Module 2's review.
Touching four finished modules for a non-functional consistency
improvement introduces real regression risk for modest immediate
benefit. This should be scheduled as its own dedicated,
compatibility-focused change — not bundled into Module 5's scope, and
not left as an untracked TODO either. This entry is that tracking.

**Date:** July 2026
**Status:** Locked — apply going forward; retrofit scheduled as future
dedicated work, not yet started

---

## Decision #004 — Override Decision #002's validate-before-voice sequencing; adopt voice interface via mature third-party infrastructure, engine unchanged

**Decision:** Build a voice-based interview interface (student speaks,
AI speaks, no text/submit-button interaction) for the v0.1 MVP,
**before** running the Stage 1 text-based pilot validation that
Decision #002 specified as the prerequisite for investing in a richer
interface. The Interview Intelligence Engine (all 10 modules) is
unchanged — only a new presentation-layer adapter is added, consistent
with the engine/interface separation Decision #002 already
established. No custom speech recognition, turn-detection, or TTS
engine will be built — voice mechanics are delegated entirely to
mature, purpose-built third-party infrastructure (see implementation
note below).

**Why the previous decision was changed:** Decision #002 assumed the
primary open question was "does realism come from engine quality or
interface." That framing still matters, but it undervalued a second,
separate consideration that has become more important: **PlacementOS
is also evaluated on the strength of its first impression** — in
demos to students, faculty, and recruiters — not solely on measured
interview quality after the fact. A text-based demo risks being
perceived as "just another chatbot" regardless of how good the
underlying reasoning is, which affects adoption and credibility
independent of engine quality. This is a legitimate, separate
consideration from the original question Decision #002 was answering,
not a refutation of it.

**Assumptions being made (stated explicitly, not hidden):**
1. That first-impression/demo credibility is valuable enough to justify
   building voice before Stage 1 pilot evidence exists — this has not
   been tested, it is a judgment call.
2. That mature third-party voice infrastructure (STT, TTS, turn
   detection/VAD) is reliable enough out-of-the-box that this remains
   "integration work," not "hard systems engineering" — reasonable for
   well-established providers, but not yet verified against this
   specific engine's latency profile (Evaluation Engine + Question
   Generator each involve an LLM call in the loop, adding real latency
   between "student stops talking" and "AI starts speaking").
3. That the existing engine/interface separation is sufficient to
   support voice without any engine-side changes — plausible given the
   architecture, not yet proven in practice.

**Risks introduced:**
- **Latency risk:** a natural voice conversation has a much lower
  tolerance for pause-before-response than a text interface. The
  engine's per-turn LLM calls (classification, question generation)
  were never designed against a real-time latency budget. If responses
  feel sluggish, voice could make the experience feel *less* natural
  than text, not more — the opposite of the intent.
- **Turn-detection failure modes:** even mature VAD/endpointing can
  misfire (cutting off a student mid-thought, or waiting too long
  after they've finished) — this is a real, known failure mode of
  voice agent platforms generally, not unique to this build.
- **Demo risk becomes a new single point of failure:** a glitchy voice
  pipeline in front of faculty/recruiters could damage credibility
  more than a plain text interface would have, per the same competitor
  research (Module 6 era) that flagged this exact risk category.
- **Opportunity cost:** engineering time spent on voice integration is
  time not spent running the Stage 1 validation this project designed
  specifically to answer "does the engine actually work."

**Falsification condition:** If, once built, the voice interface
introduces response latency that makes the conversation feel
noticeably slower or less natural than a well-designed text interface
would have (i.e., voice actively works against the "feels real" goal
rather than for it), this decision should be revisited — either by
optimizing the latency path or by reverting to text for the actual
pilot validation, with voice retained only for demo purposes. This
should be evaluated with real users, not assumed from internal testing
alone.

**Implementation constraint (per this decision):** no custom speech
recognition, voice-activity-detection, or text-to-speech is built.
Voice mechanics are handled entirely by mature, purpose-built
infrastructure (e.g., a real-time voice-agent orchestration platform
handling WebRTC audio, STT, turn detection, and TTS), with the
existing engine's `ProviderAdapter` pattern extended — not replaced —
to add this as a new interface adapter alongside the existing text
path.

**Owner:** Raj

**Date:** July 2026
**Status:** Locked — this is a deliberate override, not a reversal;
Decision #002's underlying engine-first principle remains intact, only
the interface-sequencing timeline changes.

---

## Decision #005 — [Template for next entry]

**Decision:**

**Evidence:**

**Confidence:** High / Medium / Low

**Owner:**

**Falsification Condition:**

**Date:**
**Status:** Proposed / Locked / Revisited / Reversed
