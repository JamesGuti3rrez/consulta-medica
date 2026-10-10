"""Construye un caso canónico (caso.schema.json) a partir de un candidato MedQA ya revisado.

La selección automática de la primera pasada (comando «transform») se retiró: sus 10 casos se
rechazaron en la revisión clínica y se conservan en data/cases/rejected/.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from server.cases.validator import validate_case_document

REPO_ROOT = Path(__file__).resolve().parents[3]
SPECIALTY_PREFIX = {
    "medicina_interna": "MED",
    "pediatria": "PED",
    "ginecologia_obstetricia": "GOB",
    "cirugia_general": "CIR",
    "emergencias": "EME",
}
# Tipo del evidence_id (CASO.tipo.nombre) según la categoría del dato.
EVIDENCE_TYPE = {
    "motivo": "motivo",
    "sintoma": "sintoma",
    "antecedente": "antecedente",
    "medicacion": "medicacion",
    "signo_vital": "vital",
    "anamnesis": "anamnesis",
    "examen_fisico": "examen",
    "laboratorio": "lab",
    "imagen": "imagen",
    "estudio": "estudio",
}
# Acción del estudiante que revela el dato, según su dueño (contrato de indexado del RAG, regla R14).
MODE_BY_OWNER = {
    "paciente": "al_preguntar",
    "medico_asistente": "al_examinar",
    "laboratorio": "al_solicitar_examen",
    "radiologia": "al_solicitar_examen",
}
SPECIALTY_LABEL = {
    "medicina_interna": "medicina interna",
    "pediatria": "pediatría",
    "ginecologia_obstetricia": "ginecología y obstetricia",
    "cirugia_general": "cirugía general",
    "emergencias": "emergencias",
}


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return " ".join(_as_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_as_text(v) for v in value.values())
    return str(value)


def _clean_question_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.replace("\u00a0", " ")
    return cleaned


def _extract_age(question: str) -> int | None:
    match = re.search(
        r"\b(\d{1,3})\s*(?:-\s*)?years?\s*-\s*old\b|\b(\d{1,3})\s+years?\s+old\b|\b(\d{1,3})\s*años\b",
        question,
        flags=re.IGNORECASE,
    )
    if match:
        age = next((group for group in match.groups() if group), None)
        return int(age) if age is not None and int(age) <= 120 else None
    return None


def _extract_sex(question: str) -> str | None:
    markers = {
        "femenino": re.compile(r"\b(woman|female|girl|she|her|mujer|niña|hembra)\b", re.IGNORECASE),
        "masculino": re.compile(r"\b(man|male|boy|he|him|his|hombre|niño|varón)\b", re.IGNORECASE),
    }
    first_match: tuple[int, str] | None = None
    for sex, pattern in markers.items():
        match = pattern.search(question)
        if match and (first_match is None or match.start() < first_match[0]):
            first_match = (match.start(), sex)
    return first_match[1] if first_match else None


def _question_as_title(question: str, specialty: str) -> str:
    age = _extract_age(question)
    age_suffix = f"de {age} años" if age is not None else "adulto"
    return f"Paciente {age_suffix} con cuadro de {SPECIALTY_LABEL[specialty]}"


def _evidence(case_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    item = {
        "evidence_id": f"{case_id}.{EVIDENCE_TYPE[entry['category']]}.{entry['key']}",
        "category": entry["category"],
        "label": entry["label"],
        "text": entry["text"],
    }
    if "interpretation" in entry:
        item["interpretation"] = entry["interpretation"]
    if "owner" in entry:
        item["reveal_policy"] = {
            "owner": entry["owner"],
            "mode": MODE_BY_OWNER[entry["owner"]],
            "requires": entry["requires"],
        }
    return item


def _build_case(candidate: dict[str, Any], index: int) -> dict[str, Any]:
    specialty = candidate.get("specialty", "medicina_interna")
    question = _clean_question_text(candidate.get("question", ""))
    options = candidate.get("options") or []
    answer = _as_text(candidate.get("answer"))
    case_prefix = SPECIALTY_PREFIX.get(specialty, "MED")
    case_id = _as_text(candidate.get("case_id")) or f"{case_prefix}-{index:03d}"
    age = _extract_age(question)
    sex = _extract_sex(question)
    if age is None or sex is None:
        raise ValueError(f"El caso {candidate.get('candidate_id')} no contiene edad y sexo inequívocos.")
    answer_index = ord(answer[0]) - ord("A") if len(answer) == 1 and answer.isalpha() else -1
    answer_text = _as_text(candidate.get("answer_text"))
    if not answer_text and 0 <= answer_index < len(options):
        answer_text = _as_text(options[answer_index])
    if not answer_text:
        raise ValueError(f"El caso {candidate.get('candidate_id')} no tiene una respuesta correcta recuperable.")

    title = _question_as_title(question, specialty)
    # Reparto de cada dato entre public y on_request (data/cases/reviews/medqa_lote_curacion.json).
    distribution = candidate.get("distribution")
    if not distribution:
        raise ValueError(f"El caso {case_id} no tiene reparto entre public y on_request.")
    chief_complaint_id = f"{case_id}.motivo.queja_principal"
    public_items = [_evidence(case_id, entry) for entry in distribution["public"]]
    on_request = [_evidence(case_id, entry) for entry in distribution["on_request"]]
    evidence_by_key = {entry["key"]: item["evidence_id"]
                       for entry, item in zip(distribution["on_request"], on_request)}
    # Los diferenciales pueden descartarse también con datos visibles desde el inicio.
    any_evidence_by_key = {
        "queja_principal": chief_complaint_id,
        **{entry["key"]: item["evidence_id"] for entry, item in zip(distribution["public"], public_items)},
        **evidence_by_key,
    }
    discard = distribution.get("discard", {})
    distractors = candidate.get("clinical_differentials") or [
        {"name": _as_text(option), "must_not_miss": False}
        for option_index, option in enumerate(options)
        if option_index != answer_index and _as_text(option) != answer_text
    ]
    normalized_differentials = [
        {"name": _as_text(item), "must_not_miss": False}
        if not isinstance(item, dict)
        else {
            "name": _as_text(item.get("name")),
            "must_not_miss": bool(item.get("must_not_miss", False)),
        }
        for item in distractors
    ]
    unknown = set(discard) - {item["name"] for item in normalized_differentials[:4]}
    if unknown:
        raise ValueError(f"El caso {case_id} descarta diferenciales que no tiene: {sorted(unknown)}")
    allergies = candidate.get("allergies") if distribution.get("allergies_in_public", True) else None
    treatment_reference = candidate.get("treatment_reference") or {
        "summary": (
            "La fuente MedQA no aporta un plan terapéutico validado para este paciente. "
            "No se deben inferir indicaciones de tratamiento a partir de esta ficha."
        ),
        "key_actions": [
            "Verificar la respuesta con la fuente original.",
            "Solicitar revisión clínica antes de uso asistencial o docente.",
        ],
    }

    kwargs = {
        "schema_version": "1.0.0",
        "case_id": case_id,
        "title": title,
        "specialty": specialty,
        "language": "es",
        "status": candidate.get("status", "validado"),
        "source": {
            "dataset": "MedQA",
            "item_id": candidate.get("candidate_id"),
            "license": "MIT",
            "method": "ia_validador",
        },
        "public": {
            "patient": {
                # Nombre ficticio del reparto; sin él, el número del caso (EME-001 → Paciente 1).
                "alias": distribution.get("alias") or f"Paciente {int(case_id[-3:])}",
                "age_years": age,
                "sex": sex,
            },
            "chief_complaint": {
                "evidence_id": chief_complaint_id,
                "category": "motivo",
                "label": "Motivo de consulta",
                "text": distribution["chief_complaint"],
            },
            "items": public_items,
            "allergies_recorded": bool(allergies),
            **({"allergies": allergies} if allergies else {}),
        },
        "on_request": on_request,
        "protected": {
            "diagnosis": {
                "name": _as_text(candidate.get("clinical_diagnosis")) or answer_text,
                "synonyms": [
                    _as_text(candidate.get("clinical_diagnosis")) or answer_text
                ],
            },
            "differentials": [
                {
                    "name": distractor["name"],
                    "must_not_miss": distractor["must_not_miss"],
                    "discard_evidence_ids": [any_evidence_by_key[key] for key in discard.get(distractor["name"], [])],
                }
                for distractor in normalized_differentials[:4]
            ] or [
                {
                    "name": "No hay opciones distractoras registradas en la fuente.",
                    "must_not_miss": False,
                    "discard_evidence_ids": [],
                }
            ],
            "treatment_reference": treatment_reference,
            "contraindications": [
                {
                    "id": item["id"],
                    "drug_or_class": item["drug_or_class"],
                    "reason": item["reason"],
                    "evidence_id": evidence_by_key[item["evidence"]],
                }
                for item in distribution.get("contraindications", [])
            ],
            "evaluation": {
                "key_questions": [
                    {
                        "id": "kq1",
                        "topic": (
                            f"Traducción al español: "
                            f"{_as_text(candidate.get('question_translation_es')) or question} "
                            f"Opciones traducidas: "
                            f"{'; '.join(candidate.get('options_translation_es', options))}. "
                            f"Respuesta fuente: {answer} — {answer_text}. "
                            f"Texto fuente conservado (inglés): {question} "
                            f"Opciones fuente: {'; '.join(options)}"
                        ),
                        "evidence_ids": [chief_complaint_id],
                        "weight": 3,
                        "critical": True,
                        "error_if_missing": "razonamiento_clinico",
                    },
                    *(
                        {
                            "id": f"kq{position}",
                            "topic": question["topic"],
                            "evidence_ids": [evidence_by_key[key] for key in question["evidence"]],
                            "weight": question["weight"],
                            "critical": question["critical"],
                            "error_if_missing": question["error_if_missing"],
                        }
                        for position, question in enumerate(distribution["key_questions"], start=2)
                    ),
                ],
                "tests": {
                    "recommended": candidate.get("recommended_tests", ["revision_fuente"]),
                    "optional": candidate.get("optional_tests", []),
                    "unnecessary": candidate.get("unnecessary_tests", []),
                },
            },
        },
        "provenance": {
            "created_by": "case_preparation.transform.medqa_case_builder",
            "created_at": date.today().isoformat(),
            "validator_version": "1.0.0",
            "validated_at": date.today().isoformat(),
            "curated_by": None,
            "curated_at": None,
            "rejection_reason": None,
        },
    }
    case = kwargs
    validate_case_document(case)
    return case
