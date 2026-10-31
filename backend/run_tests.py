"""Ejecuta pytest con temporales nuevos y sin telemetría externa.

Desde backend/: python run_tests.py tests/rag/ -q
Los argumentos adicionales se reenvían a pytest sin pasar por un shell.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    backend = Path(__file__).resolve().parent
    # Crear directamente bajo backend/ evita padres heredados de ejecuciones con
    # otro usuario/contexto de permisos, tanto en %TEMP% como en .pytest_cache.
    run_dir = Path(tempfile.mkdtemp(prefix=".pytest_run-", dir=backend))
    environment = os.environ.copy()
    for name in ("LANGSMITH_TRACING", "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2"):
        environment[name] = "false"
    environment["RAGAS_DO_NOT_TRACK"] = "true"
    command = [sys.executable, "-m", "pytest", "--basetemp", str(run_dir / "tmp"),
               "-o", f"cache_dir={run_dir / 'cache'}", *sys.argv[1:]]
    print(f"Temporales y caché de esta ejecución: {run_dir}", flush=True)
    return subprocess.run(command, cwd=backend, env=environment, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
