"""Adaptadores de entrada: ingesta manual, extracción determinista de MedQA y datos complementarios de Synthea."""

from .medqa import extract_medqa_candidates

__all__ = ["extract_medqa_candidates"]

