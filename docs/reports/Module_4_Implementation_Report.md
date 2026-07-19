# Implementation Report — Module 4: Evidence Graph

**Second module with no external provider dependency and a full,
unqualified DoD. First module with a real cross-module integration
test against another completed module (Conversation Memory).**

---

## 1. Files Created

```
backend/app/engine/evidence_graph/__init__.py
backend/app/engine/evidence_graph/schema.py
backend/app/engine/evidence_graph/store.py
backend/app/engine/evidence_graph/service.py
backend/tests/engine/evidence_graph/__init__.py
backend/tests/engine/evidence_graph/test_evidence_graph.py
```

## 2. Files Modified

None outside this module.

## 3. Public API

```python
from app.engine.evidence_graph.service import EvidenceGraphService

eg = EvidenceGraphService(conversation_memory=cm)  # explicit dependency injection
eg.add_evidence(interview_id, competency_id, turn_id, evidence_excerpt, relation, contradicts_evidence_id=None)
eg.get_evidence_for_competency(interview_id, competency_id)
eg.get_evidence_for_turn(interview_id, turn_id)
eg.has_contradictions(interview_id, competency_id)
```

Constructed with an explicit `ConversationMemoryService` reference
(defaulting to a fresh one if not supplied) — this is the module's one
real, documented cross-module dependency, and it's read-only.

## 4. External Libraries Introduced

None.

## 5. Design Decisions Made — All Four Reviewer Suggestions Applied

1. **Immutability enforced at the model level**, not just documented
   — `EvidenceEntry` uses Pydantic's `model_config = ConfigDict(frozen=True)`,
   so attempting to mutate a field after creation raises a
   `ValidationError`, not just a convention someone could violate.
   Tested directly (`test_evidence_entries_are_immutable`).
2. **`excerpt_start`/`excerpt_end` offset fields added**, optional,
   unused by the provenance check itself (substring matching remains
   the actual enforcement mechanism), populated only when a future
   caller can supply them.
3. **`evidence_id` generation is exclusively internal** — `add_evidence()`'s
   signature has no `evidence_id` parameter at all, making caller
   injection structurally impossible, not just discouraged. Tested via
   signature introspection.
4. **Duplicate-evidence policy decided consciously, not left
   accidental**: duplicates are allowed, not deduplicated or rejected.
   Rationale documented directly in `store.py` — a candidate
   re-affirming a point in a later answer is potentially meaningful
   information, not noise to collapse. Tested explicitly
   (`test_duplicate_evidence_is_allowed_not_deduplicated`).

## 6. Real Bugs Found

**Two ruff findings, both in my own test code, one of which was
genuinely dangerous:**

