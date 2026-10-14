r"""Numeración de los casos agrupada por especialidad (fase 23).

Antes, Pediatría quedaba en 007 y 010 con Medicina interna (008 y 009) en medio. Se renombran 3 casos:

    MED-008 (Patricia Vargas, Lyme)        -> MED-007
    MED-009 (Alberto Núñez, basocelular)   -> MED-008
    PED-007 (Mateo Quispe, Perthes)        -> PED-009

Así quedan EME 001-002, GOB 003-004, CIR 005-006, MED 007-008 y PED 009-010 (los sintéticos siguen en
101-103), y el sufijo vuelve a ser la posición del caso en el lote. No choca con los casos rechazados, que
usan otros prefijos para esos números (CIR-007, CIR-008, EME-009, EME-010).

Como MED-008 pasa a ser otro caso, el reemplazo usa marcadores intermedios. Solo toca los archivos actuales:
la evidencia de fases anteriores (.txt, .json y README de pruebas/) conserva los códigos de su momento.

Uso, desde la raíz (una sola vez; volver a correrlo no cambia nada):
    backend\.venv\Scripts\python.exe pruebas\23_numeracion_casos\renumerar_casos.py
Después: python -m case_preparation curation (desde backend/) regenera los casos con los códigos nuevos.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")

RENAMES = {"MED-008": "MED-007", "MED-009": "MED-008", "PED-007": "PED-009"}

# Archivos vigentes que nombran los casos (datos de entrada, código, pruebas, documentación y scripts).
FILES = [
    "data/cases/reviews/medqa_lote_curacion.json",
    "backend/server/ai/agents/base.py",
    "backend/tests/test_case_catalog_api.py",
    "backend/tests/test_case_rules.py",
    "backend/tests/test_case_transform.py",
    "backend/tests/test_quality_gates.py",
    "backend/tests/unit/test_disclosure.py",
    "backend/tests/unit/test_safety.py",
    "docs/decisions/0002-complementos-del-equipo.md",
    "docs/pipelines/traspaso-flujo-de-datos.md",
    "pruebas/07_integracion_sma_rag/06_orquestador/consulta_simulada.py",
    "pruebas/11_sesiones_supabase/01_almacen_real/probar_supabase.py",
    "pruebas/13_guiones_por_paciente/guiones.py",
    "pruebas/15_integracion_motor_clinico/probar_evaluacion.cjs",
    "pruebas/16_historial_simulaciones/probar_historial.cjs",
    "pruebas/17_otro_caso/probar_otro_caso.cjs",
    "pruebas/18_casos_con_un_solo_diagnostico/completar_casos.py",
    "pruebas/18_casos_con_un_solo_diagnostico/probar_indice_viejo.py",
    "pruebas/18_casos_con_un_solo_diagnostico/probar_vercel.py",
    "pruebas/_herramientas/capturar_frontend.cjs",
]


def renamed(text: str) -> str:
    for index, old in enumerate(RENAMES):
        text = text.replace(old, f"@@CASO{index}@@")
    for index, new in enumerate(RENAMES.values()):
        text = text.replace(f"@@CASO{index}@@", new)
    return text


def number(case_id: str) -> int:
    return int(case_id.rsplit("-", 1)[1])


def reorder_review() -> None:
    """El lote y sus secciones por caso quedan en el orden de su número."""
    path = ROOT / "data" / "cases" / "reviews" / "medqa_lote_curacion.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["selected_cases"].sort(key=lambda item: number(item["case_id"]))
    for section in ("clinical_review", "clinical_overrides", "distribution"):
        data[section] = dict(sorted(data[section].items(), key=lambda item: number(item[0])))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def move_case_files() -> None:
    """git mv conserva el historial de cada archivo; pasa por nombres temporales para no pisar MED-008."""
    for folder in ("curated", "validated"):
        base = ROOT / "data" / "cases" / folder
        pending = [(old, new) for old, new in RENAMES.items() if (base / f"{old}.json").exists()]
        for old, _ in pending:
            subprocess.run(["git", "mv", f"{old}.json", f"{old}.tmp.json"], cwd=base, check=True)
        for old, new in pending:
            subprocess.run(["git", "mv", f"{old}.tmp.json", f"{new}.json"], cwd=base, check=True)
        print(f"data/cases/{folder}: {', '.join(f'{old} -> {new}' for old, new in pending) or 'sin cambios'}")


if __name__ == "__main__":
    if (ROOT / "data" / "cases" / "curated" / "PED-009.json").exists():
        print("Ya está renumerado: no se hace nada.")
        raise SystemExit(0)
    for relative in FILES:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        new_text = renamed(text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            print(f"actualizado: {relative}")
    reorder_review()
    move_case_files()
    print("\nRenumeración aplicada:", ", ".join(f"{old} -> {new}" for old, new in RENAMES.items()))
