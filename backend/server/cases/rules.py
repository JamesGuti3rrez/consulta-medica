"""Reglas que cruzan campos de un caso y que el JSON Schema no puede expresar.

Cada regla cita la especificación de la que sale. Se aplican después de validar el esquema.
"""

from __future__ import annotations

import re
import unicodedata
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

# SP-002 C.4: el validador revisa que no quede texto de la pregunta de opción múltiple, que las
# opciones incorrectas no salgan de protected, que no haya cifras que no estén en la fuente y que
# la presentación inicial no traiga laboratorio ni examen físico.
SOURCE_MARKER = "Texto fuente conservado (inglés): "
MCQ_LEFTOVER = re.compile(
    r"cu[aá]l de (?:los|las) siguientes|which of the following|pregunta fuente|opciones? (?:correcta|fuente)"
    r"|respuesta correcta",
    re.IGNORECASE,
)
EXAM_OR_LAB = re.compile(
    r"\b(?:laboratorio|hemograma|leucocitos|hemoglobina|plaquetas|creatinina|glucosa|sodio|potasio|troponina"
    r"|orina|cultivo|biopsia|radiograf\w+|tomograf\w+|ecograf\w+|resonancia|electrocardiograma|ecg"
    r"|exploraci[oó]n|examen f[ií]sico|auscultaci[oó]n|palpaci[oó]n|crepitantes|soplo"
    r"|tiempo de (?:tromboplastina|protrombina)|ph vaginal)\b",
    re.IGNORECASE,
)
# Contrato de revelación del indexado del RAG (rama feature/rag-light-rag-sprint1,
# case_preparation/indexing/documents.py): qué temas puede revelar cada dueño y con qué acción.
PATIENT_REQUIRES = frozenset({
    "inicio_y_evolucion", "caracteristicas_sintoma", "sintomas_asociados", "antecedentes_personales",
    "antecedentes_familiares", "medicacion", "alergias", "habitos", "antecedentes_gineco_obstetricos",
})
ASSISTANT_REQUIRES = frozenset({"signos_vitales", "exploracion_fisica"})
MODE_BY_OWNER = {
    "paciente": "al_preguntar",
    "medico_asistente": "al_examinar",
    "laboratorio": "al_solicitar_examen",
    "radiologia": "al_solicitar_examen",
}
NUMBER = re.compile(r"\d*[.,]?\d+")
# La fuente a veces escribe las cifras con letras («Thirty minutes»): cuentan como la cifra.
NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50", "sixty": "60", "half": "0.5",
}


def evidence_text(item: dict[str, Any]) -> str:
    """Texto de un dato. El esquema admite `value` y `unit` en lugar de `text` (por ejemplo, un signo vital)."""
    if "text" in item:
        return item["text"]
    return f"{item['value']} {item['unit']}"


def _evidence_items(case: dict[str, Any]) -> list[dict[str, Any]]:
    public = case["public"]
    return [public["chief_complaint"], *public["items"], *case["on_request"]]


def _diagnosis_terms(case: dict[str, Any]) -> list[str]:
    diagnosis = case["protected"]["diagnosis"]
    return [term for term in [diagnosis["name"], *diagnosis.get("synonyms", [])] if len(term) >= 4]


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _numbers(text: str) -> set[str]:
    values = set()
    for raw in NUMBER.findall(text):
        value = raw.replace(",", ".")
        if value.startswith("."):
            value = "0" + value
        values.add(value)
    return values


def _source_text(case: dict[str, Any]) -> str | None:
    """Enunciado original en inglés que el caso conserva en protected, si lo tiene."""
    for question in case["protected"]["evaluation"]["key_questions"]:
        if SOURCE_MARKER in question["topic"]:
            return question["topic"].split(SOURCE_MARKER, 1)[1]
    return None


def _visible_text(case: dict[str, Any]) -> str:
    """Texto de las zonas 1 y 2: lo que puede llegar al estudiante o a los agentes."""
    items = _evidence_items(case)
    return " ".join([case["title"], *(item.get("text", "") for item in items), *(item["label"] for item in items)])


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

    # R11 · SP-002 (riesgo R1): las opciones incorrectas y los diferenciales nunca salen de protected.
    visible = _normalize(_visible_text(case))
    exposed = [d["name"] for d in case["protected"]["differentials"] if len(d["name"]) >= 4 and _normalize(d["name"]) in visible]
    if exposed:
        errors.append(f"R11 diferenciales visibles fuera de protected: {exposed}")

    # R12 · SP-002 (regla 4 del prompt): no queda texto de la pregunta de opción múltiple.
    leftovers = sorted({match.group(0) for match in MCQ_LEFTOVER.finditer(_visible_text(case))})
    if leftovers:
        errors.append(f"R12 texto de la pregunta de opción múltiple: {leftovers}")

    # R13 · SP-002 (regla 3): no hay cifras que no estén en el enunciado original.
    source = _source_text(case)
    if source is not None:
        source_numbers = _numbers(source) | {
            value for word, value in NUMBER_WORDS.items() if re.search(rf"\b{word}\b", source, re.IGNORECASE)
        }
        invented = sorted(_numbers(_visible_text(case)) - source_numbers - _numbers(case["case_id"]))
        if invented:
            errors.append(f"R13 cifras que no están en la fuente: {invented}")

    # R14 · contrato de revelación del RAG: cada dato bajo solicitud tiene el modo de su dueño, y el
    # paciente y el médico asistente solo usan los temas acordados.
    for item in case["on_request"]:
        policy = item["reveal_policy"]
        owner, mode, requires = policy["owner"], policy["mode"], set(policy["requires"])
        expected_mode = MODE_BY_OWNER.get(owner)
        if expected_mode and mode != expected_mode:
            errors.append(f"R14 {item['evidence_id']}: {owner} revela con {expected_mode}, no con {mode}")
        allowed = {"paciente": PATIENT_REQUIRES, "medico_asistente": ASSISTANT_REQUIRES}.get(owner)
        if allowed is not None and not requires <= allowed:
            errors.append(f"R14 {item['evidence_id']}: temas no acordados para {owner}: {sorted(requires - allowed)}")

    return errors


def check_case_warnings(case: dict[str, Any]) -> list[str]:
    """Avisos que no bloquean el caso; se informan hasta que se corrijan."""
    warnings: list[str] = []
    # W01 · SP-002 (regla 2) y arquitectura §6.1: laboratorio, imágenes y examen físico van en
    # on_request. No bloquea mientras los casos no se redistribuyan entre public y on_request.
    public = case["public"]
    public_text = " ".join(evidence_text(item) for item in [public["chief_complaint"], *public["items"]])
    found = sorted({match.group(0).lower() for match in EXAM_OR_LAB.finditer(public_text)})
    if found:
        warnings.append(f"W01 laboratorio o examen físico en public: {found}")
    return warnings


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
