from __future__ import annotations

import json
import zipfile

import pytest

from case_preparation.adapters import medqa
from case_preparation.adapters.medqa import (
    _classify_specialty,
    _parse_record,
    _question_type,
    extract_medqa_candidates,
)

# Viñetas de al menos 250 caracteres (SP-002: un caso necesita un enunciado largo).
PEDIATRIC_DX = (
    "A 17-year-old girl is brought to the emergency department with fever and acute abdominal pain that "
    "began around the umbilicus 18 hours ago and then moved to the right lower quadrant. She vomited twice "
    "and has no appetite. Her temperature is 38.4 C. Which of the following is the most likely diagnosis?"
)
ADULT_DX = (
    "A 48-year-old woman comes to the clinic because of a characteristic expanding rash on her thigh that "
    "appeared one week after a camping trip in a wooded area. She also reports fatigue, mild headache and "
    "joint pain. She does not remember any insect bite. What is the most likely diagnosis?"
)
ADULT_TX = (
    "A 60-year-old man is brought to the emergency department with hematemesis and shock after a large upper "
    "gastrointestinal bleed at home. He takes ibuprofen daily for knee pain. His pulse is 125/min and his "
    "blood pressure is 82/50 mm Hg. Which of the following is the best next step in management?"
)
IMAGE_DX = (
    "A 35-year-old man comes to the physician because of a painless skin lesion on his back that has grown "
    "over the last three months. His wife noticed that the border looks irregular. He works outdoors and "
    "rarely uses sunscreen. A photograph of the lesion is shown. Which of the following is the most likely diagnosis?"
)


def _record(identifier, question, answer="B"):
    return {
        "id": identifier,
        "question": question,
        "options": ["A. Option one", "B. Option two", "C. Option three", "D. Option four"],
        "answer": answer,
    }


