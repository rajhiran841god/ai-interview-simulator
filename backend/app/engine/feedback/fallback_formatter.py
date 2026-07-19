"""
FallbackFormatter — isolated per reviewer's recommendation. Produces
the templated statement used when LLM generation fails for a specific
competency. One competency's failure never aborts the whole report.
"""


def fallback_summary_text(competency_id: str, insufficient_evidence: bool) -> str:
    readable = competency_id.replace("_", " ")
    if insufficient_evidence:
        return f"There wasn't enough discussion of {readable} to provide meaningful feedback."
    return (
        f"Feedback for {readable} could not be generated — evidence was recorded "
        f"but could not be synthesized into a summary."
    )
