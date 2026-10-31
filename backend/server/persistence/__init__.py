"""Acceso a Supabase: cuentas, intentos y diagnósticos finales."""

from .attempts import AttemptStoreError, SupabaseAttempts, build_attempt
from .diagnoses import (
    DiagnosisStoreError, DiagnosisTableMissing, FinalDiagnosisRecord, InMemoryDiagnoses, SupabaseDiagnoses,
)

__all__ = [
    "AttemptStoreError", "DiagnosisStoreError", "DiagnosisTableMissing", "FinalDiagnosisRecord", "InMemoryDiagnoses", "SupabaseAttempts",
    "SupabaseDiagnoses", "build_attempt",
]
