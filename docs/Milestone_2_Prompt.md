You are the Lead Software Architect for Version 0.1 of our startup,
continuing from Milestone 1 (repository scaffold, auth, planning docs —
already complete and present in /docs).

Before designing anything, read every file in /docs. That is the
source of truth. If any instruction below conflicts with those
documents, stop and explain the conflict instead of silently resolving
it in either direction.

==================================================
MILESTONE 2 GOAL
==================================================

Design the complete Interview Intelligence Engine architecture.
No implementation code. Design only.

This design will be evaluated against
docs/07_Architecture_Review_Gate.md and must pass all 8 criteria before
any engine implementation begins.

==================================================
CORE PRODUCT PHILOSOPHY (this defines the architecture)
==================================================

Do not design a chatbot. Do not design a linear question-answer loop.

Design a reasoning engine whose governing question is:

"What is my current confidence in evaluating each competency, and what
evidence do I still need to reach a confident, evidence-backed
assessment?"

The engine does not optimize for asking questions. It optimizes for
collecting sufficient evidence to make a transparent, competency-based
evaluation of a candidate.

The AI does not simply pick "the next question." It:
1. Maintains a confidence estimate per competency (e.g. Communication,
   Leadership, Problem Solving, Business Thinking, Role Fit — exact set
   should be derived from JD + resume, not hardcoded).
2. Identifies which competency currently has the least supporting
   evidence or lowest confidence.
3. Generates a question (or cross-question / follow-up) specifically
   targeted at closing that evidence gap.
4. Evaluates the candidate's answer, extracts evidence, updates
   confidence.
5. Repeats until a stopping condition is met (see Stopping Condition
   below).

==================================================
CRITICAL CONSTRAINT — HOW CONFIDENCE SCORES MAY BE USED
==================================================

Internal competency confidence scores (e.g. "Leadership: 40%") are
engine-internal reasoning signals only. They represent the engine's
current confidence that it has collected *sufficient evidence* to
assess a competency — they are NOT objective measures of a candidate's
true ability, and must never be presented to this effect.

Hard rules:
- Confidence scores/percentages are NEVER shown verbatim to the
  student in any UI or report.
- All student-facing feedback must be the qualitative,
  evidence-grounded explanation (see Evidence-Based Feedback below) —
  never a bare number or grade derived directly from the internal
  confidence model.
