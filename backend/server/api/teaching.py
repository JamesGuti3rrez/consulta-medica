"""Panel de profesor: catálogo remoto, importación y evidencia RAG real."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from case_preparation.indexing.documents import IndexingError, build_case_documents
from server.auth import AuthUser, current_user, require_staff
from server.cases import CaseNotFound
from server.cases.repository import CASE_ID_PATTERN
from server.cases.consistency import review_case
from server.cases.upload_templates import example_case, excel_template
from server.cases.uploads import MAX_FILE_BYTES, UploadError, prepare_cases, read_upload
from server.config import settings
from server.engine.disclosure.policy import DisclosurePolicy
from server.orchestration.router import DecisionRouter
from server.persistence.synthetic_facts import SupabaseSyntheticFacts
from server.persistence.teaching import TeachingStore
from server.rag.supabase import SupabasePgvectorRetriever, SupabaseRAGError
from server.rag.catalog_sync import prepare_evidence, synchronize_catalog

router = APIRouter(prefix="/api/docente", tags=["docente"])


def get_teaching_store() -> TeachingStore:
    return TeachingStore(settings.supabase_url, settings.supabase_secret_key)


def _case(store, case_id):
    if not CASE_ID_PATTERN.fullmatch(case_id):
        raise HTTPException(404, "Caso no encontrado.")
    try:
        return store.cases.get_case(case_id)
    except CaseNotFound as exc:
        raise HTTPException(404, "Caso no encontrado.") from exc


def _documents(cases):
    try:
        return build_case_documents(cases)
    except IndexingError as exc:
        raise UploadError(str(exc)) from exc


def _prepare(store, raw, user):
    cases, errors, warnings = prepare_cases(raw, store.cases.list_cases(), user.id)
    if not errors:
        try:
            _documents(cases)
        except UploadError as exc:
            errors.append({"case_id": "", "path": "on_request", "message": str(exc)})
    return cases, errors, warnings


@router.get("/sesion")
def session(user: AuthUser = Depends(current_user)):
    return {"id": user.id, "email": user.email, "rol": user.role,
            "panel_docente": user.role in {"profesor", "administrativo"}}


@router.get("/casos")
def catalog(user: AuthUser = Depends(require_staff), store=Depends(get_teaching_store)):
    cases = store.cases.list_cases()
    by_specialty = Counter(case["specialty"] for case in cases)
    return {
        "total": len(cases), "por_especialidad": dict(by_specialty),
        "case_store": settings.case_store, "rag_backend": settings.rag_backend,
        "casos": [{"case_id": case["case_id"], "titulo": case["title"], "especialidad": case["specialty"],
                   "paciente": case["public"]["patient"], "diagnostico": case["protected"]["diagnosis"]["name"],
                   "evidencias": len(case["on_request"]), "fuente": case["source"]["dataset"]}
                  for case in cases],
    }


@router.get("/casos/{case_id}")
def detail(case_id: str, user: AuthUser = Depends(require_staff), store=Depends(get_teaching_store)):
    case = _case(store, case_id)
    # La ausencia de la tabla no se disfraza de cero evidencias.
    evidence = store.evidence(case_id)
    facts = SupabaseSyntheticFacts(settings.supabase_url, settings.supabase_secret_key, client=store.client).list_for_case(case_id)
    expected = _documents([case])
    indexed = {item["evidence_id"]: item for item in evidence}
    stale, missing = [], []
    for document in expected:
        row = indexed.get(document.source_id)
        if row is None:
            missing.append(document.source_id)
        elif row.get("source_hash") != hashlib.sha256(document.text.encode("utf-8")).hexdigest():
            stale.append(document.source_id)
    return {
        "caso": case, "evidencias_rag": evidence, "datos_adicionales": facts,
        "consistencia": review_case(case),
        "rag": {"backend": settings.rag_backend, "tabla": "rag_evidencias", "esperadas": len(expected),
                "indexadas": len(evidence), "faltantes": missing, "desactualizadas": stale,
                "por_propietario": dict(Counter(item["owner"] for item in evidence)),
                "por_categoria": dict(Counter(item["category"] for item in evidence))},
    }


class ConsistencyRequest(BaseModel):
    caso: dict


@router.post("/consistencia")
def consistency(payload: ConsistencyRequest, user: AuthUser = Depends(require_staff)):
    if len(json.dumps(payload.caso).encode()) > MAX_FILE_BYTES:
        raise HTTPException(413, "El caso supera el tamaño permitido.")
    return review_case(payload.caso)


@router.get("/plantilla")
def template(formato: Literal["json", "xlsx"] = "xlsx",
             user: AuthUser = Depends(require_staff), store=Depends(get_teaching_store)):
    try:
        case = example_case(store.cases.list_cases())
        content = (json.dumps({"casos": [case]}, ensure_ascii=False, indent=2).encode("utf-8")
                   if formato == "json" else excel_template(case))
    except (ValueError, KeyError, ImportError) as exc:
        raise HTTPException(503, "No se pudo preparar la plantilla. Revisa el catálogo y las dependencias de Excel.") from exc
    media = "application/json" if formato == "json" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="plantilla_casos.{formato}"'})


@router.post("/importaciones/validar")
async def validate_upload(request: Request, archivo: str = Query(min_length=1, max_length=200),
                          user: AuthUser = Depends(require_staff), store=Depends(get_teaching_store)):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(413, "El archivo supera el límite de 4 MB.")
    try:
        raw = await run_in_threadpool(read_upload, archivo, bytes(content))
        cases, errors, warnings = await run_in_threadpool(_prepare, store, raw, user)
    except UploadError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"valido": not errors, "casos": cases if not errors else [],
            "errores": errors, "avisos": warnings, "archivo": archivo}


class PublishRequest(BaseModel):
    casos: list[dict] = Field(min_length=1, max_length=100)
    archivo: str = Field(min_length=1, max_length=200)


@router.post("/importaciones")
def publish(payload: PublishRequest, user: AuthUser = Depends(require_staff), store=Depends(get_teaching_store)):
    if len(json.dumps(payload.casos, ensure_ascii=False).encode("utf-8")) > 8 * 1024 * 1024:
        raise HTTPException(413, "El lote es demasiado grande.")
    try:
        cases, errors, warnings = _prepare(store, payload.casos, user)
        if errors:
            raise HTTPException(422, {"errores": errors})
        evidence = prepare_evidence(cases)
    except UploadError as exc:
        raise HTTPException(422, str(exc)) from exc
    result = store.publish(cases, evidence, user_id=user.id, filename=payload.archivo)
    return {**result, "avisos": warnings, "case_store": settings.case_store,
            "rag_backend": settings.rag_backend}


@router.post("/rag/sincronizar")
def sync_all(user: AuthUser = Depends(require_staff), store=Depends(get_teaching_store)):
    try:
        result = synchronize_catalog(store, user_id=user.id)
    except IndexingError as exc:
        raise HTTPException(422, "El catálogo contiene evidencia que no puede indexarse. Revisa sus datos protegidos.") from exc
    return {**result, "rag_backend": settings.rag_backend}


class SearchRequest(BaseModel):
    pregunta: str = Field(min_length=2, max_length=2000)


@router.post("/casos/{case_id}/probar-rag")
def probe(case_id: str, payload: SearchRequest, user: AuthUser = Depends(require_staff),
          store=Depends(get_teaching_store)):
    case = _case(store, case_id)
    route = DecisionRouter().route(payload.pregunta)
    authorization = DisclosurePolicy().authorize(case=case, role=route.target, intent=route.intent,
                                                 student_message=payload.pregunta)
    allowed = authorization.allowed_evidence_ids
    # Se prueba la RPC real con la MISMA autorización del simulador; no permite saltarse reveal_policy.
    try:
        retriever = SupabasePgvectorRetriever(settings.supabase_url, settings.supabase_secret_key, client=store.client)
        results = retriever.retrieve(query=payload.pregunta, case_id=case_id, agent_role=route.target,
                                     allowed_evidence_ids=allowed, top_k=5)
    except SupabaseRAGError as exc:
        raise HTTPException(503, "La búsqueda pgvector falló. Revisa la RPC y el modelo de embeddings.") from exc
    return {"agente": route.target.value, "intencion": route.intent.value,
            "temas": authorization.matched_requirements, "evidencias_autorizadas": allowed,
            "resultados": [{"evidence_id": item.evidence_id, "texto": item.text, "puntaje": item.score}
                           for item in results],
            "backend_simulador": settings.rag_backend, "backend_prueba": "supabase_pgvector"}

