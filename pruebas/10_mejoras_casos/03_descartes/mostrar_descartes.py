"""Diagnósticos diferenciales de cada caso curado y los datos que los descartan o los hacen menos probables.

Uso (desde la raíz del repositorio):
  backend/.venv/Scripts/python.exe pruebas/10_mejoras_casos/03_descartes/mostrar_descartes.py
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
CURATED = Path(__file__).resolve().parents[3] / "data" / "cases" / "curated"
linked = total = 0
for path in sorted(CURATED.glob("*.json"), key=lambda p: int(p.stem[-3:])):
    case = json.loads(path.read_text(encoding="utf-8"))
    labels = {item["evidence_id"]: item["label"] for item in
              [case["public"]["chief_complaint"], *case["public"]["items"], *case["on_request"]]}
    print(f"\n{case['case_id']}")
    for differential in case["protected"]["differentials"]:
        total += 1
        data = [labels[eid] for eid in differential["discard_evidence_ids"]]
        linked += bool(data)
        print(f"  {differential['name']:<58} {' + '.join(data) if data else '(sin dato que lo descarte)'}")
print(f"\n{linked} de {total} diferenciales vinculados con datos del caso.")
