#!/usr/bin/env python3
"""Ejecuta la extracción de MedQA y comprueba que data/raw/ queda exactamente igual.

Uso (desde la raíz del repositorio):
  backend/.venv/Scripts/python.exe pruebas/06_correcciones/02_extractor/comprobar_raw_intacto.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW = REPO_ROOT / "data" / "raw"
SUMMARY = REPO_ROOT / "data" / "interim" / "medqa_candidatos_summary.json"


def snapshot() -> dict[str, tuple[int, int]]:
    return {
        str(path.relative_to(RAW)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(RAW.rglob("*"))
        if path.is_file()
    }


before = snapshot()
print(f"data/raw antes:   {len(before)} archivos")
result = subprocess.run(
    [sys.executable, "-m", "case_preparation", "adapters", "extract", "--dataset", "medqa"],
    cwd=REPO_ROOT / "backend",
    capture_output=True,
    text=True,
    encoding="utf-8",
)
after = snapshot()
print(f"data/raw después: {len(after)} archivos")
changed = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
print(f"archivos creados, modificados o borrados en data/raw: {len(changed)}")
for name in changed[:10]:
    print(f"  {name}")

summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
print(f"\nExtracción (código {result.returncode}):")
for key in ("files_scanned", "records_scanned", "rejected_by_reason", "duplicates_skipped", "candidates_kept",
            "question_type_counts", "specialty_counts"):
    print(f"  {key}: {json.dumps(summary[key], ensure_ascii=False)}")

ok = result.returncode == 0 and not changed and summary["duplicates_skipped"] == 0
print("\nRESULTADO: " + ("data/raw intacto y candidatos sin duplicados." if ok else "FALLA"))
sys.exit(0 if ok else 1)
