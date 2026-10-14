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
# Se recorren los archivos de esa versión por su nombre de entonces (los códigos cambiaron en la fase 23).
git = dict(capture_output=True, text=True, encoding="utf-8", cwd=CURATED.parents[2], check=True)
names = subprocess.run(["git", "ls-tree", "--name-only", "47ef69d", "data/cases/curated/"], **git).stdout.split()
names = [name for name in names if name.endswith(".json")]
before = 0
for name in names:
    old = subprocess.run(["git", "show", f"47ef69d:{name}"], **git).stdout
    before += len(json.loads(old)["protected"]["diagnosis"]["synonyms"])
print(f"\n{total} formas de nombrar el diagnóstico en 13 casos (antes: {before}; los 10 de MedQA solo tenían su nombre)")
