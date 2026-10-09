"""Compatibilidad de imports del prototipo legado. No agregar lógica nueva aquí."""

from server.cases.legacy import public_case, read_case
from server.engine.evaluation.legacy import evaluate_reasoning, match_differential

__all__ = ["public_case", "read_case", "evaluate_reasoning", "match_differential"]
