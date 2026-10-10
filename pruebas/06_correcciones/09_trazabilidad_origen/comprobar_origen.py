#!/usr/bin/env python3
"""Abre, dentro de data_clean.zip, el archivo y la línea registrados para cada caso y comprueba que
contienen el enunciado original que el caso conserva en protected.

Uso (desde la raíz del repositorio):
  backend/.venv/Scripts/python.exe pruebas/06_correcciones/09_trazabilidad_origen/comprobar_origen.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ZIP = REPO_ROOT / "data" / "raw" / "medqa" / "data_clean.zip"
SELECTION = REPO_ROOT / "data" / "cases" / "reviews" / "second_pass_selection.json"
CURATED = REPO_ROOT / "data" / "cases" / "curated"
MARKER = "Texto fuente conservado (inglés): "

archive = zipfile.ZipFile(ZIP)
failures = 0
for entry in json.loads(SELECTION.read_text(encoding="utf-8"))["cases"]:
    member = entry["source_file"].split(":", 1)[1]
    with archive.open(member) as handle:
        line = handle.read().decode("utf-8").splitlines()[entry["source_line"] - 1]
    question = json.loads(line)["question"]
    case = json.loads((CURATED / f"{entry['case_id']}.json").read_text(encoding="utf-8"))
    kept = case["protected"]["evaluation"]["key_questions"][0]["topic"].split(MARKER, 1)[1][:150]
    ok = kept in question
    failures += not ok
    print(f"[{'OK' if ok else 'FALLA'}] {entry['case_id']}  {member}  línea {entry['source_line']}")
    print(f"       {question[:110]}...")

print("\nRESULTADO: " + ("cada caso apunta a su pregunta original." if not failures else f"{failures} casos no coinciden."))
sys.exit(1 if failures else 0)
