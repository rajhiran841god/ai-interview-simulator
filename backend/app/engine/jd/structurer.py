"""
LLM semantic structuring for JD text. Routes exclusively through
get_provider() — never the LLM SDK directly (enforceable rule, same as
Resume Understanding).

Output is NOT trusted as final truth — every claim gets checked against
the raw JD text by the shared validator afterward (same no-fabrication
enforcement pattern as Resume Understanding).
"""

import json

from app.core.provider_adapter import get_provider

STRUCTURING_SYSTEM_PROMPT = """You extract structured role requirements from job description text.

CRITICAL RULE: Only output information explicitly present in the
provided text. Never infer, estimate, or fill in plausible-sounding
requirements. If something isn't stated, leave it out.

For every value you extract, include the exact substring from the
source text that supports it, in a "source_text" field, and a coarse
section label in "source_location" (e.g. "Requirements section",
"Role Summary", "Qualifications"). Never leave source_location blank.

REQUIRED COMPETENCIES: extract skills, abilities, or capabilities the
JD asks for. Do NOT use a fixed vocabulary — use whatever language the
JD itself uses or clearly implies (e.g. "Consumer Insight", "Structured
Problem Solving", "Client Communication" — whatever fits this specific
JD). Classify each as:
- "primary": explicitly required, or emphasized more than once in the JD
- "secondary": mentioned as desirable/supportive, not central

ROLE-SPECIFIC SIGNALS: contextual expectations that affect how
competencies should be interpreted, but are NOT themselves
competencies or qualifications. Do NOT include things like "MBA
preferred", "Remote work", "Based in Mumbai", or salary/logistics —
those are not signals. A genuine signal example: "fast-paced startup
environment" → interpretation: "candidate should demonstrate comfort
with ambiguity and rapid iteration." The interpretation must be
directly supported by the signal_text — do not introduce any new
requirement or claim not present in the source.

Return ONLY valid JSON matching this exact shape, nothing else:
{
  "role_title": {"value": "...", "source_text": "...", "source_location": "..."} or null,
  "seniority_level": {"value": "entry|associate|mid|senior|leadership", "source_text": "...", "source_location": "..."} or null,
  "required_competencies": [
    {"competency_name": "...", "emphasis": "primary|secondary", "source_text": "...", "source_location": "..."}
  ],
  "role_specific_signals": [
    {"signal_text": "...", "interpretation": "...", "source_text": "...", "source_location": "..."}
  ]
}
"""


def structure_jd_text(jd_text: str) -> dict:
    """Returns raw structured dict, NOT yet validated for provenance.
    Caller must run this through the shared validator before trusting
    any 'stated' value."""
    provider = get_provider()
    response_text = provider.complete(
        system=STRUCTURING_SYSTEM_PROMPT,
        user=f"Job description text:\n\n{jd_text}",
        max_tokens=3000,
    )

    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}
