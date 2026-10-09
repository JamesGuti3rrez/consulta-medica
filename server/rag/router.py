from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from .retriever import RAGContractError, RAGNotReadyError
from .service import RAGService

router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])
service = RAGService(settings.rag_index_dir, settings.rag_log_path)


class EvidenceSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    case_id: str = Field(min_length=1, max_length=64)
    allowed_evidence_ids: list[str]
    owner: Literal[
        "public",
        "paciente",
        "medico_asistente",
        "laboratorio",
        "radiologia",
        "especialista",
    ] | None = None
    category: str | None = Field(default=None, max_length=64)
    top_k: int = Field(default=3, ge=1, le=20)
    min_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    session_id: str | None = Field(default=None, max_length=128)
    agent: str | None = Field(default=None, max_length=64)


class CaseSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    specialty: str | None = Field(default=None, max_length=64)
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    session_id: str | None = Field(default=None, max_length=128)
    agent: str | None = Field(default=None, max_length=64)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    scope: Literal["conversation", "evaluation"] = "conversation"
    top_k: int = Field(default=3, ge=1, le=20)
    min_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    session_id: str | None = Field(default=None, max_length=128)
    agent: str | None = Field(default=None, max_length=64)


def _handle_error(error: Exception) -> None:
    if isinstance(error, RAGContractError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    if isinstance(error, RAGNotReadyError):
        raise HTTPException(status_code=503, detail=str(error)) from error
    raise error


@router.get("/health")
def rag_health():
    status = service.health()
    return status


@router.post("/reload")
def rag_reload():
    try:
        return service.reload()
    except Exception as error:  # noqa: BLE001 - convertir a contrato HTTP
        _handle_error(error)


@router.post("/evidence/search")
def evidence_search(request: EvidenceSearchRequest):
    try:
        results = service.evidence_search(**request.model_dump())
        return {
            "case_id": request.case_id,
            "results": [result.as_dict() for result in results],
            "count": len(results),
            "index_fingerprint": service.health().get("fingerprint"),
        }
    except Exception as error:  # noqa: BLE001
        _handle_error(error)


@router.post("/cases/search")
def cases_search(request: CaseSearchRequest):
    try:
        results = service.case_search(**request.model_dump())
        # Un documento público por caso; se devuelve únicamente metadata segura.
        return {
            "results": [
                {
                    "case_id": result.case_id,
                    "specialty": result.specialty,
                    "title": result.title,
                    "score": result.score,
                }
                for result in results
            ],
            "count": len(results),
            "index_fingerprint": service.health().get("fingerprint"),
        }
    except Exception as error:  # noqa: BLE001
        _handle_error(error)


@router.post("/knowledge/search")
def knowledge_search(request: KnowledgeSearchRequest):
    try:
        results = service.knowledge_search(**request.model_dump())
        return {
            "scope": request.scope,
            "results": [result.as_dict() for result in results],
            "count": len(results),
            "index_fingerprint": service.health().get("fingerprint"),
        }
    except Exception as error:  # noqa: BLE001
        _handle_error(error)
