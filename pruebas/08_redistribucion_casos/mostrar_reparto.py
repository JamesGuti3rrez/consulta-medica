"""Muestra el reparto de los 10 casos curados: qué ve el estudiante al inicio y qué se revela a petición.

Uso (desde la raíz del repositorio):
  backend/.venv/Scripts/python.exe pruebas/08_redistribucion_casos/mostrar_reparto.py
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
CURATED = Path(__file__).resolve().parents[2] / "data" / "cases" / "curated"

totals = {"public": 0, "on_request": 0, "key_questions": 0}
for path in sorted(CURATED.glob("*.json"), key=lambda p: int(p.stem[-3:])):
    case = json.loads(path.read_text(encoding="utf-8"))
    public = case["public"]
    print(f"\n=== {case['case_id']} · {public['patient']['alias']}, {public['patient']['age_years']} años")
    print(f"  INICIO    motivo: {public['chief_complaint']['text']}")
    for item in public["items"]:
        print(f"            {item['label']}: {item['text']}")
    print(f"            alergias registradas: {public['allergies_recorded']}")
    for item in case["on_request"]:
        policy = item["reveal_policy"]
        print(f"  A PEDIDO  [{policy['owner']} · {policy['mode']} · {', '.join(policy['requires'])}] {item['label']}")
    questions = case["protected"]["evaluation"]["key_questions"]
    print(f"  EVALUA    {len(questions)} preguntas clave: " + "; ".join(q["id"] for q in questions))
    totals["public"] += 1 + len(public["items"])
    totals["on_request"] += len(case["on_request"])
    totals["key_questions"] += len(questions)

print(f"\nTOTAL: {totals['public']} datos visibles al inicio, {totals['on_request']} datos a petición, "
      f"{totals['key_questions']} preguntas clave en 10 casos.")
