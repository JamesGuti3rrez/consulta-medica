"""Genera la ampliación de 30 casos sintéticos sin sobrescribir casos distintos."""
from __future__ import annotations

import json
from pathlib import Path

from server.cases.rules import check_batch_rules, check_case_rules, check_case_warnings
from server.cases.validator import validate_case_document

ROOT = Path(__file__).resolve().parents[3]
CURATED = ROOT / "data/cases/curated"
MANIFEST = ROOT / "data/cases/familias/ampliacion_2026_10_16.json"
DATE = "2026-10-16"

# Campo del diseño, tipo del identificador, categoría y tema del contrato de revelación.
HISTORY = (
    ("course", "inicio_evolucion", "anamnesis", "anamnesis", "Inicio y evolución", "inicio_y_evolucion"),
    ("features", "caracteristicas", "anamnesis", "anamnesis", "Características de las molestias", "caracteristicas_sintoma"),
    ("symptoms", "sintomas", "sintoma", "sintoma", "Síntomas asociados", "sintomas_asociados"),
    ("history", "antecedentes", "antecedente", "antecedente", "Antecedentes personales", "antecedentes_personales"),
    ("medication", "medicacion", "medicacion", "medicacion", "Medicación habitual", "medicacion"),
    ("allergies", "alergias", "antecedente", "antecedente", "Alergias", "alergias"),
    ("habits", "habitos", "anamnesis", "anamnesis", "Hábitos y entorno", "habitos"),
    ("function", "impacto_funcional", "anamnesis", "anamnesis", "Impacto en las actividades diarias", "habitos"),
    ("gynecology", "historia_ginecologica", "antecedente", "antecedente", "Historia ginecológica y obstétrica", "antecedentes_gineco_obstetricos"),
)


def load_design() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def build_case(family: dict, spec: dict) -> dict:
    case_id = spec["id"]
    items, ids = [], {}

    def add(key, kind, category, label, text, owner, mode, requirement):
        evidence_id = f"{case_id}.{kind}.{key}"
        ids[key] = evidence_id
        items.append({
            "evidence_id": evidence_id, "category": category, "label": label, "text": text,
            "reveal_policy": {"owner": owner, "mode": mode, "requires": [requirement]},
        })

    for field, key, kind, category, label, topic in HISTORY:
        text = spec.get(field, "No refiere alergias conocidas." if field == "allergies" else None)
        if text:
            add(key, kind, category, label, text, "paciente", "al_preguntar", topic)
    add("signos_vitales", "vital", "signo_vital", "Signos vitales", spec["vitals"],
        "medico_asistente", "al_examinar", "signos_vitales")
    add("exploracion_fisica", "examen", "examen_fisico", "Exploración física", spec["exam"],
        "medico_asistente", "al_examinar", "exploracion_fisica")
    for study in spec["studies"]:
        imaging = study["owner"] == "radiologia"
        add(study["key"], "imagen" if imaging else "lab", "imagen" if imaging else "laboratorio",
            study["label"], study["text"], study["owner"], "al_solicitar_examen", study["key"])

    questions = [
        ("Inicio y evolución de las molestias", ["inicio_evolucion"], 4, "anamnesis_incompleta"),
        ("Características y síntomas asociados", ["caracteristicas", "sintomas"], 4, "anamnesis_incompleta"),
        ("Antecedentes y medicación habitual", ["antecedentes", "medicacion"], 3, "anamnesis_incompleta"),
        ("Alergias antes de proponer tratamiento", ["alergias"], 3, "negligencia"),
        ("Valoración de gravedad con signos vitales y exploración", ["signos_vitales", "exploracion_fisica"], 5, "negligencia"),
        ("Datos que permiten distinguir los diagnósticos de la familia", spec["decisive"], 5, "razonamiento_clinico"),
    ]
    if spec.get("gynecology"):
        questions.append(("Historia ginecológica y obstétrica", ["historia_ginecologica"], 4, "anamnesis_incompleta"))
    context = "Acude acompañado por su madre a valoración pediátrica." if family["specialty"] == "pediatria" else "Acude a valoración médica por estas molestias."
    complaint = family["complaint"]
    return {
        "schema_version": "1.1.0", "case_id": case_id,
        "title": f"{spec['name']}: {complaint[:48].rstrip(' .')}",
        "specialty": family["specialty"], "language": "es", "status": "curado",
        "source": {"dataset": "sintetico", "item_id": f"{family['id']}/{spec['slug']}",
                   "license": "CC BY 4.0", "method": "generado_ia"},
        "public": {
            "patient": {"alias": spec["name"], "age_years": spec["age"], "sex": spec["sex"]},
            "chief_complaint": {"evidence_id": f"{case_id}.motivo.queja_principal", "category": "motivo",
                                "label": "Motivo de consulta", "text": complaint},
            "items": [{"evidence_id": f"{case_id}.anamnesis.contexto_atencion", "category": "anamnesis",
                       "label": "Contexto de atención", "text": context}],
            "allergies_recorded": False,
        },
        "on_request": items,
        "protected": {
            "diagnosis": {"name": spec["diagnosis"], "synonyms": spec["synonyms"]},
            "differentials": [
                {"name": other["diagnosis"], "must_not_miss": other["urgent"],
                 "discard_evidence_ids": [ids[key] for key in spec["decisive"]]}
                for other in family["cases"] if other["id"] != case_id
            ],
            "treatment_reference": {"summary": spec["treatment"], "key_actions": spec["actions"]},
            "contraindications": [],
            "evaluation": {
                "key_questions": [
                    {"id": f"kq{i}", "topic": topic, "evidence_ids": [ids[key] for key in keys],
                     "weight": weight, "critical": weight >= 4, "error_if_missing": error}
                    for i, (topic, keys, weight, error) in enumerate(questions, start=1)
                ],
                "tests": {
                    "recommended": spec.get("recommended", [s["key"] for s in spec["studies"]] or ["signos_vitales", "exploracion_fisica"]),
                    "optional": spec.get("optional", []), "unnecessary": spec.get("unnecessary", []),
                },
            },
        },
        "provenance": {
            "created_by": "Codex / case_preparation.familias.ampliacion", "created_at": DATE,
            "validator_version": "1.1.0", "validated_at": DATE,
            "curated_by": "Validación automática para simulación; revisión clínica humana pendiente",
            "curated_at": DATE, "rejection_reason": None,
        },
    }


def build_cases() -> list[dict]:
    return [build_case(family, spec) for family in load_design() for spec in family["cases"]]


def main() -> int:
    cases = build_cases()
    existing = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in CURATED.glob("*.json")}
    errors = []
    for case in cases:
        validate_case_document(case)
        errors += [f"{case['case_id']}: {error}" for error in check_case_rules(case) + check_case_warnings(case)]
        previous = existing.get(case["case_id"])
        if previous is not None and previous != case:
            errors.append(f"{case['case_id']}: ya existe con contenido distinto; no se sobrescribe.")
    combined = {**existing, **{case["case_id"]: case for case in cases}}
    errors += check_batch_rules(list(combined.values()))
    if errors:
        for error in errors:
            print(error)
        return 1
    CURATED.mkdir(parents=True, exist_ok=True)
    for case in cases:
        path = CURATED / f"{case['case_id']}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path.relative_to(ROOT))
    print(f"{len(cases)} casos sintéticos; catálogo total: {len(combined)}. Revisión clínica pendiente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

