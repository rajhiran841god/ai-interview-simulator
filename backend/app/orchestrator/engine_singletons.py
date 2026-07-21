"""
App-level singleton wiring for the Interview Intelligence Engine.

IMPORTANT: most engine services default to a FRESH, isolated in-memory
store per instantiation (verified by inspecting each __init__ — only
ConversationMemoryService defaults to a true shared module-level
store). If API route handlers each constructed
`EvidenceGraphService()` etc. fresh per-request, every request would
see empty, disconnected state — a real correctness bug, not a style
preference. This module exists specifically to prevent that: construct
each engine service exactly ONCE, correctly wired together, and reuse
these same instances across every request for the lifetime of the
process.

This is an in-memory, single-process wiring — matches every engine
module's own documented "Known Limitations" (not persistent, needs a
real backend before the pilot). Swapping to a persistent store later
means changing ONLY this file, per the storage-abstraction pattern
each module was built with from the start.
"""

from app.engine.conversation_memory.service import ConversationMemoryService
from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.logging.service import LoggingService
from app.engine.competency_model.service import CompetencyModelService
from app.engine.evaluation.service import EvaluationEngineService
from app.engine.reasoning.service import ReasoningEngineService
from app.engine.question_generator.service import QuestionGeneratorService
from app.engine.feedback.service import FeedbackGeneratorService

conversation_memory = ConversationMemoryService()
evidence_graph = EvidenceGraphService(conversation_memory=conversation_memory)
logging_service = LoggingService()
competency_model = CompetencyModelService()
evaluation_engine = EvaluationEngineService(
    evidence_graph=evidence_graph, logging_service=logging_service
)
reasoning_engine = ReasoningEngineService(
    competency_model=competency_model,
    evidence_graph=evidence_graph,
    logging_service=logging_service,
)
question_generator = QuestionGeneratorService(
    evidence_graph=evidence_graph, conversation_memory=conversation_memory
)
feedback_generator = FeedbackGeneratorService(
    competency_model=competency_model,
    evidence_graph=evidence_graph,
    conversation_memory=conversation_memory,
)
