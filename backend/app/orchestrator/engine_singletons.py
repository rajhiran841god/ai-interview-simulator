"""
App-level singleton wiring for the Interview Intelligence Engine.

NOW PERSISTENT (Postgres via Supabase) — this is exactly the swap
predicted when this file was first written: "Swapping to a persistent
store later means changing ONLY this file." A real cross-process bug
during live voice testing (the FastAPI backend and the LiveKit voice
worker are separate processes; the old in-memory dicts were invisible
between them, causing "No competencies initialized" even right after
initialization) made this swap necessary now rather than later.

Per Decision Log #006: this changes ONLY the storage layer each
service is constructed with. Every service class itself
(ConversationMemoryService, EvidenceGraphService, etc.) is completely
unchanged — same reasoning, same schemas, same contracts.
"""

from app.engine.conversation_memory.service import ConversationMemoryService
from app.engine.conversation_memory.store import (
    PostgresConversationMemoryStore,
    InMemoryConversationMemoryStore,
)
from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.evidence_graph.store import (
    PostgresEvidenceGraphStore,
    InMemoryEvidenceGraphStore,
)
from app.engine.logging.service import LoggingService
from app.engine.logging.store import PostgresTraceStore, InMemoryTraceStore
from app.engine.competency_model.service import CompetencyModelService
from app.engine.competency_model.store import (
    PostgresCompetencyModelStore,
    InMemoryCompetencyModelStore,
)
from app.engine.evaluation.service import EvaluationEngineService
from app.engine.reasoning.service import ReasoningEngineService
from app.engine.question_generator.service import QuestionGeneratorService
from app.engine.feedback.service import FeedbackGeneratorService
from app.core.config import settings

_use_postgres = settings.STORE_BACKEND == "postgres"

conversation_memory = ConversationMemoryService(
    store=(
        PostgresConversationMemoryStore()
        if _use_postgres
        else InMemoryConversationMemoryStore()
    )
)
evidence_graph = EvidenceGraphService(
    store=(
        PostgresEvidenceGraphStore() if _use_postgres else InMemoryEvidenceGraphStore()
    ),
    conversation_memory=conversation_memory,
)
logging_service = LoggingService(
    store=PostgresTraceStore() if _use_postgres else InMemoryTraceStore()
)
competency_model = CompetencyModelService(
    store=(
        PostgresCompetencyModelStore()
        if _use_postgres
        else InMemoryCompetencyModelStore()
    )
)
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
