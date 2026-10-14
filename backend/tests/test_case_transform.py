from __future__ import annotations

from case_preparation.transform.medqa_case_builder import _build_case
from case_preparation.transform.medqa_final_review import (
    CLINICAL_REVIEW,
    SPANISH_SOURCE_TEXT,
    SELECTED_CASES,
    curate_reviewed_case,
)
from server.cases.validator import validate_case_document

DISTRIBUTION = {
    "chief_complaint": "Fiebre y dolor abdominal.",
    "public": [{"key": "signos_vitales", "category": "signo_vital", "label": "Signos vitales", "text": "Fiebre."}],
    "on_request": [
        {"key": "dolor", "category": "sintoma", "label": "Dolor", "text": "Dolor abdominal.",
         "owner": "paciente", "requires": ["caracteristicas_sintoma"]},
        {"key": "exploracion_fisica", "category": "examen_fisico", "label": "Exploración física",
         "text": "Abdomen doloroso.", "owner": "medico_asistente", "requires": ["exploracion_fisica"]},
    ],
    "key_questions": [
        {"topic": "Exploración abdominal", "evidence": ["exploracion_fisica"], "weight": 5, "critical": True,
         "error_if_missing": "razonamiento_clinico"},
    ],
}


def test_build_case_validates_against_schema():
    candidate = {
        "candidate_id": "medqa-09999",
        "question": "A 16-year-old girl presents with fever and abdominal pain. Which of the following is the most likely diagnosis?",
        "options": ["A. Appendicitis", "B. Pneumonia", "C. Migraine", "D. Anxiety"],
        "answer": "A",
        "specialty": "pediatria",
        "question_translation_es": "Niña de 16 años con fiebre y dolor abdominal: ¿cuál es el diagnóstico más probable?",
        "options_translation_es": ["Apendicitis", "Neumonía", "Migraña", "Ansiedad"],
        "distribution": DISTRIBUTION,
    }

    case = _build_case(candidate, 1)
    validate_case_document(case)
    assert case["case_id"] == "PED-001"
    assert case["public"]["patient"]["age_years"] == 16
    assert case["public"]["patient"]["sex"] == "femenino"
    assert case["public"]["chief_complaint"]["text"] == "Fiebre y dolor abdominal."
    assert case["public"]["items"][0]["evidence_id"] == "PED-001.vital.signos_vitales"
    policies = {item["evidence_id"]: item["reveal_policy"] for item in case["on_request"]}
    assert policies["PED-001.sintoma.dolor"]["mode"] == "al_preguntar"
    assert policies["PED-001.examen.exploracion_fisica"]["mode"] == "al_examinar"
    assert case["protected"]["evaluation"]["key_questions"][1]["evidence_ids"] == ["PED-001.examen.exploracion_fisica"]
    assert case["protected"]["diagnosis"]["name"] == "A. Appendicitis"
    topic = case["protected"]["evaluation"]["key_questions"][0]["topic"]
    assert topic.startswith("Traducción al español:")
    assert "Niña de 16 años con fiebre y dolor abdominal" in topic
    assert candidate["question"] in topic
    assert case["source"]["method"] == "ia_validador"


def test_build_case_requires_source_demographics():
    candidate = {
        "candidate_id": "medqa-00001",
        "question": "A patient presents with fever and abdominal pain. Which is the most likely diagnosis?",
        "options": ["A. Appendicitis", "B. Pneumonia"],
        "answer": "A",
        "specialty": "medicina_interna",
    }

    try:
        _build_case(candidate, 1)
    except ValueError as error:
        assert "edad y sexo inequívocos" in str(error)
    else:
        raise AssertionError("Se esperaba rechazar un caso sin edad y sexo de origen.")


