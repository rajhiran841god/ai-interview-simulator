You are implementing Module 1 of 10 for the Interview Intelligence Engine.

SOURCE OF TRUTH: docs/contracts/Resume_Understanding_Contract_3.md
Also read: docs/Milestone_2_Architecture.md (Sections 2.1, 10, 11)

RULE: If the implementation conflicts with the contract, the
implementation is wrong — not the contract. Do not silently change or
reinterpret the contract while coding. If the contract appears
insufficient or ambiguous for something you encounter, STOP and
document the issue clearly instead of inventing behavior to fill the
gap. Report it back rather than guessing.

==================================================
TASK
==================================================

1. Create branch: feature/resume-understanding
2. Implement the Resume Understanding module inside
   backend/app/engine/resume/ (per the target structure in Milestone 2
   Architecture Section 2, "Target folder structure")
3. Follow the hybrid pipeline exactly: deterministic PDF/DOCX
   extraction → LLM semantic structuring (routed through a
   ProviderAdapter — do not import the Anthropic SDK directly anywhere
   outside that adapter) → provenance validation layer
4. Output must match the schema in the contract exactly — including
   parser_version, processing_metadata, and the two-state
   (stated/absent) confidence model with no "inferred" state
5. Implement the provenance matching rule exactly as specified in the
   contract (normalized exact substring match, no fuzzy matching)
6. Write unit tests mapped directly to each of the 8 Acceptance
   Criteria in the contract — name tests so the mapping is obvious
   (e.g. test_ac7_provenance_traceability)
7. Run formatting, linting, and the full test suite

==================================================
DO NOT
==================================================

- Modify the architecture document
- Modify the contract document
- Change existing APIs from Milestone 1 (auth, etc.)
- Introduce new dependencies unless strictly required for this module
- Implement any part of JD Understanding or any other module
- Optimize for hypothetical future requirements not in the contract
- Leave any functionality outside Resume Understanding's scope

==================================================
DEFINITION OF DONE
==================================================

The module is considered complete only if ALL of the following are true:

- All 8 Acceptance Criteria pass
- No contract violations exist
- No TODO/FIXME comments remain
- Public interfaces are documented
- Unit tests pass
- Type checking passes
- Linting passes
- Formatting passes
- The module exposes only the documented public API
- No functionality outside Resume Understanding has been added

If any of these are not true, the module is not done — do not report
it as complete.

==================================================
IMPLEMENTATION REPORT (required output when finished)
==================================================

Produce a structured report:

1. Files created
2. Files modified
3. Public API (function/class signatures exposed to other modules)
4. External libraries introduced (and why each was necessary)
5. Design decisions made where the contract left room for judgment
6. Contract ambiguities encountered (if any) — do not resolve these
   silently, just document them
7. Acceptance Criteria checklist (all 8, pass/fail)
8. Test summary (count, pass/fail, coverage if available)
9. Known limitations
10. Future improvements identified but NOT implemented (these belong
    in docs/FUTURE_ROADMAP.md, not in this module)

Stop after this module is complete, tested, and the report is
produced. Do not proceed to Module 2. Prepare a commit (or PR if you
have GitHub access configured) but do not merge to main.
