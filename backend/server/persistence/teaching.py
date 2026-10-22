"""Operaciones del panel docente sobre las tablas actuales de Supabase."""
from __future__ import annotations

import httpx

from server.cases.supabase import CaseStoreError, SupabaseCaseRepository


class TeachingStoreError(CaseStoreError):
    """Error seguro para mostrar en el panel docente."""


class TeachingStore:
    def __init__(self, url: str, secret_key: str, *, client=None):
        if not url or not secret_key:
            raise TeachingStoreError("El panel docente requiere credenciales de Supabase.")
        self.base = url.rstrip("/") + "/rest/v1"
        self.headers = {"apikey": secret_key}
        if not secret_key.startswith("sb_"):
            self.headers["Authorization"] = f"Bearer {secret_key}"
        self.client = client
        self.cases = SupabaseCaseRepository(url, secret_key, client=client)

    def request(self, method, path, **kwargs):
        try:
            if self.client is not None:
                response = self.client.request(method, self.base + path, headers=self.headers, **kwargs)
            else:
                with httpx.Client(timeout=35) as client:
                    response = client.request(method, self.base + path, headers=self.headers, **kwargs)
        except httpx.HTTPError as exc:
            raise TeachingStoreError("No se pudo conectar con Supabase para gestionar los casos.") from exc
        if response.is_error:
            if response.status_code == 409:
                raise TeachingStoreError("Un identificador ya tiene otro contenido. Recarga el catálogo y revisa el lote.")
            if response.status_code == 404 and path.startswith("/rpc/"):
                raise TeachingStoreError("Aplica la migración 0004_panel_docente.sql en Supabase para publicar casos.")
            raise TeachingStoreError(f"La operación docente respondió HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError as exc:
            raise TeachingStoreError("Supabase devolvió una respuesta no válida.") from exc

    def evidence(self, case_id):
        rows = []
        while True:
            page = self.request("GET", "/rag_evidencias", params={
                "case_id": f"eq.{case_id}",
                "select": "case_id,evidence_id,owner,category,requires,content,embedding_model,source_hash,updated_at",
                "order": "evidence_id.asc", "limit": 100, "offset": len(rows),
            })
            if not isinstance(page, list) or any(row.get("case_id") != case_id for row in page):
                raise CaseStoreError("Respuesta de evidencias no válida.")
            if not page:
                return rows
            rows.extend(page)

    def publish(self, cases, evidence, *, user_id, filename):
        result = self.request("POST", "/rpc/importar_casos_docente", json={
            "p_casos": cases, "p_evidencias": evidence, "p_docente_id": user_id, "p_archivo": filename,
        })
        if not isinstance(result, dict) or not isinstance(result.get("casos_insertados"), int):
            raise TeachingStoreError("No se pudo verificar el resultado de la publicación.")
        return result

