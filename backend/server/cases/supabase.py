"""Casos canónicos en Supabase, accesibles exclusivamente desde el servidor."""

from __future__ import annotations

import copy
from typing import Any

import httpx

from .repository import (
    CASE_ID_PATTERN, CanonicalCaseRepository, CaseNotFound, CaseValidationError,
)
from .rules import check_case_rules
from .validator import validate_case_document
from .consistency import ensure_presentable


class CaseStoreError(RuntimeError):
    """No se pudo consultar o verificar el almacén remoto de casos."""


class SupabaseCaseRepository(CanonicalCaseRepository):
    """Conserva las vistas filtradas del repositorio local, sin leer archivos de casos."""

    def __init__(self, url: str, secret_key: str, *, client: httpx.Client | None = None):
        if not url or not secret_key:
            raise CaseStoreError("Los casos requieren SUPABASE_URL y SUPABASE_SECRET_KEY.")
        self._url = url.rstrip("/") + "/rest/v1/casos_curados"
        self._headers = {"apikey": secret_key}
        if not secret_key.startswith("sb_"):
            self._headers["Authorization"] = f"Bearer {secret_key}"
        self._client = client

    def _request(self, method: str, **kwargs) -> httpx.Response:
        try:
            if self._client is not None:
                response = self._client.request(method, self._url, headers=self._headers, **kwargs)
            else:
                with httpx.Client(timeout=20.0) as client:
                    response = client.request(method, self._url, headers=self._headers, **kwargs)
        except httpx.HTTPError as exc:
            raise CaseStoreError("No se pudo conectar al almacén de casos.") from exc
        if response.is_error:
            # No se incluyen cuerpos remotos, claves ni contenido clínico en el error.
            raise CaseStoreError(f"El almacén de casos respondió HTTP {response.status_code}.")
        return response

    def _rows(self, params: dict[str, str | int]) -> list[dict[str, Any]]:
        try:
            rows = self._request("GET", params=params).json()
        except ValueError as exc:
            raise CaseStoreError("Respuesta inválida del almacén de casos.") from exc
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise CaseStoreError("Respuesta inválida del almacén de casos.")
        return rows

    @staticmethod
    def _document(row: dict[str, Any]) -> dict[str, Any]:
        document = row.get("documento")
        try:
            validate_case_document(document)
            if check_case_rules(document):
                raise CaseValidationError("Reglas cruzadas inválidas.")
            ensure_presentable(document)
            if document["case_id"] != row.get("case_id") or document["status"] != "curado":
                raise CaseValidationError("Identidad o estado inválido.")
        except Exception as exc:
            raise CaseStoreError("Un caso remoto no cumple el contrato de casos curados.") from exc
        return copy.deepcopy(document)

    def list_cases(self) -> list[dict[str, Any]]:
        cases = []
        offset = 0
        while True:
            rows = self._rows({"select": "case_id,documento", "order": "case_id.asc",
                               "limit": 100, "offset": offset})
            if not rows:
                return cases
            cases.extend(self._document(row) for row in rows)
            offset += len(rows)

    def list_curated(self) -> list[str]:
        return [case["case_id"] for case in self.list_cases()]

    def get_case(self, case_id: str) -> dict[str, Any]:
        if not isinstance(case_id, str) or not CASE_ID_PATTERN.fullmatch(case_id):
            raise CaseNotFound(case_id)
        rows = self._rows({"select": "case_id,documento", "case_id": f"eq.{case_id}", "limit": 1})
        if not rows:
            raise CaseNotFound(case_id)
        document = self._document(rows[0])
        if document["case_id"] != case_id:
            raise CaseStoreError("El almacén devolvió otro caso.")
        return document

    def insert_missing(self, cases: list[dict[str, Any]]) -> None:
        """Inserción atómica por lote; repetir la carga no sobrescribe casos existentes."""
        if not cases:
            return
        rows = [{"case_id": case["case_id"], "documento": case} for case in cases]
        # Validar TODO el lote antes de enviar cualquier escritura.
        for row in rows:
            self._document(row)
        headers = {**self._headers, "Prefer": "resolution=ignore-duplicates,return=minimal"}
        # Cliente separado para poder usar Prefer sin mutar las cabeceras de lectura.
        try:
            if self._client is not None:
                response = self._client.post(self._url, headers=headers,
                                             params={"on_conflict": "case_id"}, json=rows)
            else:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(self._url, headers=headers,
                                           params={"on_conflict": "case_id"}, json=rows)
        except httpx.HTTPError as exc:
            raise CaseStoreError("No se pudo importar el lote de casos.") from exc
        if response.is_error:
            raise CaseStoreError(f"La importación respondió HTTP {response.status_code}.")
