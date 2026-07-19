"""
LLM semantic structuring — step 2 of the hybrid pipeline. Maps raw
extracted text into the contract's schema shape and identifies
probe-worthy claims.

This module is the ONLY place besides provider_adapter.py that touches
the LLM, and it does so exclusively through get_provider() — never the
SDK directly (Milestone 2 Architecture, Section 10).

IMPORTANT: this step's output is NOT trusted as final truth. Every
"stated" claim it produces gets checked against the raw source text by
validator.py afterward. If the model invents something not present in
the source, the validator strips it back to "absent". This is the
concrete mechanism that makes the no-fabrication rule enforceable
rather than aspirational.
"""

import json

from app.core.provider_adapter import get_provider

STRUCTURING_SYSTEM_PROMPT = """You extract structured information from resume text.

CRITICAL RULE: Only output information that is explicitly present in
the provided text. Never infer, estimate, or fill in plausible-sounding
values. If something isn't stated, leave it out or mark it absent.

For every value you extract, you MUST include the exact substring from
the source text that supports it, in a "source_text" field. If you
cannot quote exact supporting text, do not include that value at all.

Also include a "source_location" field for every value — a coarse
section label such as "Personal Summary", "Education", "Work
Experience", "Projects", "Skills", "Certifications", or "Achievements".
This does not need to be a precise character offset — just which
section of the resume the value came from. Never leave this blank;
use the most specific section label that applies.

Also identify "probe_worthy_claims": statements that assert an outcome,
achievement, or leadership role WITHOUT supporting detail (e.g. "led a
team of 5" with no explanation of what leading involved, or "increased
revenue by 30%" with no explanation of how). Flag these — do not
evaluate whether they're true.

Return ONLY valid JSON matching this exact shape, nothing else:
{
  "personal_summary": {"value": "...", "source_text": "...", "source_location": "Personal Summary"} or null,
  "education": [{"institution": "...", "degree": "...", "field": "...", "dates": "...", "source_text": "...", "source_location": "Education"}],
  "work_experience": [{"organization": "...", "role": "...", "dates": "...", "description_raw": "...", "source_text": "...", "source_location": "Work Experience"}],
  "projects": [{"name": "...", "description_raw": "...", "source_location": "Projects"}],
  "skills": ["..."],
  "certifications": ["..."],
  "achievements": ["..."],
  "probe_worthy_claims": [{"claim_text": "...", "source_section": "work_experience|projects|achievements|personal_summary", "reason_flagged": "..."}]
}
"""


def structure_resume_text(raw_text: str) -> dict:
    """Returns raw structured dict, NOT yet validated for provenance.
    Caller (service.py) must run this through validator.py before
    trusting any 'stated' value."""
    provider = get_provider()
    response_text = provider.complete(
        system=STRUCTURING_SYSTEM_PROMPT,
        user=f"Resume text:\n\n{raw_text}",
        max_tokens=4000,
    )

    # Model may wrap JSON in markdown fences despite instructions — strip defensively.
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Structuring failure is a parse_warning, not a crash — handled by service.py
        return {}
