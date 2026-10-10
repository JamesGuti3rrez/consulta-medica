"""Nombre, edad y sexo de cada paciente del lote curado (lo que muestra la ficha).

Uso (desde la raíz del repositorio):
  backend/.venv/Scripts/python.exe pruebas/10_mejoras_casos/01_nombres/mostrar_nombres.py
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
CURATED = Path(__file__).resolve().parents[3] / "data" / "cases" / "curated"
for path in sorted(CURATED.glob("*.json"), key=lambda p: int(p.stem[-3:])):
    patient = json.loads(path.read_text(encoding="utf-8"))["public"]["patient"]
    print(f"{path.stem}  {patient['alias']:<18} {patient['age_years']:>3} años  {patient['sex']}")
