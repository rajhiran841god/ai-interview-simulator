"""
Backward-compatible re-export. The actual provenance validation logic
now lives in app.engine.shared.validator (extracted per JD
Understanding Contract v2's reuse requirement, to prevent Resume
Understanding and JD Understanding from diverging into two separate
implementations of the same no-fabrication rule).

Kept as a thin re-export so existing imports
(`from app.engine.resume.validator import ...`) keep working without
every call site needing to change.
"""

from app.engine.shared.validator import (
    normalize,
    is_traceable,
    ValidationResult,
    validate_value,
)

__all__ = ["normalize", "is_traceable", "ValidationResult", "validate_value"]
