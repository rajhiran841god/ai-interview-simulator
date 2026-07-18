# Architecture Review Gate (v0.1)

The Interview Intelligence Engine architecture is approved for
implementation only if all eight criteria pass. If any criterion fails,
the architecture is revised before any backend or frontend engine work
begins. This gate applies to Milestone 2 and to every future revision
or refactor of the engine.

| # | Criterion | Status |
|---|---|---|
| 1 | Engine Independence — engine is completely independent of the presentation layer; text/voice/avatar swappable without touching core logic | Pending |
| 2 | Modular Responsibilities — every module has one clear responsibility, defined inputs/outputs, minimal coupling | Pending |
| 3 | Provider Independence — LLM, storage, and future voice/avatar providers are abstracted; no business logic depends on one vendor | Pending |
| 4 | Evidence-Based Feedback (Critical) — every piece of feedback is traceable to the specific question, answer, and competency it came from; generic feedback is not acceptable | Pending |
| 5 | Adaptive Reasoning Transparency (Critical) — every follow-up question has an inspectable reason (competency tested, missing evidence detected, why probe vs. move on) | Pending |
| 6 | Pilot Learning Loop (Critical) — realism/usability feedback from students is explicitly captured and easily reviewable, not buried in logs | Pending |
| 7 | Extensibility — adding a new competency, role, or interview type reuses the same core reasoning framework without a rewrite | Pending |
| 8 | Product Consistency — architecture is consistent with Research Charter, Problem Statement, PRD, Scope, and Decision Log; conflicts are explained, not silently resolved | Pending |

**Final Rule:** No implementation begins until every criterion passes.

## Review Log

| Date | Architecture Version | Reviewed By | Outcome |
|---|---|---|---|
| | | | |
