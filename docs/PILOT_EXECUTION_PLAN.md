# Pilot Execution Plan

**This document governs the next phase. Per the project's own
discipline: once this pilot begins, changes to the product should come
from evidence collected here — not from new brainstorming.** If you
find yourself wanting to add a feature mid-pilot, write it in
`docs/FUTURE_ROADMAP.md` instead and keep running the pilot as planned.

**Status:** Not yet started — blocked on Anthropic billing access
(live LLM integration is a prerequisite for everything below).

---

## Objectives

Answer exactly these questions, and no others, with real evidence:

1. Does the engine's questioning genuinely feel adaptive and relevant,
   or generic? (The original Stage 1 validation question from Decision
   #002 — still not answered with real data.)
2. Does voice interaction make the experience feel more real, or does
   latency/turn-detection friction make it feel worse than text would
   have? (Decision #004's stated falsification condition.)
3. Is the feedback report perceived as useful, specific, and
   trustworthy — or generic and unconvincing?
4. What is real, measured end-to-end latency, and is it acceptable to
   real users (not just "technically working")?
5. What breaks, confuses, or frustrates real students that no test
   suite could have caught?

## Participant Profile

- MBA students, ideally a mix of: some who've already been through
  real placement interviews (can compare directly) and some still
  preparing (primary target user)
- Target: 10-20 participants, per the original Research Charter's
  sample-size reasoning (enough to see a pattern repeat or break,
  without diminishing returns)
- Recruit outside your immediate friend group where possible — same
  bias caution flagged in the original Discovery Interview Guide

## Pre-Pilot Checklist (must be true before Participant #1)

- [ ] Anthropic billing resolved, live API key working
- [ ] Live-API validation run across all 5 LLM-backed modules (Resume/JD
      Understanding, Evaluation Engine, Question Generator, Feedback
      Generator) — the gap that's been open since Module 1
- [ ] Voice pipeline connected end-to-end at least once (Test 1 from
      `VOICE_VALIDATION.md`)
- [ ] Latency measured at least once (Test 2 from `VOICE_VALIDATION.md`)
      — if this reveals voice feels unacceptably slow, decide *before*
      the pilot whether to run it in voice or fall back to text, per
      Decision #004's falsification condition. Don't discover this
      mid-pilot.
- [ ] Pilot notice / consent copy shown at signup (already built —
      confirm it's still accurate)
- [ ] You personally run one full interview yourself, start to finish,
      before any real participant does

## Test Script (what you tell each participant)

1. Brief framing: "This is a pilot AI mock interview tool. Please
   answer naturally, as you would in a real interview. There's no
   passing or failing — we're testing the tool, not you."
2. Upload resume, paste a real JD (ideally one relevant to their
   actual target roles)
3. Complete the interview
4. Immediately after, ask the structured questions below — before they
   have time to forget specifics

## Feedback Questions (ask immediately after, per Decision #002's Stage 1 design)

- Did this feel like a real interview? Why or why not?
- Which question felt most realistic? Which felt most artificial?
- Was any part of the feedback report especially useful — or
  especially generic/unconvincing?
- What frustrated you, if anything?
- Would you practice with this again before a real interview?
- (If voice was used) Did the voice interaction help or hurt the
  experience compared to what you'd expect from typing?

## Success Metrics

- Majority of participants say it felt closer to a real interview than
  their existing prep methods (mirror, friends, YouTube, ChatGPT — per
  the original Problem Statement)
- Feedback reports are described as specific/evidence-grounded, not
  generic, by most participants
- No repeated, severe technical failures (crashes, silent hangs,
  confusing state) across the group

## Failure Metrics — What Would Mean Rethinking, Not Just Tuning

- Multiple participants say it felt like "talking to a chatbot," not
  an interview — this would be evidence the engine-quality question
  from Decision #002 is not yet resolved, regardless of interface
- Voice interaction is described as making things worse, not better —
  direct evidence for Decision #004's falsification condition firing
- Feedback reports are seen as generic despite the evidence-grounding
  architecture — would mean the prompt/grounding needs real rework,
  not just tuning

## What to Record, Per Interview

| Field | Notes |
|---|---|
| Participant ID (anonymized) | |
| Real vs. simulated interview experience (do they have one to compare against?) | |
| Full transcript / recording (with consent) | |
| Measured latency (avg, max per turn) | |
| Bugs/glitches observed | Raw, unfiltered — even minor ones |
| Answers to the feedback questions above | Verbatim where possible — quotes are valuable |

## Deliberate Test Matrix (don't rely on organic interviews alone)

Real pilot interviews will mostly produce "average, cooperative"
answers by default — the harder-to-observe behaviors (insufficient
evidence, contradiction handling, vague-answer follow-up) may never
appear organically in a small sample. Script these scenarios
deliberately, either as dedicated pre-pilot live tests (cheaper, faster
feedback loop) or as directed prompts to a few pilot participants
("for this one, try giving a deliberately vague answer"):

| Candidate type | Goal | Status |
|---|---|---|
| Strong | Confirm high-confidence reporting, coherent multi-turn synthesis | ✅ Validated live — `LIVE_VALIDATION_LOG.md` Entry 6 |
| Average | Check calibration and stopping behavior at moderate confidence | ⏳ Not yet tested live |
| Weak | Validate `insufficient_evidence` handling — honest, not fabricated | ⏳ Not yet tested live |
| Contradictory | Exercise `has_unresolved_contradiction` / `challenge_inconsistency` | ⏳ Not yet tested live |
| Vague | Ensure the engine asks follow-up questions rather than overconfidently concluding | ⏳ Not yet tested live |

**Do not tune any threshold based on the "Strong" row alone** — that's
exactly the mistake avoided by adding this matrix. Every row needs at
least one real, live data point before `reasoning_config.py`'s
defaults get touched.


- [ ] Does Decision #002's core hypothesis (readiness gap is real,
      engine quality matters) hold up?
- [ ] Does Decision #004's voice bet pay off, or does the falsification
      condition trigger?
- [ ] Which pilot-default parameters (contradiction penalty,
      confidence thresholds, question-count bounds — all in
      `app/shared/reasoning_config.py`) need real tuning based on
      observed behavior?
- [ ] Is the product ready for a faculty demo, or does it need another
      pilot round first?

---

**Reminder to future-you:** if this document starts accumulating new
feature ideas instead of pilot results, that's the signal scope is
drifting again. Log new ideas in `FUTURE_ROADMAP.md` and keep this
document about evidence only.
