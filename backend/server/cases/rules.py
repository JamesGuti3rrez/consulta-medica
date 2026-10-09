"""Reglas que cruzan campos de un caso y que el JSON Schema no puede expresar.

Cada regla cita la especificación de la que sale. Se aplican después de validar el esquema.
"""

from __future__ import annotations

from typing import Any

# docs/decisions/0001 §3: prefijo de case_id por especialidad.
SPECIALTY_PREFIX = {
    "MED": "medicina_interna",
    "PED": "pediatria",
    "GOB": "ginecologia_obstetricia",
    "CIR": "cirugia_general",
    "EME": "emergencias",
}
# backend/case_preparation/sources/registry.py: licencia registrada de cada fuente.
SOURCE_LICENSE = {"MedQA": "MIT"}
PEDIATRIC_AGE_LIMIT = 18


def _evidence_items(case: dict[str, Any]) -> list[dict[str, Any]]:
    public = case["public"]
    return [public["chief_complaint"], *public["items"], *case["on_request"]]


def _diagnosis_terms(case: dict[str, Any]) -> list[str]:
    diagnosis = case["protected"]["diagnosis"]
    return [term for term in [diagnosis["name"], *diagnosis.get("synonyms", [])] if len(term) >= 4]


def check_case_rules(case: dict[str, Any]) -> list[str]:
    """Devuelve la lista de incumplimientos (vacía si el caso cumple todas las reglas)."""
    errors: list[str] = []
    case_id = case["case_id"]
    specialty = case["specialty"]
    patient = case["public"]["patient"]

    # R01 · 0001 §3: el prefijo identifica la especialidad.
    prefix = case_id.split("-", 1)[0]
    if SPECIALTY_PREFIX.get(prefix) != specialty:
        errors.append(f"R01 prefijo {prefix} no corresponde a la especialidad {specialty}")

    # R02 · esquema (evidence_id = CASO.tipo.nombre): únicos y del propio caso.
    evidence_ids = [item["evidence_id"] for item in _evidence_items(case)]
    duplicated = sorted({eid for eid in evidence_ids if evidence_ids.count(eid) > 1})
    if duplicated:
        errors.append(f"R02 evidence_id repetidos: {duplicated}")
    foreign = sorted(eid for eid in evidence_ids if not eid.startswith(f"{case_id}."))
    if foreign:
        errors.append(f"R02 evidence_id de otro caso: {foreign}")

    # R03 · la evaluación solo puede citar evidencia que existe en el caso.
    cited = {eid for question in case["protected"]["evaluation"]["key_questions"] for eid in question["evidence_ids"]}
    missing = sorted(cited - set(evidence_ids))
    if missing:
        errors.append(f"R03 key_questions citan evidencia inexistente: {missing}")

    # R04 · esquema («el título no debe revelar el diagnóstico») y separación public/protected.
    visible = " ".join(
        [case["title"], *(item.get("text", "") for item in _evidence_items(case)), *(item["label"] for item in _evidence_items(case))]
    ).casefold()
    revealed = [term for term in _diagnosis_terms(case) if term.casefold() in visible]
    if revealed:
        errors.append(f"R04 el diagnóstico aparece fuera de protected: {revealed}")

    # R05 · esquema (allergies_recorded): sin registro no hay lista; con registro, la lista no está vacía.
    allergies = case["public"].get("allergies")
    if case["public"]["allergies_recorded"] and not allergies:
        errors.append("R05 allergies_recorded es true pero no hay alergias")
    if not case["public"]["allergies_recorded"] and allergies:
        errors.append("R05 allergies_recorded es false pero hay alergias")

    # R06 · 0001 §4: menor de 18 años ⇔ pediatría; ginecología y obstetricia ⇒ paciente femenina.
    is_minor = patient["age_years"] < PEDIATRIC_AGE_LIMIT
    if is_minor != (specialty == "pediatria"):
        errors.append(f"R06 edad {patient['age_years']} incompatible con la especialidad {specialty}")
    if specialty == "ginecologia_obstetricia" and patient["sex"] != "femenino":
        errors.append("R06 caso de ginecología y obstetricia con paciente no femenina")

    # R07 · esquema (status) y data/README: la procedencia debe reflejar el estado.
    provenance = case["provenance"]
    if case["status"] == "curado" and not (provenance.get("curated_by") and provenance.get("curated_at")):
        errors.append("R07 caso curado sin curated_by o curated_at")
    if case["status"] == "rechazado" and not provenance.get("rejection_reason"):
        errors.append("R07 caso rechazado sin rejection_reason")
    if case["status"] != "rechazado" and provenance.get("rejection_reason"):
        errors.append("R07 rejection_reason en un caso no rechazado")

    # R08 · registry.py: la licencia del caso es la de su fuente.
    source = case["source"]
    expected_license = SOURCE_LICENSE.get(source["dataset"])
    if expected_license and source["license"] != expected_license:
        errors.append(f"R08 licencia {source['license']} distinta de la registrada ({expected_license})")

    return errors


def check_batch_rules(cases: list[dict[str, Any]]) -> list[str]:
    """Reglas entre casos de un mismo lote."""
    errors: list[str] = []
    # R09 · 0001 §2: cada caso sale de una sola pregunta; ninguna pregunta se usa dos veces.
    seen: dict[str, str] = {}
    for case in cases:
        key = f"{case['source']['dataset']}:{case['source']['item_id']}"
        if key in seen:
            errors.append(f"R09 {case['case_id']} reutiliza la pregunta fuente de {seen[key]}")
        seen[key] = case["case_id"]
    # R10 · data/README: IDs completos únicos.
    ids = [case["case_id"] for case in cases]
    duplicated = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicated:
        errors.append(f"R10 case_id repetidos: {duplicated}")
    return errors
