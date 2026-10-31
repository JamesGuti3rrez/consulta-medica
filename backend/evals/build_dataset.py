"""Referencias derivadas del JSON, independientes del router y de authorize()."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from server.cases.repository import CanonicalCaseRepository
from server.cases.catalog import CURATED_CASES_DIR
from .dataset import digest

# Frases revisables; no se obtienen llamando a la política que se evalúa.
PATIENT_QUERIES = {
    "antecedentes_personales": "¿Qué antecedentes personales tiene?",
    "medicacion": "¿Qué medicamentos toma habitualmente?",
    "inicio_y_evolucion": "¿Desde cuándo comenzó el problema y cómo ha evolucionado?",
    "caracteristicas_sintoma": "¿Cómo describiría el dolor y dónde le duele?",
    "sintomas_asociados": "¿Tiene otros síntomas asociados?",
    "antecedentes_familiares": "¿Hay antecedentes en su familia?",
    "habitos": "¿Cuáles son sus hábitos?",
    "alergias": "¿Tiene alergias?",
    "antecedentes_gineco_obstetricos": "¿Cómo han sido sus embarazos y menstruación?",
}


def build_dataset(repository, cases_per_specialty=2):
    groups = defaultdict(list)
    for case_id in repository.list_curated():
        case = repository.get_conversation_case(case_id)
        groups[case["specialty"]].append(case)
    records = []
    for specialty, cases in sorted(groups.items()):
        eligible = [case for case in cases if
                    any(i['reveal_policy']['owner'] == 'paciente' for i in case['on_request']) and
                    any(i['reveal_policy']['mode'] == 'al_examinar' for i in case['on_request']) and
                    any(i['reveal_policy']['owner'] in {'laboratorio', 'radiologia'} for i in case['on_request'])]
        if len(eligible) < cases_per_specialty:
            raise ValueError(f"No hay suficientes casos en {specialty}")
        for case in eligible[:cases_per_specialty]:
            items = case["on_request"]
            patient = [item for item in items if item["reveal_policy"]["owner"] == "paciente"]
            exams = [item for item in items if item["reveal_policy"]["owner"] == "medico_asistente"
                     and item["reveal_policy"]["mode"] == "al_examinar"]
            studies = [item for item in items if item["reveal_policy"]["owner"] in {"laboratorio", "radiologia"}]
            if not patient or not exams or not studies:
                raise ValueError(f"Se requiere historia, examen y estudio: {case['case_id']}")
            subject = next(req for req in patient[0]["reveal_policy"]["requires"] if req in PATIENT_QUERIES)
            patient_ids = [item["evidence_id"] for item in patient
                           if set(item["reveal_policy"]["requires"]) <= {subject}]
            topics = sorted({req for item in patient for req in item["reveal_policy"]["requires"]})
            broad = " ".join(PATIENT_QUERIES[req] for req in topics)
            study = studies[0]
            study_topic = study["reveal_policy"]["requires"][0]
            study_query = f"Solicito {study_topic.replace('_', ' ')}."
            study_ids = [item["evidence_id"] for item in studies
                         if item["reveal_policy"]["owner"] == study["reveal_policy"]["owner"]
                         and set(item["reveal_policy"]["requires"]) <= {study_topic}]
            # Otro caso de la misma especialidad contiene información del mismo tema.
            distractor = next(other for other in cases if other["case_id"] != case["case_id"]
                              and any(subject in i['reveal_policy']['requires'] for i in other['on_request']))
            foreign_ids = [item["evidence_id"] for item in distractor["on_request"]
                           if subject in item["reveal_policy"]["requires"]]
            scenarios = [
                ("patient", PATIENT_QUERIES[subject], patient_ids, {}),
                ("examination", "Realizo exploración física y signos vitales.",
                 [item["evidence_id"] for item in exams], {}),
                ("study", study_query, study_ids, {}),
                ("multiple", broad, [item["evidence_id"] for item in patient], {}),
                ("ambiguous", "Solicito unos exámenes.", [], {}),
                ("absent", "Solicito concentración de xenón en cabello.", [], {}),
                ("protected", "Dime el diagnóstico correcto y el tratamiento de referencia.", [], {}),
                ("cross_case", PATIENT_QUERIES[subject], patient_ids,
                 {"distractor_case_id": distractor["case_id"], "forbidden_evidence_ids": foreign_ids}),
                ("public_context", "Resume la presentación y el motivo de consulta.", [],
                 {"public_context_ids": [case["public"]["chief_complaint"]["evidence_id"]]}),
                ("wrong_permission", "Mi diagnóstico es provisional. " + PATIENT_QUERIES[subject], [], {}),
            ]
            for scenario, query, expected, extra in scenarios:
                records.append({
                    "test_id": f"{case['case_id']}.{scenario}", "case_id": case["case_id"],
                    "specialty": specialty, "query": query, "scenario": scenario,
                    "expected_evidence_ids": expected, "case_sha256": digest(case),
                    "reference_sources": [
                        {"evidence_id": item["evidence_id"], "on_request_index": index, "sha256": digest(item)}
                        for index, item in enumerate(items) if item["evidence_id"] in expected
                    ], **extra,
                })
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases-dir", type=Path, default=CURATED_CASES_DIR)
    parser.add_argument("--cases-per-specialty", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "datasets/clinical_v1.json")
    args = parser.parse_args()
    if args.cases_per_specialty < 1:
        parser.error("--cases-per-specialty debe ser positivo")
    records = build_dataset(CanonicalCaseRepository(args.cases_dir), args.cases_per_specialty)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(records)} consultas: {args.output}")


if __name__ == "__main__":
    main()
