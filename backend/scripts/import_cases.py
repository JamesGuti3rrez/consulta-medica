"""Carga inicial, validada y repetible de los JSON curados en el nuevo Supabase."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from urllib.parse import urlsplit

# También funciona al ejecutarse directamente desde la raíz del repositorio.
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import set_key

from server.cases.catalog import CURATED_CASES_DIR, load_curated_cases
from server.cases.supabase import CaseStoreError, SupabaseCaseRepository
from server.config import ROOT_DIR, settings


def import_cases(repository, cases):
    """Solo inserta IDs ausentes; verifica que los documentos coinciden después."""
    repository.insert_missing(cases)
    remote = {case["case_id"]: case for case in repository.list_cases()}
    mismatches = [case["case_id"] for case in cases if remote.get(case["case_id"]) != case]
    if mismatches:
        raise CaseStoreError(
            "Estos casos no coinciden con el origen; no se sobrescribieron: "
            + ", ".join(mismatches)
        )
    return len(cases)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=CURATED_CASES_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Valida sin conectar ni escribir.")
    parser.add_argument("--activate", action="store_true", help="Activa CASE_STORE=supabase tras verificar.")
    args = parser.parse_args(argv)
    try:
        cases = load_curated_cases(args.directory)
        if not cases:
            raise ValueError("No hay casos curados para importar.")
        if len({case["case_id"] for case in cases}) != len(cases):
            raise ValueError("Hay identificadores de caso duplicados en el origen.")
        print(f"Casos curados validados: {len(cases)}", flush=True)
        if args.dry_run:
            print("Validación completa. No se modificó Supabase ni .env.")
            return 0
        print(f"Destino: {urlsplit(settings.supabase_url).hostname or '(sin configurar)'}", flush=True)
        repository = SupabaseCaseRepository(settings.supabase_url, settings.supabase_secret_key)
        count = import_cases(repository, cases)
        print(f"Carga verificada: {count} casos. No se sobrescribieron casos existentes.")
        if args.activate:
            set_key(str(ROOT_DIR / ".env"), "CASE_STORE", "supabase")
            print("CASE_STORE=supabase guardado en .env. Reinicia el servidor con npm start.")
        print("Los JSON quedan como material de migración. Los datos adicionales no se modificaron.")
        return 0
    except Exception as exc:
        # La representación de errores de validación puede contener datos protegidos.
        print(f"Importación detenida ({type(exc).__name__}). No se cambió CASE_STORE.", file=sys.stderr)
        if isinstance(exc, CaseStoreError):
            print(str(exc), file=sys.stderr)
        else:
            print("Comprueba los archivos, su esquema, las reglas y la configuración local.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
