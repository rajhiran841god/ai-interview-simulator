"""
Deterministic fallback templates, used only when LLM generation fails
or repeatedly produces too-similar questions. Generic enough to never
be wrong, specific enough to keep the interview moving.
"""


def fallback_question_text(competency_id: str, decision_strategy: str) -> str:
    templates = {
        "probe_deeper": f"Can you tell me more about your experience with {competency_id.replace('_', ' ')}?",
        "challenge_inconsistency": f"I want to make sure I understand correctly — can you clarify your role in {competency_id.replace('_', ' ')}?",
        "verify": f"Can you walk me through a specific example that demonstrates {competency_id.replace('_', ' ')}?",
        "wrap_up_competency": f"Is there anything else you'd like to add about {competency_id.replace('_', ' ')}?",
        "switch_competency": f"Let's move on — can you tell me about {competency_id.replace('_', ' ')}?",
    }
    return templates.get(
        decision_strategy,
        f"Can you tell me more about {competency_id.replace('_', ' ')}?",
    )
