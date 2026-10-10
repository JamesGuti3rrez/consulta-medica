"""Aplicación FastAPI: arma el servidor, registra las rutas de api/ y sirve el frontend."""

import mimetypes
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .api.routes import router as api_router
from .rag.router import router as rag_router

PUBLIC_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public"

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


# Rutas de la API: las del RAG (rag/router.py) van antes que api/routes.py, que termina con la
# respuesta 404 para cualquier otra ruta /api/.
app.include_router(rag_router)
app.include_router(api_router)

# Todo lo demás son los archivos del frontend.
app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