- The architecture must document, explicitly, what the confidence
  score represents ("confidence that enough evidence has been
  collected," not "how good the candidate is") so this distinction
  survives future engineering handoffs.
- This constraint itself must be captured as ADR 0006 (see ADRs below)
  so it cannot be quietly dropped later when someone is optimizing the
  feedback UI.

==================================================
STOPPING CONDITION (interview length adapts to the candidate)
==================================================

Do not use a fixed question count. Design a stopping condition based on
aggregate and per-competency confidence crossing a threshold — but with
explicit safeguards for a small pilot:

- Minimum question floor: the interview must not end suspiciously
  early even if early answers are strong — define a sensible minimum.
- Maximum question ceiling with graceful exit: if a competency's
  confidence will not converge (e.g. a genuinely weak or ambiguous
  area), the engine must not loop indefinitely trying to force
  confidence upward. At some point, "the evidence suggests this
  competency is weak or unclear" is itself a valid, evidence-backed
  finding — not a failure state requiring more probing.
- Document both bounds explicitly and explain the reasoning behind the
  chosen values.

==================================================
STATE MACHINE — TWO LAYERS
==================================================

Design two distinct layers and be explicit about which parts are truly
fixed vs. dynamically ordered. Do not blur them.

**Layer 1 — Fixed Lifecycle** (linear, does not change):
START → Consent → Resume Upload → JD Upload → Greeting → Interview →
Evaluation → Feedback → END

**Layer 2 — Dynamic Reasoning Loop** (inside "Interview" — order is
computed, not scripted):
Evidence state (per competency) → Confidence model → Identify missing
evidence → Reasoning engine selects target competency → Generate
question/cross-question → Candidate answers → Extract evidence →
Update confidence → Check stopping condition → Loop or exit

There is no fixed competency order (e.g. no hardcoded "Leadership then
Marketing then HR"). The engine decides based on evidence gaps.

==================================================
EVIDENCE-BASED FEEDBACK (Gate Criterion #4 — must be satisfiable by
construction, not bolted on after)
==================================================

Every piece of feedback must be traceable to:
- Which interview question produced it
- Which specific part of the candidate's answer supports it
- Which competency was being evaluated

Generic feedback ("improve your leadership examples") is not
acceptable. Feedback must read like: "When answering the question
about your internship, you described the outcome but did not explain
how you personally influenced the team, which made it difficult to
assess your leadership competency." Design the data model so this
traceability is structural, not something reconstructed after the fact
from logs.

==================================================
LOGGING / REASONING TRANSPARENCY (Gate Criterion #5 — part of the
architecture, not an afterthought)
==================================================

Every question the engine asks must automatically produce a structured
record containing at minimum:

- Interview ID
- Question ID
- Target competency
- Current confidence (pre-question)
- Evidence identified as missing
- Reason for asking this specific question
- Prompt version
- Model version
- Candidate's answer
- Evidence extracted from the answer
- Updated confidence (post-question)

This must be inspectable — if a student later says "the follow-up
questions felt irrelevant," this log should let you actually check
why the engine chose that question, rather than treating the engine as
a black box.

==================================================
PILOT LEARNING LOOP (Gate Criterion #6)
==================================================

Design where and how post-interview pilot feedback is captured:
Interview Complete → Evaluation Report → Pilot Feedback Form (Did this
feel like a real interview? Which question felt most/least realistic?
Was any feedback especially useful? What frustrated you? Would you
practice again?) → stored in a way that's easily reviewable by the
founder, not buried in raw logs.

==================================================
MODULE BREAKDOWN
==================================================

Break the engine into independent modules. For each module, specify:
- Purpose
- Inputs
- Outputs
- Responsibilities
- Interaction with other modules

Expected modules include (adjust as the design requires): Resume
Understanding, JD Understanding, Competency Model / Confidence
Tracker, Evidence Graph, Reasoning/Decision Engine, Question
Generator, Cross-Questioning Engine, Conversation Memory, Evaluation
Engine, Feedback Generator, Logging/Trace Recorder.

Do not nest this under a generic "services/" folder as a permanent
home — propose a more specific structure (e.g. app/engine/ with
submodules) but do not restructure Milestone 1's existing folders
today; just specify the target structure for Milestone 2 code to land
in.

==================================================
PROVIDER INDEPENDENCE
==================================================

No module may couple business logic directly to a specific LLM
provider. Anthropic Claude is the current choice (see
backend/app/core/config.py from Milestone 1) but the design must make
swapping providers a matter of changing one abstraction layer, not
rewriting the engine.

==================================================
ARCHITECTURE DECISION RECORDS (ADRs)
==================================================

Create docs/ADR/ with one-page records for the decisions already made
in this project, so the reasoning survives beyond chat history:

- 0001-engine-is-core-ip.md
- 0002-provider-abstraction.md
- 0003-engine-presentation-separation.md
- 0004-build-first-pilot-strategy.md
- 0005-evidence-driven-reasoning.md
- 0006-confidence-scores-are-internal-reasoning-signals-not-ability-measures.md

Each ADR: context, decision, consequences, alternatives considered.

==================================================
DELIVERABLE FORMAT
==================================================

Produce this as a design document (markdown), not code:
1. Module breakdown (as specified above)
2. The two-layer state machine, illustrated
3. The confidence/evidence data model
4. The stopping condition logic, with floor/ceiling values and
   reasoning
5. The logging/trace schema
6. The six ADRs
7. A short section explicitly walking through each of the 8
   Architecture Review Gate criteria, explaining how this design
   satisfies it (or flagging where it doesn't yet)

==================================================
RULES
==================================================

- No implementation code in this milestone.
- If there are multiple reasonable approaches to any design choice,
  present the options and trade-offs, recommend one, and explain why —
  do not silently pick one.
- Do not expand scope. If you identify something valuable but outside
  Milestone 2 or v0.1, add it to docs/FUTURE_ROADMAP.md instead of
  designing it in.
- Stop after producing the design document. Do not proceed to
  implementation. It will be reviewed against the Architecture Review
  Gate before that happens.
