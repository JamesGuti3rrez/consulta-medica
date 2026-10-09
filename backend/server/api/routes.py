"""Rutas HTTP de la API (/api). Solo validan y responden; la lógica clínica vivirá en engine/."""

import secrets

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..cases.catalog import load_curated_cases, to_student_case
from ..config import settings

router = APIRouter(prefix="/api")


@router.get("/caso")
def get_case():
    cases = load_curated_cases()
    if not cases:
        raise HTTPException(status_code=503, detail="No hay casos curados disponibles.")
    return to_student_case(secrets.choice(cases))


@router.get("/status")
def get_status():
    cases = load_curated_cases()
    return {
        "caseConfigured": bool(cases),
        "simulationReady": False,
        "availableCases": len(cases),
    }


@router.get("/config")
def get_public_config():
    """Datos que el navegador necesita para iniciar sesión. Solo la clave pública, nunca la secreta."""
    if not settings.auth_enabled:
        return {"auth": False}
    return {
        "auth": True,
        "supabaseUrl": settings.supabase_url,
        "supabaseKey": settings.supabase_publishable_key,
    }


# Debe ir al final: cualquier otra ruta /api que no exista responde 404 en JSON.
@router.api_route("/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def api_not_found(rest: str):
    return JSONResponse(status_code=404, content={"error": "Ruta de API no encontrada"})