def _write_jsonl(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def _read_candidates(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_extract_medqa_candidates_filters_patient_cases(tmp_path):
    raw_dir = tmp_path / "data" / "raw" / "medqa"
    _write_jsonl(
        raw_dir / "us_train.jsonl",
        [
            _record("US-001", PEDIATRIC_DX),
            _record("US-002", "Which vitamin is essential for blood clotting?"),
        ],
    )

    output_path = tmp_path / "data" / "interim" / "medqa_candidatos.jsonl"
    summary = extract_medqa_candidates(raw_root=raw_dir, output_path=output_path)

    assert summary["status"] == "ok"
    assert summary["candidates_kept"] == 1
    assert summary["rejected_by_reason"] == {"enunciado_corto": 1}
    assert summary["specialty_counts"]["pediatria"] == 1
    [candidate] = _read_candidates(output_path)
    assert candidate["candidate_id"] == "US-001"
    assert candidate["answer"] == "B"
    assert candidate["question_type"] == "diagnostico"
    assert candidate["source_file"] == "us_train.jsonl"
    assert candidate["source_line"] == 1


def test_parse_record_uses_answer_index_and_answer_text():
    candidate = _parse_record(
        {
            "id": "US-ANSWER-001",
            "question": ADULT_DX,
            "options": {"A": "Cellulitis", "B": "Lyme disease", "C": "Psoriasis", "D": "Contact dermatitis"},
            "answer": "Lyme disease",
            "answer_idx": "B",
        },
        1,
    )

    assert candidate is not None
    assert candidate["answer"] == "B"
    assert candidate["answer_text"] == "Lyme disease"
    assert candidate["specialty"] == "medicina_interna"


def test_generated_candidate_ids_are_content_stable():
    record = {
        "question": ADULT_DX,
        "options": ["Cellulitis", "Lyme disease", "Psoriasis", "Contact dermatitis"],
        "answer_idx": "B",
    }

    first = _parse_record(record, 1)
    second = _parse_record(record, 999)
    third = _parse_record({**record, "options": ["Cellulitis", "Lyme disease", "Psoriasis"]}, 1)

    assert first["candidate_id"] == second["candidate_id"]
    assert first["candidate_id"] != third["candidate_id"]


def test_specialty_classifier_does_not_match_laboratory_as_obstetrics():
    specialty, _ = _classify_specialty("A 59-year-old man has fever and dyspnea. Laboratory tests show leukocytosis.")
    assert specialty == "medicina_interna"


def test_question_type_requires_exactly_one_request():
    assert _question_type(ADULT_DX) == "diagnostico"
    assert _question_type(ADULT_TX) == "tratamiento"
    assert _question_type("Which antimicrobial drug did the physician prescribe") == "tratamiento"
    assert _question_type("Which of the following is the most likely diagnosis and the next best step?") is None
    assert _question_type("Which enzyme is most likely deficient?") is None


def test_extract_medqa_candidates_rejects_study_image_and_non_clinical_questions(tmp_path):
    raw_dir = tmp_path / "data" / "raw" / "medqa"
    study = (
        "Please refer to the summary above to answer this question. In the study, all participants who were "
        "enrolled and randomly assigned to treatment were analyzed regardless of adherence, and the authors "
        "report the hazard ratio for the primary outcome with its confidence interval at the end of follow-up."
    )
    _write_jsonl(
        raw_dir / "questions.jsonl",
        [_record("STUDY-001", study), _record("IMG-001", IMAGE_DX), _record("PAT-001", ADULT_TX, "A")],
    )

    output_path = tmp_path / "data" / "interim" / "medqa_candidatos.jsonl"
    summary = extract_medqa_candidates(raw_root=raw_dir, output_path=output_path)

    assert summary["rejected_by_reason"] == {"depende_de_imagen": 1, "investigacion": 1}
    [candidate] = _read_candidates(output_path)
    assert candidate["candidate_id"] == "PAT-001"
    assert candidate["question_type"] == "tratamiento"


def test_extract_medqa_candidates_skips_duplicates(tmp_path):
    raw_dir = tmp_path / "data" / "raw" / "medqa"
    _write_jsonl(raw_dir / "a.jsonl", [_record("DUP-001", ADULT_DX)])
    _write_jsonl(raw_dir / "b.jsonl", [_record("DUP-001", ADULT_DX)])

    output_path = tmp_path / "data" / "interim" / "medqa_candidatos.jsonl"
    summary = extract_medqa_candidates(raw_root=raw_dir, output_path=output_path)

    assert summary["candidates_kept"] == 1
    assert summary["duplicates_skipped"] == 1


def test_extract_medqa_candidates_handles_empty_source_dir(tmp_path):
    raw_dir = tmp_path / "data" / "raw" / "medqa"
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_path = tmp_path / "data" / "interim" / "medqa_candidatos.jsonl"

    summary = extract_medqa_candidates(raw_root=raw_dir, output_path=output_path)

    assert summary["status"] == "no_candidate_files_found"
    assert summary["candidates_kept"] == 0
    assert output_path.read_text(encoding="utf-8") == ""


def test_extract_reads_only_admitted_banks_inside_zip_without_writing_raw(tmp_path):
    raw_dir = tmp_path / "data" / "raw" / "medqa"
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "data_clean.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data_clean/questions/US/US_qbank.jsonl", json.dumps(_record("US-1", PEDIATRIC_DX)) + "\n")
        zf.writestr("data_clean/questions/US/train.jsonl", json.dumps(_record("US-1", PEDIATRIC_DX)) + "\n")
        zf.writestr("data_clean/questions/Mainland/train.jsonl", json.dumps(_record("CN-1", ADULT_DX)) + "\n")
        zf.writestr(
            "data_clean/questions/Taiwan/tw_translated_jsonl/en/dev-2en.jsonl",
            json.dumps(_record("TW-1", ADULT_TX)) + "\n",
        )
        zf.writestr("__MACOSX/data_clean/._x.jsonl", "basura")
    before = sorted(p.name for p in raw_dir.rglob("*"))

    output_path = tmp_path / "data" / "interim" / "medqa_candidatos.jsonl"
    summary = extract_medqa_candidates(raw_root=raw_dir, output_path=output_path)

    assert summary["files_scanned"] == [
        "data_clean.zip:data_clean/questions/Taiwan/tw_translated_jsonl/en/dev-2en.jsonl",
        "data_clean.zip:data_clean/questions/US/US_qbank.jsonl",
    ]
    assert sorted(c["candidate_id"] for c in _read_candidates(output_path)) == ["TW-1", "US-1"]
    assert sorted(p.name for p in raw_dir.rglob("*")) == before


def test_extract_rejects_registered_zip_with_unexpected_hash(tmp_path, monkeypatch):
    raw_dir = tmp_path / "medqa"
    raw_dir.mkdir()
    with zipfile.ZipFile(raw_dir / "data_clean.zip", "w") as zf:
        zf.writestr("data_clean/us.jsonl", json.dumps(_record("X-1", ADULT_DX)) + "\n")
    monkeypatch.setattr(medqa, "DATA_RAW_ROOT", raw_dir)

    with pytest.raises(ValueError, match="huella registrada"):
        extract_medqa_candidates(output_path=tmp_path / "out.jsonl")
