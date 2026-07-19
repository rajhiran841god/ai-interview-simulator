# Implementation Report — Module 9: Question Generator / Cross-Questioning Engine

**First module whose primary responsibility is presentation, not
decision-making. Implemented as four isolated components
(GroundingBuilder, PromptBuilder, Generator, SimilarityHandler) per
explicit reviewer recommendation. Second consecutive module with a
real, honestly-caught recurring bug pattern.**

---

## 1. Files Created

```
backend/app/engine/question_generator/__init__.py
backend/app/engine/question_generator/schema.py
backend/app/engine/question_generator/grounding_builder.py
backend/app/engine/question_generator/prompt_builder.py
backend/app/engine/question_generator/generator.py
backend/app/engine/question_generator/similarity_handler.py
backend/app/engine/question_generator/fallback_templates.py
backend/app/engine/question_generator/service.py
backend/tests/engine/question_generator/__init__.py
backend/tests/engine/question_generator/test_question_generator.py
```

## 2. Files Modified

None outside this module.

## 3. Public API

```python
from app.engine.question_generator.service import QuestionGeneratorService

qg = QuestionGeneratorService(evidence_graph=eg, conversation_memory=cm)
generated = qg.generate_question(interview_id, reasoning_decision)
```

Internal structure exactly as recommended:
- `grounding_builder.py` — fetches real Evidence Graph excerpts only.
- `prompt_builder.py` — assembles the prompt from decision + grounding.
- `generator.py` — the ONLY component touching `ProviderAdapter`.
- `similarity_handler.py` — owns the bounded retry-then-fallback policy.
- `service.py` — orchestrates all four, records the turn in
  Conversation Memory.

## 4. External Libraries Introduced

None new — reuses `anthropic` via `ProviderAdapter`.

## 5. Design Decisions Made

- **`question_type` mapping is a private method on the service, not
  its own isolated component** — unlike the other four pieces, this
  logic is a handful of lines and doesn't benefit from further
  isolation; kept in `service.py` deliberately rather than
  over-fragmenting for its own sake.
- **`Generator.call_generation()` does not catch its own exceptions**
  — a hard provider failure propagates up to `SimilarityHandler`,
  which catches it there. This keeps `Generator` genuinely minimal (a
  pure wrapper) and puts failure-handling responsibility where the
  retry logic already lives, rather than duplicating try/except in two
  places.
- **Fallback templates are keyed by `decision_strategy`**, giving each
  strategy a fallback that preserves *some* of its intent (e.g.
  `challenge_inconsistency`'s fallback asks for clarification, not an
  accusatory question) — a first pass at the reviewer's suggested
  future acceptance criterion ("fallback preserves the original
  strategy's intent"), implemented now even though not formally
  required by the contract, since it cost little to do at the same
  time as writing the templates anyway.

## 6. Real Bugs Found

**I caught my own repeated bug before running tests this time.** While
writing `test_ac9_turn_recorded_with_matching_question_id`, I wrote
`trace_turn = cm.get_trace = None` — the exact same chained-assignment
mistake that caused a real bug in Module 4's test suite (silently
overwriting a method on a live service object). Recognized it from the
pattern and fixed it before the first test run, rather than needing
ruff to catch it after the fact. Worth noting as a case where the
project's own documented history of mistakes (visible in this same
report series) directly prevented a repeat.

**Two ruff findings**, auto-fixed, confirmed cosmetic.

**Three real mypy findings, all one root cause** — the same
`str`-vs-`Literal` pattern now caught for the fourth+ time across the
project (Modules 3, 4, and now 9, with a near-miss avoided in Module
8 only because of an explicit guard). This time it appeared in two
places: `_determine_question_type()`'s return type, and
`GenerationOutcome.generation_method`'s field type. Fixed by importing
`QuestionType` from `app.shared.types` and defining a proper
`GenerationMethod` Literal alias in `similarity_handler.py`. **This
pattern is now well-established enough that it should probably be
addressed structurally** (e.g. a project-wide lint rule or a mypy
strict-mode setting) rather than continuing to rely on catching it
module-by-module — flagging this as a concrete recommendation rather
than just repeating the observation again.

## 7. Contract Ambiguities Encountered

None requiring a stop-and-flag.

## 8. Acceptance Criteria Checklist

