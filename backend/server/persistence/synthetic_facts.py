"""Datos sintéticos compartidos por caso: lectura, inserción sin sobrescritura y concurrencia."""

from __future__ import annotations

import httpx

from server.cases.supabase import CaseStoreError


class SupabaseSyntheticFacts:
    def __init__(self, url: str, secret_key: str, *, client=None):
        if not url or not secret_key:
            raise CaseStoreError("Los datos adicionales requieren credenciales de Supabase.")
        self.url = url.rstrip("/") + "/rest/v1/caso_datos_adicionales"
        self.headers = {"apikey": secret_key}
        if not secret_key.startswith("sb_"):
            self.headers["Authorization"] = f"Bearer {secret_key}"
        self.client = client

    def _request(self, method, *, headers=None, **kwargs):
        headers = {**self.headers, **(headers or {})}
        try:
            if self.client is not None:
                response = self.client.request(method, self.url, headers=headers, **kwargs)
            else:
                with httpx.Client(timeout=20) as client:
                    response = client.request(method, self.url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise CaseStoreError("No se pudo conectar al almacén de datos adicionales.") from exc
        if response.is_error:
            raise CaseStoreError(f"Los datos adicionales respondieron HTTP {response.status_code}.")
        return response

    def list_for_case(self, case_id: str) -> list[dict]:
        result = []
        while True:
            try:
                rows = self._request("GET", params={
                    "case_id": f"eq.{case_id}", "select": "*", "order": "clave.asc",
                    "limit": 100, "offset": len(result),
                }).json()
            except ValueError as exc:
                raise CaseStoreError("Respuesta inválida de datos adicionales.") from exc
            if not isinstance(rows, list) or any(
                not isinstance(row, dict) or row.get("case_id") != case_id for row in rows
            ):
                raise CaseStoreError("Respuesta inválida de datos adicionales.")
            if not rows:
                return result
            result.extend(rows)

    def insert_missing(self, rows: list[dict]) -> None:
        if rows:
            self._request("POST", params={"on_conflict": "case_id,clave"}, json=rows,
                          headers={"Prefer": "resolution=ignore-duplicates,return=minimal"})
