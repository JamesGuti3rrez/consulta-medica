from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from server.cases.validator import validate_case_document

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = REPO_ROOT / "data" / "interim" / "medqa_candidatos.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "cases" / "validated"
SPECIALTY_ORDER = [
    "medicina_interna",
    "pediatria",
    "ginecologia_obstetricia",
    "cirugia_general",
    "emergencias",
]
SPECIALTY_PREFIX = {
    "medicina_interna": "MED",
    "pediatria": "PED",
    "ginecologia_obstetricia": "GOB",
    "cirugia_general": "CIR",
    "emergencias": "EME",
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


def _score_candidate(record: dict[str, Any]) -> tuple[int, str]:
    question = _clean_question_text(record.get("question", ""))
    options = record.get("options") or []
    option_count = len(options) if isinstance(options, list) else 0
    answer = _as_text(record.get("answer"))
    has_valid_answer = bool(answer) and answer not in {"", "N/A", "nan"}
    age_bonus = 20 if _extract_age(question) is not None else 0
    length_bonus = len(question)
    option_bonus = option_count * 15
    return (length_bonus + option_bonus + age_bonus + (20 if has_valid_answer else 0), question.lower()),


def _load_candidates(input_path: Path | str) -> list[dict[str, Any]]:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de candidatos: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            record = json.loads(text)
            if isinstance(record, dict):
                records.append(record)
    return records


def _select_candidates(candidates: list[dict[str, Any]], count: int = 10) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {specialty: [] for specialty in SPECIALTY_ORDER}
    seen_questions: set[str] = set()
    for candidate in candidates:
        specialty = candidate.get("specialty")
        if specialty not in grouped:
            continue
        question = _clean_question_text(candidate.get("question", ""))
        normalized_question = question.casefold()
        if not question or normalized_question in seen_questions:
            continue
        if not candidate.get("options") or not candidate.get("answer"):
            continue
        if _extract_age(question) is None or _extract_sex(question) is None:
            continue
        seen_questions.add(normalized_question)
        grouped[specialty].append(candidate)

    selected: list[dict[str, Any]] = []
    for specialty in SPECIALTY_ORDER:
        items = sorted(grouped.get(specialty, []), key=lambda item: _score_candidate(item), reverse=True)
        selected.extend(items[:2])

    if len(selected) > count:
        selected = selected[:count]
    elif len(selected) < count:
        remaining = []
        for candidate in candidates:
            if any(candidate.get("candidate_id") == item.get("candidate_id") for item in selected):
                continue
            remaining.append(candidate)
        remaining = sorted(remaining, key=lambda item: _score_candidate(item), reverse=True)
        selected.extend(remaining[: count - len(selected)])

    return selected[:count]


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
    public_case_text = _as_text(candidate.get("clinical_summary_es")) or question
    chief_complaint = re.split(r"(?<=[.!?])\s+", public_case_text, maxsplit=1)[0]
    source_evidence_id = f"{case_id}.historia.fuente_medqa"
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
    allergies = candidate.get("allergies")
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
                "alias": f"Paciente {index}",
                "age_years": age if age is not None else 45,
                "sex": sex,
            },
            "chief_complaint": {
                "evidence_id": f"{case_id}.motivo.queja_principal",
                "category": "motivo",
                "label": "Queja principal",
                "text": chief_complaint,
            },
            "items": [
                {
                    "evidence_id": source_evidence_id,
                    "category": "anamnesis",
                    "label": "Resumen clínico (adaptado de MedQA)",
                    "text": public_case_text,
                }
            ],
            "allergies_recorded": bool(allergies),
            **({"allergies": allergies} if allergies else {}),
        },
        "on_request": [
            {
                "evidence_id": f"{case_id}.solicitud.exploracion_fisica",
                "category": "examen_fisico",
                "label": "Exploración física",
                "text": (
                    "Los hallazgos de exploración física descritos por la fuente ya están incluidos en la "
                    "historia pública; no se documentan otros hallazgos para revelar."
                ),
                "reveal_policy": {
                    "owner": "medico_asistente",
                    "mode": "al_preguntar",
                    "requires": ["exploracion_fisica"],
                },
            }
        ],
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
                    "discard_evidence_ids": [],
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
            "contraindications": [],
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
                        "evidence_ids": [source_evidence_id],
                        "weight": 3,
                        "critical": True,
                        "error_if_missing": "razonamiento_clinico",
                    }
                ],
                "tests": {
                    "recommended": candidate.get("recommended_tests", ["revision_fuente"]),
                    "optional": candidate.get("optional_tests", []),
                    "unnecessary": candidate.get("unnecessary_tests", []),
                },
            },
        },
        "provenance": {
            "created_by": "case_preparation.transform.medqa_selection",
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


def build_selected_cases(input_path: Path | str = DEFAULT_INPUT, output_dir: Path | str = DEFAULT_OUTPUT_DIR, count: int = 10) -> dict[str, Any]:
    candidates = _load_candidates(input_path)
    selected = _select_candidates(candidates, count=count)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    validated_cases: list[dict[str, Any]] = []
    for position, candidate in enumerate(selected, start=1):
        case = _build_case(candidate, position)
        filepath = output_root / f"{case['case_id']}.json"
        filepath.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        validated_cases.append(case)

    index_payload = {
        "dataset": "MedQA",
        "status": "validado",
        "source_path": str(Path(input_path)),
        "selected_case_ids": [case["case_id"] for case in validated_cases],
        "specialty_counts": dict(Counter(case["specialty"] for case in validated_cases)),
        "selected_count": len(validated_cases),
    }
    index_path = output_root / "medqa_selected_cases_index.json"
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_payload


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Selecciona 10 casos clínicos canónicos a partir de candidatos MedQA.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()

    summary = build_selected_cases(input_path=args.input, output_dir=args.output_dir, count=args.count)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
