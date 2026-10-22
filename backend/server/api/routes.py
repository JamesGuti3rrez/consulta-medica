"""Rutas HTTP de la API (/api). Solo validan y responden; la lógica clínica vivirá en engine/."""

import secrets
from collections import Counter

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..cases.catalog import to_student_case
from ..cases.source import load_configured_cases as load_curated_cases
from ..cases.validator import load_schema
from ..config import settings

router = APIRouter(prefix="/api")

# Especialidades válidas: las del esquema oficial.
SPECIALTIES = tuple(load_schema()["properties"]["specialty"]["enum"])


@router.get("/caso")
def get_case(especialidad: str | None = None, caso: str | None = None, excluir: str | None = None):
    """Un caso curado al azar; con ?especialidad=…, solo de esa especialidad (la elige el estudiante).

    ?excluir=A,B lista los casos que el estudiante ya vio, empezando por el actual («Probar otro caso»).
    Si ya los vio todos, solo se evita el actual, para no repetir el mismo paciente seguido.

    ?caso=EME-103 devuelve ese caso: solo para pruebas (docs/guia_de_pruebas). Entrega la misma vista
    pública que el azar, sin protected.
    """
    if especialidad is not None and especialidad not in SPECIALTIES:
        raise HTTPException(status_code=422, detail=f"Especialidad no válida. Use una de: {', '.join(SPECIALTIES)}.")
    cases = load_curated_cases()
    if caso is not None:
        chosen = next((case for case in cases if case["case_id"] == caso), None)
        if chosen is None:
            raise HTTPException(status_code=404, detail="Caso no encontrado.")
        return to_student_case(chosen)
    if especialidad is not None:
        cases = [case for case in cases if case["specialty"] == especialidad]
    if not cases:
        raise HTTPException(status_code=503, detail="No hay casos curados disponibles.")
    seen = [case_id.strip() for case_id in (excluir or "").split(",") if case_id.strip()]
    if seen:
        cases = (
            [case for case in cases if case["case_id"] not in seen]
            or [case for case in cases if case["case_id"] != seen[0]]
            or cases
        )
    return to_student_case(secrets.choice(cases))


@router.get("/status")
def get_status():
    cases = load_curated_cases()
    by_specialty = Counter(case["specialty"] for case in cases)
    return {
        "caseConfigured": bool(cases),
        "caseStore": settings.case_store,
        "availableCases": len(cases),
        "casesBySpecialty": {specialty: by_specialty.get(specialty, 0) for specialty in SPECIALTIES},
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
        "history": settings.history_enabled,
    }


# Debe ir al final: cualquier otra ruta /api que no exista responde 404 en JSON.
@router.api_route("/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def api_not_found(rest: str):
    return JSONResponse(status_code=404, content={"error": "Ruta de API no encontrada"})
