r"""Lista las formas aceptadas de nombrar el diagnóstico de cada caso curado (protected.diagnosis.synonyms).

Uso, desde la raíz:  backend\.venv\Scripts\python.exe pruebas\20_sinonimos_diagnostico\mostrar_sinonimos.py
"""

import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
CURATED = Path(__file__).resolve().parents[2] / "data" / "cases" / "curated"

total = 0
for path in sorted(CURATED.glob("*.json")):
    case = json.loads(path.read_text(encoding="utf-8"))
    diagnosis = case["protected"]["diagnosis"]
    synonyms = [item for item in diagnosis["synonyms"] if item != diagnosis["name"]]
    total += len(diagnosis["synonyms"])
    print(f"{case['case_id']}  {diagnosis['name']}")
    print(f"         también: {'; '.join(synonyms)}")

# Antes de esta fase (commit 47ef69d), para comparar.
before = 0
for path in sorted(CURATED.glob("*.json")):
    old = subprocess.run(["git", "show", f"47ef69d:data/cases/curated/{path.name}"], capture_output=True,
                         text=True, encoding="utf-8", cwd=CURATED.parents[2], check=True).stdout
    before += len(json.loads(old)["protected"]["diagnosis"]["synonyms"])
print(f"\n{total} formas de nombrar el diagnóstico en 13 casos (antes: {before}; los 10 de MedQA solo tenían su nombre)")