| # | Criterion | Status |
|---|---|---|
| 1 | probe_deeper, zero evidence → fresh | ✅ Pass |
| 2 | probe_deeper, existing evidence → cross_question | ✅ Pass |
| 3 | challenge_inconsistency/verify/wrap_up_competency → cross_question, all three tested | ✅ Pass |
| 4 | Stop decision raises without generation attempt | ✅ Pass |
| 5 | LLM failure falls back to template | ✅ Pass |
| 6 | Grounding context contains only real evidence, verified by inspecting actual prompt | ✅ Pass |
| 7 | Retries exactly once when too similar | ✅ Pass |
| 8 | Falls back after one retry if still similar, call count stays at 2 | ✅ Pass |
| 9 | Turn recorded with matching question_id | ✅ Pass |
| 10 | End-to-end integration with a REAL ReasoningDecision from Module 8 | ✅ Pass |
| 11 | Interview isolation | ✅ Pass |

**11/11, plus a provider-isolation check — 12 total, all passing.**

## 9. Test Summary

**14 new tests, all passing. Combined with Modules 1–8: 139 tests, 139
passing, actually executed.**

```
PYTHONPATH=. python -m pytest tests/engine/ -v
...
139 passed, 1 warning in 1.04s
```

## 10. Grounding Verification (AC6) — How It Was Actually Checked

`test_ac6_grounding_context_uses_only_real_evidence` captures the
actual prompt string sent to the (mocked) provider call and asserts
the real evidence excerpt appears in it, while a fabricated phrase
that was never added to Evidence Graph does NOT appear — directly
testing the grounding discipline at the level the reviewer specified
("prompts should contain only Evidence Graph excerpts... never
invented summaries"), not just trusting that the code path was
exercised.

## 11. End-to-End Integration (AC10)

`test_ac10_end_to_end_with_real_reasoning_decision` wires Conversation
Memory, Evidence Graph, Logging, Competency Model, Reasoning Engine,
and Question Generator together — six modules — calls Reasoning
Engine's real `decide_next_action()`, and feeds that real
`ReasoningDecision` into Question Generator. This is the widest
integration test in the project so far, and it passed on the first
real run.

## 12. Tooling

```
black app/engine/question_generator/ tests/engine/question_generator/
  → 7 files reformatted (first run)

ruff check ... --fix
  → 2 findings, auto-fixed, confirmed cosmetic

mypy app/engine/question_generator/*.py --ignore-missing-imports --follow-imports=silent
  → 3 real findings, all one root cause (Section 6)
  → Success: no issues found in 8 source files, after fix
```

## 13. Known Limitations

- **No live LLM call has been made** — same structural gap as Resume/
  JD Understanding and Evaluation Engine. Question quality, and
  whether the grounding discipline actually prevents misattribution in
  practice (not just in the mocked-prompt test), remains unverified
  against a real model.
- **`switch_competency`'s question-type mapping is untested in
  practice** since Reasoning Engine never selects that strategy yet —
  the mapping exists in code for completeness but has no real caller.
- The recurring `str`-vs-`Literal` pattern (Section 6) suggests a
  structural fix is overdue — noted as a concrete recommendation for
  before Module 10 or shortly after.

## 14. Future Improvements (Not Implemented)

- Semantic (not just literal) repetition detection — explicitly
  deferred per reviewer's guidance, belongs in Conversation Memory's
  future capabilities, not this module
- A project-wide structural fix for the str-vs-Literal pattern

---

## Definition of Done — Self-Check

| Requirement | Met? |
|---|---|
| All Acceptance Criteria pass | ✅ 11/11 |
| No contract violations | ✅ |
| No TODO/FIXME comments | ✅ |
| Public interfaces documented | ✅ |
| Unit tests pass | ✅ (139/139 combined, actually run) |
| Type checking passes | ✅ (after fixing 3 real findings, one root cause) |
| Linting passes | ✅ (after 2 cosmetic auto-fixes) |
| Formatting passes | ✅ |
| Only documented public API exposed | ✅ |
| No functionality outside Question Generator added | ✅ |

**Honest verdict: engineering-complete, live-API validation pending —
fourth module sharing that gap (joining Resume/JD Understanding,
Evaluation Engine).** Everything this environment can verify is
verified; question quality and grounding-discipline robustness against
a real model remain open until the Anthropic billing issue clears.
