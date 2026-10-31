from __future__ import annotations

import re
import unicodedata


def _normalize(text: str) -> str:
    raw = unicodedata.normalize("NFD", str(text or "").casefold())
    raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", raw).strip()


class OutputGuard:
    """Segunda barrera: valida la salida sin recibir `protected` ni el caso completo."""

    def validate(self, text: str, forbidden_terms: set[str]) -> tuple[bool, str | None]:
        source = f" {_normalize(text)} "
        leaks = [term for term in forbidden_terms if f" {term} " in source]
        if leaks:
            leaks = sorted(set(leaks))
            # La causa se devuelve también en eventos: nunca revelar el término que se bloqueó.
            return False, "contenido_protegido"
        return True, None
