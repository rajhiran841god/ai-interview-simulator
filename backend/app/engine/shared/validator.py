"""
Shared provenance validation logic — used by Resume Understanding AND
JD Understanding (and any future module needing the same
no-fabrication guarantee).

Per JD Understanding Contract v2's implementation prompt requirement:
creating a second validator implementation is a contract violation
unless a documented technical reason makes reuse impossible. This
module exists so reuse is structural (an import), not just a
convention someone has to remember.

Matching rule (unchanged from Resume Understanding Contract v3):
- Normalize both strings: collapse whitespace, strip leading/trailing
  punctuation, lowercase.
- After normalization, source_text must appear as an exact substring
  of the original text.
- No fuzzy/similarity matching. Fail closed.
"""

import re
from dataclasses import dataclass, field


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" \t\n.,;:!?\"'()[]{}")
    return text.strip()


def is_traceable(source_text: str, original_text: str) -> bool:
    """Returns True only if source_text can be verified as an exact
    substring of original_text after normalization."""
    if not source_text or not original_text:
        return False
    return normalize(source_text) in normalize(original_text)


@dataclass
class ValidationResult:
    """Structured outcome of validating one extracted value —
    observable and debuggable, not a silent mutation."""

    accepted: bool
    value: dict
    warnings: list[str] = field(default_factory=list)


def validate_value(
    value: dict,
    original_text: str,
    fallback_location: str,
    required_field: str = "source_text",
) -> ValidationResult:
    """
    Verify a single extracted value's claimed source_text is
    traceable to original_text. fallback_location is a coarse section
    label (e.g. "Education", "Requirements section") used only if the
    structurer didn't supply a source_location itself — never a
    placeholder like "unspecified".
    """
    source_text = value.get(required_field)

    if not source_text:
        return ValidationResult(
            accepted=False,
            value={k: None for k in value.keys()} | {"confidence": "absent"},
            warnings=[
                f"No source_text provided for a {fallback_location} entry; rejected."
            ],
        )

    if not is_traceable(source_text, original_text):
        return ValidationResult(
            accepted=False,
            value={k: None for k in value.keys()} | {"confidence": "absent"},
            warnings=[
                f"Provenance check failed for a {fallback_location} entry — "
                f"claimed source_text could not be found in the original document. Rejected."
            ],
        )

    result_value = dict(value)
    result_value["confidence"] = "stated"
    result_value.setdefault("source_location", fallback_location)
    if not result_value.get("source_location"):
        result_value["source_location"] = fallback_location

    return ValidationResult(accepted=True, value=result_value, warnings=[])


def normalize_competency_id(competency_name: str) -> str:
    """
    Normalizes a competency name into a stable ID, per JD
    Understanding Contract v2's implementation note. Handles the
    variants the reviewer flagged: hyphens, double spaces, mixed case
    all collapse to the same ID.

    "Consumer Insight" / "Consumer-Insight" / "consumer insight" /
    "Consumer  Insight" all normalize to "consumer_insight".
    """
    text = competency_name.lower()
    text = re.sub(r"[-\s]+", "_", text.strip())
    text = re.sub(r"[^\w_]", "", text)
    return text
