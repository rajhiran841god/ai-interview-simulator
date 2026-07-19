# Module Dependency Matrix

Tracks what each implemented module consumes and produces, so future
schema changes and reviews can quickly assess downstream impact.
Update this alongside each new Implementation Report — it's a living
document, not a one-time artifact.

| Module | Contract Version | Consumes | Produces | Provider Dependency | DoD Status |
|---|---|---|---|---|---|
| Resume Understanding | v3 | — | `ResumeUnderstandingOutput` | Yes — Anthropic (structuring step) | Engineering-complete; live-API validation pending |
| JD Understanding | v2 | — | `JDUnderstandingOutput` | Yes — Anthropic (structuring step) | Engineering-complete; live-API validation pending (batched with Resume Understanding) |
| Conversation Memory | v2 | — | `TurnRecord` | None | Full DoD — 🟢 |
| Evidence Graph | v1 | Conversation Memory (`get_history`, read-only) | `EvidenceEntry` | None | Full DoD — 🟢 |
| Logging / Trace Recorder | v1 | None directly (references `question_id`/`competency_id`/evidence IDs by value, no live calls to other modules) | `TraceRecord` | None | Full DoD — 🟢 |
| Evaluation Engine | v1 | Evidence Graph (writes), Logging (reads + writes via `update_trace_outcome`) | `EvaluationResult` | Yes — Anthropic (classification step) | Engineering-complete; live-API validation pending (batched with Resume/JD Understanding) |
| Competency Model | v1 | Evaluation Engine's `EvaluationResult` fields (consumed by value, no live calls to Module 6) | `CompetencyState` | None | Full DoD — 🟢 |
| Reasoning Engine | v1 | Competency Model (reads only), Evidence Graph (reads only), Logging (writes) | `ReasoningDecision` | None | Full DoD — 🟢 |
| Question Generator | v1 | Reasoning Engine's `ReasoningDecision` (by value), Evidence Graph (reads), Conversation Memory (reads + writes turns) | `GeneratedQuestion` | Yes — Anthropic (question generation) | Engineering-complete; live-API validation pending (batched with Resume/JD Understanding, Evaluation Engine) |
| Feedback Generator | v1 | Competency Model (reads, emphasis only — never confidence), Evidence Graph (reads), Conversation Memory (reads) | `InterviewFeedbackReport` | Yes — Anthropic (feedback synthesis) | Engineering-complete; live-API validation pending (batched with Resume/JD Understanding, Evaluation Engine, Question Generator) |

## Notes

- "Provider Dependency" means the module calls `ProviderAdapter`
  (directly or transitively) and therefore has an outstanding live-LLM
  validation gap until that's run with a real API key.
- Schema versions in the "Produces" column should be updated if a
  contract is ever revised post-freeze (see the schema-freeze
  discipline noted after Module 2's review — changes should default to
  "can downstream adapt?" before "should upstream change?").
- Cross-module reads (like Evidence Graph → Conversation Memory)
  should be listed explicitly here so a future schema change to
  Conversation Memory's `TurnRecord` immediately surfaces which other
  modules need re-checking.