def test_build_case_requires_distribution():
    candidate = {
        "candidate_id": "medqa-00004",
        "question": "A 30-year-old man presents with fever. Which is the most likely diagnosis?",
        "options": ["A. Influenza", "B. Pneumonia"],
        "answer": "A",
        "specialty": "medicina_interna",
    }
    try:
        _build_case(candidate, 1)
    except ValueError as error:
        assert "reparto" in str(error)
    else:
        raise AssertionError("Se esperaba rechazar un caso sin edad y sexo de origen.")


def test_final_review_batch_uses_supported_postoperative_and_emergency_cases():
    by_case_id = {case["case_id"]: case for case in SELECTED_CASES}

    assert len(SELECTED_CASES) == 10
    assert len({case["candidate_id"] for case in SELECTED_CASES}) == 10
    assert by_case_id["CIR-006"]["candidate_id"] == "medqa-e9b7102d702a0a7f"
    assert by_case_id["CIR-006"]["clinical_diagnosis"] == "Sepsis posoperatoria"
    assert by_case_id["EME-002"]["candidate_id"] == "medqa-83b0322c93dff066"
    assert by_case_id["EME-002"]["clinical_diagnosis"] == "Hemorragia subaracnoidea"
    assert by_case_id["PED-010"]["candidate_id"] == "medqa-5fc375051c4a68f2"
    assert by_case_id["PED-010"]["clinical_diagnosis"] == "Síndrome de McCune-Albright"
    assert all("delirium tremens" not in case["clinical_diagnosis"].lower() for case in SELECTED_CASES)
    assert CLINICAL_REVIEW["PED-010"]["disposition"] == "coherente_con_precauciones"
    assert len(SPANISH_SOURCE_TEXT) == 10
    case_ids = [case["case_id"] for case in SELECTED_CASES]
    assert len(set(case_ids)) == 10
    assert sorted(int(case_id.rsplit("-", 1)[1]) for case_id in case_ids) == list(range(1, 11))
    specialty_prefixes = {
        "medicina_interna": "MED",
        "pediatria": "PED",
        "ginecologia_obstetricia": "GOB",
        "cirugia_general": "CIR",
        "emergencias": "EME",
    }
    assert all(
        case_id.startswith(f"{specialty_prefixes[case['specialty']]}-")
        for case_id, case in zip(case_ids, SELECTED_CASES)
    )
    assert sorted(
        case_ids,
        key=lambda case_id: int(case_id.rsplit("-", 1)[1]),
    ) == [
        "EME-001",
        "EME-002",
        "GOB-003",
        "GOB-004",
        "CIR-005",
        "CIR-006",
        "PED-007",
        "MED-008",
        "MED-009",
        "PED-010",
    ]
    assert "tiempo de tromboplastina parcial prolongado" in SPANISH_SOURCE_TEXT["medqa-4135d59786b5b7ac"]["question"]
    assert "frecuencia respiratoria de 20/min" in SPANISH_SOURCE_TEXT["medqa-83b0322c93dff066"]["question"]


def test_build_case_preserves_differential_risk_and_reviewed_test_recommendations():
    candidate = {
        "candidate_id": "medqa-00002",
        "question": "A 57-year-old man presents with a sudden severe headache. Which is the most likely diagnosis?",
        "options": ["A. Migraine", "B. Subarachnoid hemorrhage"],
        "answer": "B",
        "answer_text": "Subarachnoid hemorrhage",
        "specialty": "emergencias",
        "clinical_diagnosis": "Hemorragia subaracnoidea",
        "clinical_differentials": [
            {"name": "Meningitis", "must_not_miss": True},
            {"name": "Migraña", "must_not_miss": False},
        ],
        "recommended_tests": ["tc_craneal_sin_contraste_urgente"],
        "optional_tests": ["puncion_lumbar_si_persiste_sospecha"],
        "distribution": DISTRIBUTION,
    }

    case = _build_case(candidate, 1)

    assert case["protected"]["differentials"][0]["must_not_miss"] is True
    assert case["protected"]["evaluation"]["tests"]["recommended"] == [
        "tc_craneal_sin_contraste_urgente"
    ]
    assert case["protected"]["evaluation"]["tests"]["optional"] == [
        "puncion_lumbar_si_persiste_sospecha"
    ]
    assert case["protected"]["differentials"][0]["discard_evidence_ids"] == []


