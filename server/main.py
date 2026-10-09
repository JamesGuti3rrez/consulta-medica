"""Servidor local (FastAPI): la API del caso clínico guionizado y los archivos de public/."""

import json
import mimetypes
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .clinical_case import evaluate_reasoning, match_differential, public_case, read_case
from .api.ai import router as ai_router
from .rag.router import router as rag_router
from .config import settings

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"
MAX_BODY_BYTES = 100_000

# En Windows los tipos se leen del registro y pueden venir mal: se fijan los que usa la web.
for extension, content_type in {
    ".js": "text/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}.items():
    mimetypes.add_type(content_type, extension)

app = FastAPI(
    title="Consulta Médica Virtual",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    else:
        # El navegador puede guardar los archivos, pero confirma en cada visita que no cambiaron:
        # así nunca se mezcla un HTML nuevo con un JS viejo.
        response.headers["Cache-Control"] = "no-cache"
    return response


async def read_json(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload demasiado grande")
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON invalido")
    return data if isinstance(data, dict) else {}


@app.get("/api/caso")
def get_case():
    return public_case(read_case())


@app.get("/api/status")
def get_status():
    return {"provider": "guion-local", "scripted": True}


@app.get("/api/config")
def get_public_config():
    """Datos que el navegador necesita para iniciar sesión. Solo la clave pública, nunca la secreta."""
    if not settings.auth_enabled:
        return {"auth": False}
    return {
        "auth": True,
        "supabaseUrl": settings.supabase_url,
        "supabaseKey": settings.supabase_publishable_key,
    }


@app.post("/api/chat")
async def chat(request: Request):
    body = await read_json(request)
    script = read_case().get("guion_conversacion", [])
    turn_index = body.get("turnIndex")
    if not isinstance(turn_index, int) or isinstance(turn_index, bool):
        turn_index = 0
    turn = script[turn_index] if 0 <= turn_index < len(script) else None

    if not turn:
        return {
            "done": True,
            "doctorQuestion": "La secuencia guiada del caso ha terminado.",
            "answer": "Ya respondí las preguntas principales de este caso. Puedes realizar el diagnóstico.",
            "nextPrompt": None,
            "provider": "guion-local",
        }

    next_turn = script[turn_index + 1] if turn_index + 1 < len(script) else None
    return {
        "done": False,
        "doctorQuestion": turn["pregunta_doctor"],
        "answer": turn["respuesta_paciente"],
        "nextPrompt": next_turn["sugerencia_alumno"] if next_turn else None,
        "provider": "guion-local",
    }


@app.post("/api/hipotesis")
async def recognize_hypothesis(request: Request):
    body = await read_json(request)
    match = match_differential(body.get("texto"), read_case().get("diagnosticos_diferenciales", []))
    if not match:
        return {"reconocida": False}
    return {"reconocida": True, "id": match["id"], "nombre": match["nombre"]}


@app.post("/api/evaluar")
async def evaluate(request: Request):
    body = await read_json(request)
    return {"razonamiento": evaluate_reasoning(read_case(), body)}


app.include_router(ai_router)
app.include_router(rag_router)


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def api_not_found(rest: str):
    return JSONResponse(status_code=404, content={"error": "Ruta de API no encontrada"})


# Todo lo demás son archivos de public/. El caso clínico y el código quedan fuera de esta carpeta.
# En Vercel, public/ lo sirve su CDN directamente; montarlo aquí solo hace falta en local.
if not os.getenv("VERCEL"):
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
