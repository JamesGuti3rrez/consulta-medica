"""Rutas del sistema multiagente (/api/ai): sesiones, turnos, eventos y cierre."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from server.ai.agents.base import PROMPTS_DIR
from server.ai.agents.reformulador import QuestionReformulator
from server.ai.agents.registry import build_agents
from server.ai.llm.factory import build_gateway
from server.ai.llm.gateway import LLMUnavailable
from server.cases import CanonicalCaseRepository, CaseNotAvailable, CaseNotFound
from server.cases.catalog import CURATED_CASES_DIR
from server.config import settings
from server.engine.disclosure.context import ContextAssembler
from server.engine.disclosure.policy import DisclosurePolicy
from server.engine.evaluation import ClinicalEvaluationEngine
from server.engine.safety.protected_lexicon import ProtectedLexiconService
from server.engine.safety import ClinicalSafetyEngine
from server.engine.state_machine.service import ClinicalStateMachine
from server.guardrails import OutputGuard
from server.orchestration import (
    DecisionRouter,
    InMemorySessionStore,
    MultiAgentSessionService,
    SessionNotFound,
    SessionStoreError,
    StarGraphOrchestrator,
    SupabaseSessionStore,
)
from server.persistence import AttemptStoreError, SupabaseAttempts, build_attempt
from server.rag.embedded import EmbeddedRAGRetriever
from server.rag.retriever import CaseEvidenceRetriever, HttpRetriever
from server.tracing import LangSmithObserver, LocalTraceLogger

router = APIRouter(prefix="/api/ai", tags=["ai-sma"])


def build_session_store() -> InMemorySessionStore | SupabaseSessionStore:
    if settings.session_store == "supabase":
        return SupabaseSessionStore(settings.supabase_url, settings.supabase_secret_key)
    if settings.session_store != "memoria":
        raise ValueError(f"SESSION_STORE no reconocido: {settings.session_store!r} (use memoria o supabase).")
    return InMemorySessionStore()


STORE = build_session_store()
# Carpeta de casos que atiende el SMA; las pruebas la cambian por tests/fixtures/cases.
CASES_DIR = CURATED_CASES_DIR


def _store_unavailable(exc: SessionStoreError) -> HTTPException:
    print(f"[sesiones] {exc}")
    return HTTPException(status_code=503, detail="No se pudo acceder a las sesiones. Inténtalo de nuevo.")


LLM_UNAVAILABLE_DETAIL = "El simulador no puede responder en este momento. Inténtalo de nuevo en unos minutos."


class StartRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=64)


class MessageRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)


class HypothesisItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    discarded: bool = False
    reason: str = Field(default="", max_length=500)


class FinishRequest(BaseModel):
    """Lo que registró el estudiante. No se califica: se guarda junto al puntaje del motor clínico."""

    diagnosis: str | None = Field(default=None, max_length=2000)
    hypotheses: list[HypothesisItem] = Field(default_factory=list, max_length=50)


@lru_cache
def get_attempts() -> SupabaseAttempts | None:
    """Guardado de intentos; None si el servidor no tiene configurado Supabase."""
    if not (settings.supabase_url and settings.supabase_publishable_key and settings.supabase_secret_key):
        return None
    return SupabaseAttempts(settings.supabase_url, settings.supabase_publishable_key, settings.supabase_secret_key)


@lru_cache
def get_service() -> MultiAgentSessionService:
    repository = CanonicalCaseRepository(CASES_DIR)
    if settings.rag_service_url:
        retriever = HttpRetriever(settings.rag_service_url, token=settings.rag_http_token)
    elif settings.rag_embedded_enabled:
        embedded = EmbeddedRAGRetriever(settings.rag_index_dir, settings.rag_log_path)
        retriever = embedded if embedded.ready else CaseEvidenceRetriever(repository)
    else:
        retriever = CaseEvidenceRetriever(repository)
    gateway = build_gateway()
    disclosure = DisclosurePolicy()
    state_machine = ClinicalStateMachine()
    graph = StarGraphOrchestrator(
        router=DecisionRouter(),
        agents=build_agents(gateway),
        repository=repository,
        retriever=retriever,
        disclosure_policy=disclosure,
        context_assembler=ContextAssembler(),
        state_machine=state_machine,
        output_guard=OutputGuard(),
        protected_lexicon=ProtectedLexiconService(repository),
        reformulator=QuestionReformulator(gateway, PROMPTS_DIR),
        temperature=settings.llm_temperature,
    )
    return MultiAgentSessionService(
        graph=graph,
        repository=repository,
        disclosure_policy=disclosure,
        store=STORE,
        local_tracer=LocalTraceLogger(settings.trace_path),
        langsmith_observer=LangSmithObserver(
            enabled=settings.langsmith_tracing,
            api_key=settings.langsmith_api_key,
            project=settings.langsmith_project,
        ),
        state_machine=state_machine,
        safety_engine=ClinicalSafetyEngine(repository),
        evaluation_engine=ClinicalEvaluationEngine(repository),
    )


@router.get("/status")
def status():
    service = get_service()
    return {
        "topology": "star",
        "orchestration": "langgraph-stategraph",
        "decision_router": "deterministic",
        "disclosure_policy": "reveal-policy-minimum-privilege",
        "llm_mode": settings.llm_mode,
        "rag_connected": isinstance(service.graph.retriever, (HttpRetriever, EmbeddedRAGRetriever)),
        "retrieval_mode": (
            "http-rag" if isinstance(service.graph.retriever, HttpRetriever)
            else "embedded-lightrag" if isinstance(service.graph.retriever, EmbeddedRAGRetriever)
            else "deterministic-case-fallback"
        ),
        "session_store": settings.session_store,
        "langsmith_enabled": settings.langsmith_tracing and bool(settings.langsmith_api_key),
        "agents": ["medico_asistente", "paciente", "laboratorio", "radiologia", "especialista"],
        "gateway": service.graph.agents[next(iter(service.graph.agents))].gateway.status(),
    }


@router.post("/sessions")
def start(payload: StartRequest, authorization: str | None = Header(default=None)):
    try:
        return get_service().start(payload.case_id, owner_id=_student_id(authorization))
    except (CaseNotFound, CaseNotAvailable) as exc:
        raise HTTPException(status_code=404, detail="Caso no encontrado o no disponible.") from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    try:
        return get_service().get(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc


@router.post("/sessions/{session_id}/message")
def message(session_id: str, payload: MessageRequest):
    try:
        return get_service().message(session_id, payload.message)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc
    except LLMUnavailable as exc:
        # Claves rechazadas o servicio caído: se registra el motivo y el estudiante recibe un aviso claro.
        print(f"[llm] {exc}")
        raise HTTPException(status_code=503, detail=LLM_UNAVAILABLE_DETAIL) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/events")
def events(session_id: str):
    try:
        return get_service().events(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc


@router.post("/sessions/{session_id}/finish")
def finish(session_id: str, payload: FinishRequest | None = None, authorization: str | None = Header(default=None)):
    try:
        service = get_service()
        result = service.finish(session_id)
        result["attempt"] = _save_attempt(service, result, payload or FinishRequest(), authorization)
        return result
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc


def _save_attempt(service: MultiAgentSessionService, session: dict, payload: FinishRequest,
                  authorization: str | None) -> dict:
    """Guarda la consulta en el historial del alumno, solo si tiene la sesión iniciada.

    Un fallo de Supabase no impide ver la evaluación: se informa en attempt y la consulta termina igual.
    """
    if session.get("attempt_id"):
        return {"saved": True, "id": session["attempt_id"]}
    token = _bearer(authorization)
    if not token:
        return {"saved": False, "reason": "sin_sesion"}
    attempts = get_attempts()
    if attempts is None:
        return {"saved": False, "reason": "no_configurado"}
    owner_id = service.owner_of(session["session_id"])
    if not owner_id:
        return {"saved": False, "reason": "iniciada_sin_sesion"}
    try:
        user_id = attempts.user_id(token)
        if not user_id:
            return {"saved": False, "reason": "sesion_invalida"}
        # Solo quien empezó la consulta puede guardarla: conocer su id no basta para quedarse con ella.
        if user_id != owner_id:
            return {"saved": False, "reason": "otro_usuario"}
        specialty = service.repository.get_conversation_case(session["case_id"])["specialty"]
        attempt_id = attempts.save(build_attempt(
            user_id=user_id,
            session=session,
            specialty=specialty,
            diagnosis=payload.diagnosis,
            hypotheses=[item.model_dump() for item in payload.hypotheses],
        ))
    except AttemptStoreError as exc:
        print(f"[intentos] {exc}")
        return {"saved": False, "reason": "error"}
    service.attach_attempt(session["session_id"], attempt_id)
    return {"saved": True, "id": attempt_id}


def _bearer(authorization: str | None) -> str:
    return (authorization or "").removeprefix("Bearer ").strip()


def _student_id(authorization: str | None) -> str | None:
    """Id del alumno con sesión iniciada al empezar la consulta; None si es invitado o el token no vale.

    Iniciar la consulta nunca falla por esto: si Supabase no responde, la consulta sigue sin dueño.
    """
    token = _bearer(authorization)
    attempts = get_attempts() if token else None
    if attempts is None:
        return None
    try:
        return attempts.user_id(token)
    except AttemptStoreError as exc:
        print(f"[intentos] {exc}")
        return None