def test_curation_changes_only_status_and_curation_provenance():
    candidate = {
        "candidate_id": "medqa-00003",
        "question": "A 57-year-old man presents with a sudden severe headache. Which is the most likely diagnosis?",
        "options": ["A. Migraine", "B. Subarachnoid hemorrhage"],
        "answer": "B",
        "answer_text": "Subarachnoid hemorrhage",
        "specialty": "emergencias",
        "clinical_diagnosis": "Hemorragia subaracnoidea",
        # Un caso curado necesita un dato que descarte cada diferencial (R15, decisión 0002).
        "distribution": {**DISTRIBUTION, "discard": {"A. Migraine": ["exploracion_fisica"]}},
    }
    case = _build_case(candidate, 1)
    original_public = case["public"].copy()
    original_protected = case["protected"].copy()
    original_source = case["source"].copy()
    original_provenance = case["provenance"].copy()

    curated = curate_reviewed_case(
        case,
        {
            "assessment": "Compatible con el cuadro descrito; requiere confirmación por imagen.",
            "disposition": "compatible_urgencia_critica_requiere_confirmacion",
        },
    )

    assert curated["status"] == "curado"
    assert curated["provenance"]["curated_by"] == "case_preparation.curation"
    assert curated["provenance"]["curated_at"]
    assert curated["public"] == original_public
    assert curated["protected"] == original_protected
    assert curated["source"] == original_source
    assert curated["provenance"]["created_by"] == original_provenance["created_by"]
    assert curated["provenance"]["created_at"] == original_provenance["created_at"]
    assert curated["provenance"]["validated_at"] == original_provenance["validated_at"]


def test_team_complements_must_cite_a_registered_clinical_source():
    # Decisión 0002: cada dato agregado por el equipo cita una fuente de clinical_sources.
    import pytest

    from case_preparation.transform.medqa_final_review import check_complements

    sources = {"cdc_hemophilia": {"title": "CDC", "url": "https://www.cdc.gov/hemophilia/"}}
    complement = {"key": "factores", "complemento": {"fuente": "cdc_hemophilia", "motivo": "Descarta hemofilia B."}}
    check_complements("CIR-005", {"public": [], "on_request": [complement]}, sources)

    unknown = {"key": "factores", "complemento": {"fuente": "fuente_inventada", "motivo": "x"}}
    with pytest.raises(ValueError, match="fuente_inventada"):
        check_complements("CIR-005", {"public": [], "on_request": [unknown]}, sources)
    without_reason = {"key": "factores", "complemento": {"fuente": "cdc_hemophilia"}}
    with pytest.raises(ValueError, match="motivo"):
        check_complements("CIR-005", {"public": [], "on_request": [without_reason]}, sources)


def test_build_case_adds_reviewed_diagnosis_synonyms_after_the_name():
    candidate = {
        "candidate_id": "medqa-00004",
        "question": "A 57-year-old man presents with a sudden severe headache. Which is the most likely diagnosis?",
        "options": ["A. Migraine", "B. Subarachnoid hemorrhage"],
        "answer": "B",
        "answer_text": "Subarachnoid hemorrhage",
        "specialty": "emergencias",
        "clinical_diagnosis": "Hemorragia subaracnoidea",
        "diagnosis_synonyms": ["HSA", "Hemorragia subaracnoidea", "Sangrado subaracnoideo"],
        "distribution": DISTRIBUTION,
    }
    diagnosis = _build_case(candidate, 1)["protected"]["diagnosis"]
    assert diagnosis["synonyms"] == ["Hemorragia subaracnoidea", "HSA", "Sangrado subaracnoideo"]