1. An unused `entry` variable — cosmetic, fixed.
2. **`retrieved_turn = cm.get_turn = None`** — this line doesn't do
   what it looks like it does. Python's chained assignment set
   `cm.get_turn` (a method on the `ConversationMemoryService`
   instance) to `None`, silently clobbering it. Since this was in a
   throwaway test-local variable assignment, it happened to be
   harmless in this specific test (nothing called `cm.get_turn`
   afterward) — but it's exactly the kind of typo that could corrupt
   shared state if it had touched a fixture reused across tests, or if
   `get_turn` had actually existed as a real method on the service
   (it doesn't currently — `get_history` is the real lookup path) and
   something downstream depended on it. Removed entirely rather than
   "fixed," since the line served no purpose.

**One real mypy finding, same pattern as Module 3:** `relation`
parameter in `add_evidence()` was typed as plain `str` instead of the
schema's `Relation = Literal["supports", "contradicts"]`. Fixed by
importing and using the precise type. This is now the second time this
exact category of bug (loose `str` typing on a field that should be a
`Literal`) has been caught by mypy rather than by a human — worth
noting as a pattern to watch for proactively in Module 5 onward, not
just something tooling happens to catch after the fact.

## 7. Contract Ambiguities Encountered

None requiring a stop-and-flag — the contract's explicit "conscious
decision" prompts (immutability, duplicate policy, ID ownership) were
already anticipated by the review, so implementation matched contract
intent directly.

## 8. Acceptance Criteria Checklist

| # | Criterion | Status |
|---|---|---|
| 1 | Add + retrieve evidence successfully | ✅ Pass |
| 2 | Fabricated excerpt rejected (shared validator reused) | ✅ Pass |
| 3 | Nonexistent turn rejected | ✅ Pass |
| 4 | Contradicts without target rejected | ✅ Pass |
| 5 | Contradicts with nonexistent target rejected | ✅ Pass |
| 6 | has_contradictions — both directions | ✅ Pass |
| 7 | Ordering derived from Conversation Memory sequence | ✅ Pass |
| 8 | No full conversation text duplicated (structural check) | ✅ Pass |
| 9 | Interview isolation | ✅ Pass |

**9/9, plus 4 supplementary tests for the reviewer's specific
suggestions (immutability, duplicate policy, ID ownership) and 1 full
cross-module integration test — 14 total, all passing.**

## 9. Test Summary

**13 new tests (one folded into the immutability/duplicate/ownership
set above), all passing. Combined with Modules 1–3: 65 tests, 65
passing, actually executed.**

```
PYTHONPATH=. python -m pytest tests/engine/ -v
...
65 passed, 1 warning in 1.32s
```

The one remaining warning is the pre-existing Milestone 1
`config.py` deprecation notice — confirmed out of scope for this
module, not newly introduced.

## 10. Cross-Module Integration Test (per explicit reviewer request)

`test_full_cross_module_integration_with_conversation_memory` performs
the exact 6-step sequence requested: record a turn → answer it →
retrieve via Conversation Memory → add evidence using a real excerpt
→ confirm the shared validator accepts it → query by both competency
and turn → confirm ordering follows Conversation Memory's sequence.
This is the first test in the project that exercises two "finished"
modules together rather than each in isolation with mocked
dependencies — and it passed on the first real run, which is a decent
signal that both modules' contracts are actually compatible in
practice, not just on paper.

## 11. Tooling

```
black app/engine/evidence_graph/ tests/engine/evidence_graph/
  → 4 files reformatted (first run)

ruff check ... --fix
  → 2 real findings (one cosmetic, one a genuine landmine — Section 6)

mypy app/engine/evidence_graph/*.py --ignore-missing-imports --follow-imports=silent
  → 1 real type error found and fixed (same category as Module 3)
  → Success: no issues found in 4 source files, after fixes
```

## 12. Known Limitations

- **`InMemoryEvidenceGraphStore` is not persistent**, same caveat as
  Conversation Memory — expected for now, needs a real backend before
  the pilot.
- **`competency_id` is not validated against the interview's actual
  JD-derived competency set** — per the contract's explicit
  Non-Responsibility, this is left as a cross-module integrity concern
  for a future module or caller, not enforced here.
- Character-offset fields (`excerpt_start`/`excerpt_end`) exist in the
  schema but nothing currently populates them — present for future use
  per the reviewer's suggestion, not yet exercised.

## 13. Future Improvements (Not Implemented)

- Persistent `EvidenceGraphStore` backend
- Cross-module validation that `competency_id` values are legitimate
  for a given interview (likely belongs to Competency Model, Module 7)
- Populating offset fields once a caller can supply them

---

## Definition of Done — Self-Check

| Requirement | Met? |
|---|---|
| All Acceptance Criteria pass | ✅ 9/9, plus all reviewer-suggested items |
| No contract violations | ✅ |
| No TODO/FIXME comments | ✅ |
| Public interfaces documented | ✅ |
| Unit tests pass | ✅ (65/65 combined, actually run) |
| Type checking passes | ✅ (after fixing a real error) |
| Linting passes | ✅ (after fixing 2 real findings, one genuinely risky) |
| Formatting passes | ✅ |
| Only documented public API exposed | ✅ |
| No functionality outside Evidence Graph added | ✅ |

**Honest verdict: full, unqualified 🟢, same category as Module 3 —
no provider dependency, nothing waiting on the Anthropic billing
issue.** The cross-module integration test passing on the first real
run is a genuinely good sign for the project's overall contract
discipline, not just this module in isolation.
