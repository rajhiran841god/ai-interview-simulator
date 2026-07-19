"""
Centralized tunable reasoning parameters, per reviewer's guidance
before Module 7 was implemented: rather than scattering pilot-default
constants (CONTRADICTION_PENALTY, and later Module 8's stop/probe/
wrap-up thresholds) inline across modules, they live here so pilot
tuning after real data is a one-file change, not a hunt through
multiple services.

Every value here is an explicitly-flagged pilot default, not a
validated constant — same honesty standard as Milestone 2 Architecture
Section 4's question-count bounds (6/18) and 85%/60% thresholds.
"""

# Competency Model (Module 7)
CONTRADICTION_PENALTY = 0.3  # pilot default — see Competency_Model_Contract.md

# Reasoning Engine (Module 8) — pilot defaults, see Reasoning_Engine_Contract.md
# and Milestone_2_Architecture.md Section 4. None of these are
# validated against real interview data yet.
MIN_QUESTIONS = 6
MAX_QUESTIONS = 18
STOP_CONFIDENCE_THRESHOLD = 0.85
STOP_CONFIDENCE_FLOOR = 0.60
