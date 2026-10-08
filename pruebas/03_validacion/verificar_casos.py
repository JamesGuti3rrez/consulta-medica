#!/usr/bin/env python3
"""Verificación de la fase 3: esquema, lote curado y vista pública del estudiante.

Uso (desde la raíz del repositorio):
  backend/.venv/Scripts/python.exe pruebas/03_validacion/verificar_casos.py

Termina con código 0 solo si todas las comprobaciones pasan.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from jsonschema import Draft202012Validator  # noqa: E402

from server.cases.catalog import CURATED_CASES_DIR, load_curated_cases, to_student_case  # noqa: E402
from server.cases.validator import load_schema  # noqa: E402

CASES_ROOT = REPO_ROOT / "data" / "cases"
FOLDERS = ("curated", "validated_second_pass", "rejected")
STUDENT_KEYS = {"case_id", "specialty", "patient", "chief_complaint", "items", "allergies_recorded", "allergies"}

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    print(f"  [{'OK' if condition else 'FALLA'}] {message}")
    if not condition:
        failures.append(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def protected_texts(case: dict) -> list[str]:
    protected = case["protected"]
    texts = [protected["diagnosis"]["name"], *protected["diagnosis"].get("synonyms", [])]
    texts += [item["name"] for item in protected.get("differentials", [])]
    treatment = protected.get("treatment_reference", {})
    texts += [treatment.get("summary", ""), *treatment.get("key_actions", [])]
    return [text for text in texts if text and len(text) >= 4]


print("1. Validación contra schemas/caso.schema.json")
validator = Draft202012Validator(load_schema())
for folder in FOLDERS:
    files = sorted((CASES_ROOT / folder).glob("*.json"))
    statuses = Counter()
    invalid = []
    for path in files:
        case = load(path)
        errors = list(validator.iter_errors(case))
        if errors:
            invalid.append(f"{path.name}: {errors[0].message}")
        statuses[case.get("status")] += 1
    check(not invalid, f"{folder}/: {len(files)} archivos válidos, estados {dict(statuses)}")
    for message in invalid:
        print(f"      {message}")

print("\n2. Lote curado (data/cases/curated/)")
curated = {path.stem: load(path) for path in sorted(CURATED_CASES_DIR.glob("*.json"))}
check(len(curated) == 10, f"hay {len(curated)} casos curados (se esperan 10)")
check(all(case["status"] == "curado" for case in curated.values()), "todos tienen status = curado")
check(all(case["case_id"] == stem for stem, case in curated.items()), "el nombre de archivo coincide con case_id")
suffixes = sorted(int(re.fullmatch(r"[A-Z]{3}-(\d{3})", case_id).group(1)) for case_id in curated)
check(suffixes == list(range(1, 11)), f"sufijos de ID 001–010 sin huecos ni repetidos: {suffixes}")
ordered = sorted(curated, key=lambda case_id: case_id[-3:])
print(f"      orden por posición: {', '.join(ordered)}")
specialties = Counter(case["specialty"] for case in curated.values())
check(set(specialties.values()) == {2}, f"2 casos por especialidad: {dict(specialties)}")
check(all(case["source"]["dataset"] == "MedQA" for case in curated.values()), "fuente MedQA en todos")
check(
    all(case["provenance"].get("curated_by") for case in curated.values()),
    "procedencia de curación registrada (provenance.curated_by)",
)
rejected_ids = {path.stem for path in (CASES_ROOT / "rejected").glob("*.json")}
check(not (rejected_ids & set(curated)), f"ningún ID rechazado está en curated/ ({len(rejected_ids)} rechazados)")

print("\n3. Catálogo que sirve la API (server/cases/catalog.py)")
api_cases = load_curated_cases()
api_ids = sorted(case["case_id"] for case in api_cases)
check(api_ids == sorted(curated), f"la API expone exactamente los {len(api_ids)} casos curados")
check(CURATED_CASES_DIR == CASES_ROOT / "curated", f"la API lee solo {CURATED_CASES_DIR.relative_to(REPO_ROOT)}")

print("\n4. Vista del estudiante (to_student_case) sin información protegida")
for case in api_cases:
    student = to_student_case(case)
    serialized = json.dumps(student, ensure_ascii=False).casefold()
    extra_keys = set(student) - STUDENT_KEYS
    leaks = [text for text in protected_texts(case) if text.casefold() in serialized]
    hidden = [key for key in ("protected", "on_request", "source", "provenance") if f'"{key}"' in serialized]
    check(
        not extra_keys and not leaks and not hidden,
        f"{case['case_id']}: campos {sorted(student)}; diagnóstico protegido «{case['protected']['diagnosis']['name']}» no aparece",
    )
    for text in leaks:
        print(f"      texto protegido visible: {text!r}")

print()
if failures:
    print(f"RESULTADO: {len(failures)} comprobaciones fallaron.")
    sys.exit(1)
print("RESULTADO: todas las comprobaciones pasaron.")
