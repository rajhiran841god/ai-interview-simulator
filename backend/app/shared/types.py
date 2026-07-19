"""
Shared type aliases, per Decision Log #003. Modules 5 onward import
enum-like types from here rather than redefining Literal[...] locally.

Modules 1–4 (Resume Understanding, JD Understanding, Conversation
Memory, Evidence Graph) are NOT retrofitted to import from this module
— they keep their own local definitions, per Decision #003's explicit
deferral. QuestionType and Relation are defined here too, matching
those modules' existing definitions exactly, so that:
(a) Module 5 (which references turns and evidence conceptually) has a
    single correct source if it ever needs these types, and
(b) a future retrofit of Modules 1-4 has an obvious, already-correct
    target to migrate to, rather than needing to invent the shared
    version at that time.
"""

from typing import Literal

QuestionType = Literal["fresh", "cross_question"]
Relation = Literal["supports", "contradicts"]

DecisionStrategy = Literal[
    "probe_deeper",
    "challenge_inconsistency",
    "verify",
    "switch_competency",
    "wrap_up_competency",
]

AnswerClassification = Literal["substantive", "partial", "deflection", "non_answer"]

Emphasis = Literal["primary", "secondary"]
