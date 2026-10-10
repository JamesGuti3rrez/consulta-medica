"""Rutas del sistema multiagente (/api/ai): sesiones, turnos, eventos y cierre."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.ai.agents.registry import build_agents
from server.ai.llm.factory import build_gateway
from server.cases import CanonicalCaseRepository, CaseNotAvailable, CaseNotFound
from server.cases.catalog import CURATED_CASES_DIR
from server.config import settings
from server.engine.disclosure.context import ContextAssembler
from server.engine.disclosure.policy import DisclosurePolicy
from server.engine.safety.protected_lexicon import ProtectedLexiconService
from server.engine.state_machine.service import ClinicalStateMachine
from server.guardrails import OutputGuard
from server.orchestration import (
    DecisionRouter,
    InMemorySessionStore,
    MultiAgentSessionService,
    SessionNotFound,
    StarGraphOrchestrator,
)
from server.rag.embedded import EmbeddedRAGRetriever
from server.rag.retriever import CaseEvidenceRetriever, HttpRetriever
from server.tracing import LangSmithObserver, LocalTraceLogger

router = APIRouter(prefix="/api/ai", tags=["ai-sma"])
STORE = InMemorySessionStore()
# Carpeta de casos que atiende el SMA; las pruebas la cambian por tests/fixtures/cases.
CASES_DIR = CURATED_CASES_DIR


class StartRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=64)


class MessageRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)


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
    graph = StarGraphOrchestrator(
        router=DecisionRouter(),
        agents=build_agents(gateway),
        repository=repository,
        retriever=retriever,
        disclosure_policy=disclosure,
        context_assembler=ContextAssembler(),
        state_machine=ClinicalStateMachine(),
        output_guard=OutputGuard(),
        protected_lexicon=ProtectedLexiconService(repository),
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
        "langsmith_enabled": settings.langsmith_tracing and bool(settings.langsmith_api_key),
        "agents": ["medico_asistente", "paciente", "laboratorio", "radiologia", "especialista"],
        "gateway": service.graph.agents[next(iter(service.graph.agents))].gateway.status(),
    }


@router.post("/sessions")
def start(payload: StartRequest):
    try:
        return get_service().start(payload.case_id)
    except (CaseNotFound, CaseNotAvailable) as exc:
        raise HTTPException(status_code=404, detail="Caso no encontrado o no disponible.") from exc


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    try:
        return get_service().get(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc


@router.post("/sessions/{session_id}/message")
def message(session_id: str, payload: MessageRequest):
    try:
        return get_service().message(session_id, payload.message)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/events")
def events(session_id: str):
    try:
        return get_service().events(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc


@router.post("/sessions/{session_id}/finish")
def finish(session_id: str):
    try:
        return get_service().finish(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc
