"""Repositorio de casos canónicos: carga, validación estructural (JSON Schema) y semántica (reglas cruzadas), compuerta de status."""

from .repository import CanonicalCaseRepository, CaseNotAvailable, CaseNotFound, CaseValidationError

__all__ = ["CanonicalCaseRepository", "CaseNotAvailable", "CaseNotFound", "CaseValidationError"]
