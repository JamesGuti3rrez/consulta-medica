"""Selección explícita del almacén; un fallo de Supabase nunca usa casos locales."""

from .catalog import CURATED_CASES_DIR, load_curated_cases
from .repository import CanonicalCaseRepository
from .supabase import CaseStoreError, SupabaseCaseRepository
from ..config import settings


def build_case_repository(cases_dir=CURATED_CASES_DIR, *, config=None):
    config = config or settings
    if config.case_store == "supabase":
        return SupabaseCaseRepository(config.supabase_url, config.supabase_secret_key)
    if config.case_store == "local":
        return CanonicalCaseRepository(cases_dir)
    raise CaseStoreError("CASE_STORE debe ser local o supabase.")


def load_configured_cases():
    if settings.case_store == "local":
        return load_curated_cases()
    return build_case_repository().list_cases()
