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

## Decision #003 — [Template for next entry]

**Decision:**

**Evidence:**

**Confidence:** High / Medium / Low

**Owner:**

**Falsification Condition:**

**Date:**
**Status:** Proposed / Locked / Revisited / Reversed
