"""Filtro de salida y detección de términos protegidos (compartido por orquestación, RAG y pipeline)."""

from .output_guard import OutputGuard

__all__ = ["OutputGuard"]
