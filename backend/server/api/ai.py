"""Rutas del sistema multiagente (/api/ai): sesiones, turnos, eventos y cierre."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from functools import lru_cache

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from server.ai.agents.base import PROMPTS_DIR
from server.ai.agents.reformulador import QuestionReformulator
from server.ai.agents.history_composer import HistoryComposer
from server.ai.agents.registry import build_agents
from server.ai.llm.factory import build_gateway
from server.ai.llm.gateway import LLMUnavailable
from server.auth import SupabaseAuth
from server.cases import CaseNotAvailable, CaseNotFound
from server.cases.catalog import CURATED_CASES_DIR
from server.cases.source import build_case_repository
from server.config import settings
from server.domain.final_diagnosis import InvalidDiagnosis, normalize_final_diagnosis
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
    SessionNotFinished,
    SessionNotFound,
    SessionStoreError,
    StarGraphOrchestrator,
    SupabaseSessionStore,
)
from server.persistence import (
    AttemptStoreError, DiagnosisStoreError, InMemoryDiagnoses, SupabaseAttempts, SupabaseDiagnoses, build_attempt,
)
from server.persistence.synthetic_facts import SupabaseSyntheticFacts
from server.orchestration.patient_completion import PatientHistoryCompletion
from server.rag.embedded import EmbeddedRAGRetriever
from server.rag.retriever import CaseEvidenceRetriever, HttpRetriever
from server.rag.supabase import SupabasePgvectorRetriever, SupabaseRAGError
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
SESSION_NOT_FOUND = "Sesión no encontrada."
REPORT_NOT_READY = "El reporte estará disponible al terminar la consulta."
CLOSE_NOT_CONFIRMED = "Confirma el cierre de la consulta para registrar tu diagnóstico."
DIAGNOSIS_NOT_REGISTERED = "No se pudo registrar tu diagnóstico. La consulta sigue abierta: inténtalo de nuevo."
UNAUTHORIZED_DETAIL = "Inicia sesión o vuelve a empezar la consulta para continuar."
# Credencial de capacidad de las consultas de invitado: secrets.token_urlsafe(32), 256 bits en base64url.
SESSION_TOKEN_FORMAT = re.compile(r"[A-Za-z0-9_-]{43}")


class StartRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=64)


class MessageRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)


class HypothesisItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    discarded: bool = False
    reason: str = Field(default="", max_length=500)


class FinishRequest(BaseModel):
    """Diagnóstico final del estudiante (HU-006). No se califica: se registra junto al puntaje del motor clínico.

    El texto se valida en la ruta (normalize_final_diagnosis) para responder con un motivo claro; el límite de
    Field solo frena cuerpos desmedidos. confirmado debe ser true: es la confirmación de cierre del alumno.
    """

    diagnosis: str | None = Field(default=None, max_length=10000)
    hypotheses: list[HypothesisItem] = Field(default_factory=list, max_length=50)
    confirmado: bool = False


# Registro de diagnósticos con SESSION_STORE=memoria (vive lo mismo que STORE).
DIAGNOSES = InMemoryDiagnoses()


@lru_cache
def get_diagnoses() -> InMemoryDiagnoses | SupabaseDiagnoses:
    """Registro del diagnóstico final: en Supabase si las sesiones están en Supabase, si no en memoria."""
    if settings.session_store == "supabase":
        return SupabaseDiagnoses(settings.supabase_url, settings.supabase_secret_key)
    return DIAGNOSES


@lru_cache
def get_attempts() -> SupabaseAttempts | None:
    """Guardado de intentos; None si el historial está desactivado o el servidor no tiene configurado Supabase."""
    if not settings.history_enabled:
        return None
    if not (settings.supabase_url and settings.supabase_publishable_key and settings.supabase_secret_key):
        return None
    return SupabaseAttempts(settings.supabase_url, settings.supabase_publishable_key, settings.supabase_secret_key)


@lru_cache
def get_session_auth() -> SupabaseAuth | None:
    """Verificación del token del alumno con Supabase Auth; None si el servidor no tiene Supabase."""
    if not settings.auth_enabled:
        return None
    return SupabaseAuth(settings.supabase_url, settings.supabase_publishable_key)


@lru_cache
def get_service() -> MultiAgentSessionService:
    repository = build_case_repository(CASES_DIR, config=settings)
    if settings.rag_backend == "supabase_pgvector":
        retriever = SupabasePgvectorRetriever(settings.supabase_url, settings.supabase_secret_key)
    elif settings.case_store == "supabase":
        # La evidencia procede del caso remoto actual, nunca de un indice local antiguo.
        retriever = CaseEvidenceRetriever(repository)
    elif settings.rag_service_url:
        retriever = HttpRetriever(settings.rag_service_url, token=settings.rag_http_token)
    elif settings.rag_backend != "local":
        raise ValueError(
            f"RAG_BACKEND no reconocido: {settings.rag_backend!r} "
            "(use local o supabase_pgvector)."
        )
    elif settings.rag_embedded_enabled and settings.case_store == "local":
        embedded = EmbeddedRAGRetriever(settings.rag_index_dir, settings.rag_log_path, repository=repository)
        retriever = embedded if embedded.ready else CaseEvidenceRetriever(repository)
    else:
        retriever = CaseEvidenceRetriever(repository)
    gateway = build_gateway()
    disclosure = DisclosurePolicy()
    state_machine = ClinicalStateMachine()
    completion = None
    if settings.synthetic_case_data and settings.case_store == "supabase" and settings.groq_api_keys:
        completion = PatientHistoryCompletion(
            HistoryComposer(gateway),
            SupabaseSyntheticFacts(settings.supabase_url, settings.supabase_secret_key),
            OutputGuard(),
        )
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
        patient_completion=completion,
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
        "case_store": settings.case_store,
        "synthetic_case_data": service.graph.patient_completion is not None,
        "rag_connected": isinstance(
            service.graph.retriever,
            (HttpRetriever, EmbeddedRAGRetriever, SupabasePgvectorRetriever),
        ),
        "retrieval_mode": (
            "http-rag" if isinstance(service.graph.retriever, HttpRetriever)
            else "supabase-pgvector" if isinstance(service.graph.retriever, SupabasePgvectorRetriever)
            else "embedded-lightrag" if isinstance(service.graph.retriever, EmbeddedRAGRetriever)
            else "supabase-case-evidence" if settings.case_store == "supabase"
            else "deterministic-case-fallback"
        ),
        "session_store": settings.session_store,
        "langsmith_enabled": settings.langsmith_tracing and bool(settings.langsmith_api_key),
        "agents": ["medico_asistente", "paciente", "laboratorio", "radiologia", "especialista"],
        "gateway": service.graph.agents[next(iter(service.graph.agents))].gateway.status(),
    }


@router.post("/sessions")
def start(payload: StartRequest, request: Request, authorization: str | None = Header(default=None)):
    owner_id = _start_owner(request, authorization)
    # Sin alumno identificado, la consulta se protege con una credencial de capacidad de 256 bits que solo
    # recibe quien la crea; el servidor guarda únicamente su hash.
    session_token = None if owner_id else secrets.token_urlsafe(32)
    try:
        result = get_service().start(payload.case_id, owner_id=owner_id,
                                     access_token_hash=_token_hash(session_token) if session_token else None)
    except (CaseNotFound, CaseNotAvailable) as exc:
        raise HTTPException(status_code=404, detail="Caso no encontrado o no disponible.") from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc
    if session_token:
        result["session_token"] = session_token
    return result


def authorize_session(
    session_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None),
) -> str | None:
    """Política de TA-011 para toda operación sobre una sesión; devuelve el id del alumno, si lo hay.

    - Sin credencial, o con una malformada o que Supabase rechaza: 401, antes de buscar la sesión.
    - Sesión de un alumno: solo su propio token (Authorization: Bearer) la abre.
    - Sesión de invitado: solo la credencial de capacidad que recibió al crearla (X-Session-Token).
    - Sesión ajena o inexistente: el mismo 404, para no revelar qué sesiones existen.
    """
    token = _bearer_token(request, authorization)
    if x_session_token is not None and not SESSION_TOKEN_FORMAT.fullmatch(x_session_token):
        raise _deny(request, 401, "credencial_malformada", f"capacidad={_mask(x_session_token)}")
    if token is None and x_session_token is None:
        raise _deny(request, 401, "sin_credencial", "anonimo")
    user_id = _verified_user(request, token) if token else None
    who = f"usuario={user_id}" if user_id else f"capacidad={_mask(x_session_token)}"
    try:
        owner_id, token_hash = get_service().access_of(session_id)
    except SessionNotFound as exc:
        raise _deny(request, 404, "inexistente", who) from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc
    if owner_id:
        allowed = user_id == owner_id
    else:
        allowed = bool(token_hash and x_session_token
                       and hmac.compare_digest(token_hash, _token_hash(x_session_token)))
    if not allowed:
        raise _deny(request, 404, "ajena", who)
    return user_id


@router.get("/sessions/{session_id}", dependencies=[Depends(authorize_session)])
def get_session(session_id: str):
    try:
        return get_service().get(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND) from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc


@router.post("/sessions/{session_id}/message", dependencies=[Depends(authorize_session)])
def message(session_id: str, payload: MessageRequest):
    try:
        return get_service().message(session_id, payload.message)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND) from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc
    except LLMUnavailable as exc:
        # Claves rechazadas o servicio caído: se registra el motivo y el estudiante recibe un aviso claro.
        print(f"[llm] {exc}")
        raise HTTPException(status_code=503, detail=LLM_UNAVAILABLE_DETAIL) from exc
    except SupabaseRAGError as exc:
        print(f"[rag] {exc}")
        raise HTTPException(
            status_code=503,
            detail="El servicio de recuperación de evidencia no está disponible. Inténtalo de nuevo.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/events", dependencies=[Depends(authorize_session)])
def events(session_id: str):
    try:
        return get_service().events(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND) from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc


@router.post("/sessions/{session_id}/finish", dependencies=[Depends(authorize_session)])
def finish(session_id: str, payload: FinishRequest | None = None, authorization: str | None = Header(default=None)):
    """Propone y registra el diagnóstico final y cierra la consulta (HU-006).

    Orden pensado para que un fallo no deje un cierre a medias: validar el texto y la confirmación; si la consulta
    ya estaba cerrada, devolver lo mismo que la primera vez; registrar el diagnóstico (alumno con sesión); cerrar.
    Si el registro falla, 503 y la consulta sigue abierta. Si otro envío de la misma consulta registró antes, vale
    el suyo: un segundo envío nunca cambia el diagnóstico registrado.
    """
    payload = payload or FinishRequest()
    try:
        diagnosis = normalize_final_diagnosis(payload.diagnosis)
    except InvalidDiagnosis as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    if not payload.confirmado:
        raise HTTPException(status_code=422, detail=CLOSE_NOT_CONFIRMED)
    hypotheses = [item.model_dump() for item in payload.hypotheses]
    try:
        service = get_service()
        owner_id, case_id, finished = service.closing_state(session_id)
        if finished:
            record = get_diagnoses().by_session(session_id) if owner_id else None
        elif owner_id:
            # El dueño y el caso los fija la sesión (TA-011), nunca el cuerpo de la petición.
            record, _ = get_diagnoses().register(session_id=session_id, user_id=owner_id, case_id=case_id,
                                                 diagnosis=diagnosis, hypotheses=hypotheses)
            diagnosis, hypotheses = record.diagnostico, record.hipotesis
        else:
            record = None
        result = service.finish(session_id, diagnosis=diagnosis, hypotheses=hypotheses)
        result["registro"] = _registry_summary(owner_id, record)
        stored = payload.model_copy(update={"diagnosis": diagnosis,
                                            "hypotheses": [HypothesisItem(**item) for item in hypotheses]})
        result["attempt"] = _save_attempt(service, result, stored, authorization)
        result["report"] = service.report(session_id)
        return result
    except DiagnosisStoreError as exc:
        print(f"[diagnosticos] {exc}")
        raise HTTPException(status_code=503, detail=DIAGNOSIS_NOT_REGISTERED) from exc
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND) from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc


def _registry_summary(owner_id: str | None, record) -> dict:
    """Lo que el alumno necesita saber de su registro: si quedó guardado y con qué número de intento."""
    if not owner_id:
        return {"guardado": False, "motivo": "invitado"}
    if record is None:
        # Consulta cerrada antes de existir el registro de HU-006: no se crea uno con un texto nuevo.
        return {"guardado": False, "motivo": "cerrada_sin_registro"}
    return {"guardado": True, "id": record.id, "numero_intento": record.numero_intento}


@router.get("/sessions/{session_id}/report", dependencies=[Depends(authorize_session)])
def report(session_id: str):
    """Reporte final (HU-007): solo para el dueño, que ya validó authorize_session, y solo con la consulta cerrada."""
    try:
        return get_service().report(session_id)
    except SessionNotFinished as exc:
        raise HTTPException(status_code=409, detail=REPORT_NOT_READY) from exc
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND) from exc
    except SessionStoreError as exc:
        raise _store_unavailable(exc) from exc


def _save_attempt(service: MultiAgentSessionService, session: dict, payload: FinishRequest,
                  authorization: str | None) -> dict:
    """Guarda la consulta en el historial del alumno, solo si tiene la sesión iniciada.

    Un fallo de Supabase no impide ver la evaluación: se informa en attempt y la consulta termina igual.
    """
    if session.get("attempt_id"):
        return {"saved": True, "id": session["attempt_id"]}
    attempts = get_attempts()
    if attempts is None and not settings.history_enabled:
        # Sin historial no hay nada que guardar ni que avisar, tenga o no sesión el alumno.
        return {"saved": False, "reason": "desactivado"}
    token = _bearer(authorization)
    if not token:
        return {"saved": False, "reason": "sin_sesion"}
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


def _token_hash(session_token: str) -> str:
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()


def _mask(secret: str | None) -> str:
    """Para los registros: nunca se escribe una credencial completa."""
    if not secret:
        return "ninguna"
    return f"{secret[:6]}…{secret[-4:]}" if len(secret) > 12 else "…"


def _deny(request: Request, status: int, reason: str, who: str) -> HTTPException:
    print(f"[autorizacion] {status} {request.method} {request.url.path} {who} motivo={reason}")
    return HTTPException(status_code=status, detail=SESSION_NOT_FOUND if status == 404 else UNAUTHORIZED_DETAIL)


def _bearer_token(request: Request, authorization: str | None) -> str | None:
    """Token de Supabase de la cabecera Authorization; 401 si llega con otro esquema o vacía."""
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not token.strip() or len(token) > 8192:
        raise _deny(request, 401, "esquema_invalido", f"autorizacion={_mask(authorization)}")
    return token.strip()


def _verified_user(request: Request, token: str) -> str:
    auth = get_session_auth()
    if auth is None:
        raise _deny(request, 401, "auth_no_configurada", f"token={_mask(token)}")
    try:
        return auth.verify(token).id
    except HTTPException as exc:
        if exc.status_code == 401:
            raise _deny(request, 401, "token_rechazado", f"token={_mask(token)}") from exc
        raise


def _start_owner(request: Request, authorization: str | None) -> str | None:
    """Alumno que inicia la consulta; None si es invitado.

    Un token rechazado por Supabase es un 401. Si Supabase no responde, la consulta empieza como de invitado,
    con su credencial de capacidad, en lugar de fallar.
    """
    token = _bearer_token(request, authorization)
    if token is None or get_session_auth() is None:
        return None
    try:
        return _verified_user(request, token)
    except HTTPException as exc:
        if exc.status_code == 401:
            raise
        print("[autorizacion] Supabase Auth no respondió al iniciar: la consulta empieza como de invitado")
        return None
