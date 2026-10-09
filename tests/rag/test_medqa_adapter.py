from __future__ import annotations

import json
import zipfile

from case_preparation.adapters.medqa import _classify_specialty, _parse_record, extract_medqa_candidates


def _write_jsonl(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def test_extract_medqa_candidates_filters_patient_cases(tmp_path):
    raw_dir = tmp_path / "data" / "raw" / "medqa"
    _write_jsonl(
        raw_dir / "us_train.jsonl",
        [
            {
                "id": "US-001",
                "question": "A 17-year-old girl presents with fever and acute abdominal pain. Which of the following is the most likely diagnosis?",
                "options": [
                    "A. Appendicitis",
                    "B. Pneumonia",
                    "C. Migraine",
                    "D. Anxiety",
                ],
                "answer": 1,
            },
            {
                "id": "US-002",
                "question": "Which vitamin is essential for blood clotting?",
                "options": ["A. Vitamin A", "B. Vitamin K", "C. Vitamin C", "D. Vitamin B12"],
                "answer": "B",
            },
        ],
    )

    output_path = tmp_path / "data" / "interim" / "medqa_candidatos.jsonl"
    summary = extract_medqa_candidates(raw_root=raw_dir, output_path=output_path)

    assert summary["status"] == "ok"
    assert summary["candidates_kept"] == 1
    assert summary["specialty_counts"]["pediatria"] == 1
    candidates = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert candidates[0]["candidate_id"] == "US-001"
    assert candidates[0]["answer"] == "B"
    assert candidates[0]["specialty"] == "pediatria"


def test_parse_record_uses_answer_index_and_answer_text():
    candidate = _parse_record(
        {
            "id": "US-ANSWER-001",
            "question": "A 48-year-old woman presents with a characteristic expanding rash. What is the most likely diagnosis?",
            "options": {
                "A": "Cellulitis",
                "B": "Lyme disease",
                "C": "Psoriasis",
                "D": "Contact dermatitis",
            },
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
        "question": "A 48-year-old woman presents with a characteristic expanding rash. What is the most likely diagnosis?",
        "options": ["Cellulitis", "Lyme disease", "Psoriasis", "Contact dermatitis"],
        "answer_idx": "B",
    }

    first = _parse_record(record, 1)
    second = _parse_record(record, 999)
    alternate_options = {**record, "options": ["Cellulitis", "Lyme disease", "Psoriasis"]}
    third = _parse_record(alternate_options, 1)

    assert first is not None
    assert second is not None
    assert third is not None
    assert first["candidate_id"] == second["candidate_id"]
    assert first["candidate_id"] != third["candidate_id"]


def test_specialty_classifier_does_not_match_laboratory_as_obstetrics():
    specialty, _ = _classify_specialty(
        "A 59-year-old man has fever and dyspnea. Laboratory tests show leukocytosis."
    )
    assert specialty == "medicina_interna"


def test_extract_medqa_candidates_rejects_study_abstract_questions(tmp_path):
    raw_dir = tmp_path / "data" / "raw" / "medqa"
    _write_jsonl(
        raw_dir / "study_questions.jsonl",
        [
            {
                "id": "STUDY-001",
                "question": "Please refer to the summary above to answer this question In the study, all participants who were enrolled and randomly assigned to treatment were analyzed regardless of adherence.",
                "options": ["A. Yes", "B. No", "C. Maybe", "D. Not sure"],
                "answer": "A",
            },
            {
                "id": "PAT-001",
                "question": "A 60-year-old man presents with hematemesis and shock after a large upper GI bleed. Which of the following is the best next step?",
                "options": ["A. Administer IV fluids", "B. Observe", "C. Start aspirin", "D. Discharge"],
                "answer": "A",
            },
        ],
    )

    output_path = tmp_path / "data" / "interim" / "medqa_candidatos.jsonl"
    summary = extract_medqa_candidates(raw_root=raw_dir, output_path=output_path)

    assert summary["status"] == "ok"
    assert summary["candidates_kept"] == 1
    assert sum(summary["specialty_counts"].values()) == 1
    candidates = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert candidates[0]["candidate_id"] == "PAT-001"


def test_extract_medqa_candidates_handles_empty_source_dir(tmp_path):
    raw_dir = tmp_path / "data" / "raw" / "medqa"
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_path = tmp_path / "data" / "interim" / "medqa_candidatos.jsonl"

    summary = extract_medqa_candidates(raw_root=raw_dir, output_path=output_path)

    assert summary["status"] == "no_candidate_files_found"
    assert summary["candidates_kept"] == 0
    assert output_path.read_text(encoding="utf-8") == ""


def test_extract_medqa_candidates_reads_jsonl_from_zip(tmp_path):
    raw_dir = tmp_path / "data" / "raw" / "medqa"
    raw_dir.mkdir(parents=True, exist_ok=True)

    records = [
        {
            "id": "ZIP-001",
            "question": "A 12-year-old boy presents with fever and cough. Which is the most likely diagnosis?",
            "options": ["A. Asthma", "B. Pneumonia", "C. Fracture", "D. Migraine"],
            "answer": 1,
        }
    ]
    zip_path = raw_dir / "data_clean.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data_clean/us.jsonl", "\n".join(json.dumps(item) for item in records) + "\n")

    output_path = tmp_path / "data" / "interim" / "medqa_candidatos.jsonl"
    summary = extract_medqa_candidates(raw_root=raw_dir, output_path=output_path)

    assert summary["status"] == "ok"
    assert summary["candidates_kept"] == 1
    assert summary["specialty_counts"]["pediatria"] == 1
