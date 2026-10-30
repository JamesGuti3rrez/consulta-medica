"""Proyección de auditoría: metadatos permitidos, sin textos clínicos ni credenciales."""
from __future__ import annotations

SAFE_KEYS = frozenset({"session_id", "case_id", "type", "phase", "intent", "agent", "provider", "model",
                       "input_tokens", "output_tokens", "fallback_used", "grounding_retry_used",
                       "grounding_fallback_used", "evidence_ids", "blocked", "block_reason", "data_source",
                       "synthetic_generated_ids", "synthetic_reused_ids", "synthetic_rejection_reason",
                       "exam_validation", "route_confidence"})


def audit_metadata(event):
    return {key: value for key, value in event.items() if key in SAFE_KEYS}
