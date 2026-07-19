"""
Shared type aliases used across multiple engine modules. Per Decision
Log #003: enum-like fields should be defined once here and imported
everywhere they're used, rather than redefined per-module — this is
the structural fix for the str-vs-Literal bug pattern that mypy caught
independently in Module 3 (question_type) and Module 4 (relation).

Modules 1-4 are NOT retrofitted to import from here (see Decision
#003) — this module is used starting with Module 5.
"""

from typing import Literal

# Used by Logging (Module 5) and will be used by Reasoning Engine
# (Module 8) when it's built — defined once here so both stay in sync.
DecisionStrategy = Literal[
    "probe_deeper",
    "challenge_inconsistency",
    "verify",
    "switch_competency",
    "wrap_up_competency",
]
