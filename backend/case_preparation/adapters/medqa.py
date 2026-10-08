from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_RAW_ROOT = REPO_ROOT / "data" / "raw" / "medqa"
DATA_INTERIM_ROOT = REPO_ROOT / "data" / "interim"

PATIENT_MARKERS = (
    "patient",
    "man",
    "woman",
    "boy",
    "girl",
    "child",
    "infant",
    "newborn",
    "teen",
    "pregnant",
    "pregnancy",
    "mother",
    "father",
    "adult",
    "elderly",
    "person",
)
CLINICAL_MARKERS = (
    "diagnosis",
    "most likely",
    "best next step",
    "treatment",
    "management",
    "symptom",
    "sign",
    "history",
    "exam",
    "lab",
    "imaging",
    "surgery",
    "operative",
    "acute",
)
STUDY_REJECTION_MARKERS = (
    "please refer to the summary above",
    "background:",
    "methods:",
    "randomly assigned",
    "participants were",
    "multicenter",
    "trial",
    "study design",
    "in the study",
    "abstract",
    "cohort",
    "randomization",
    "comparator group",
)


def _is_metadata_path(path: Path) -> bool:
    if "__MACOSX" in path.parts:
        return True
    name = path.name
    return name.startswith(".") and name != ".jsonl"


def _iter_jsonl_files(root: Path) -> list[Path]:
    if not root.exists():
        return []

    if root.is_file():
        root = root.parent

    candidates = []
    zip_files = sorted({p for p in root.rglob("*.zip") if p.is_file() and not _is_metadata_path(p)})
    for zip_path in zip_files:
        if zip_path.name in {"MedQA-master.zip", "source_manifest.json"}:
            continue
        try:
            with zipfile.ZipFile(zip_path) as archive:
                extracted_root = zip_path.with_suffix("")
                if not extracted_root.exists():
                    archive.extractall(path=root)
                candidates.extend(
                    sorted(
                        {
                            p for p in extracted_root.rglob("*.jsonl") if p.is_file() and not _is_metadata_path(p)
                        }
                    )
                )
        except (zipfile.BadZipFile, OSError, RuntimeError):
            continue

    jsonl_files = sorted({p for p in root.rglob("*.jsonl") if p.is_file() and not _is_metadata_path(p)})
    if jsonl_files:
        return jsonl_files

    excluded_names = {"source_manifest.json", "manifest.json", "medqa_candidatos_summary.json"}
    json_files = sorted(
        {
            p
            for p in root.rglob("*.json")
            if p.is_file() and p.name not in excluded_names and not _is_metadata_path(p)
        }
    )
    return list(json_files)


def _read_lines(path: Path) -> Iterable[str]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                text = line.strip()
                if text:
                    yield text
    except UnicodeDecodeError:
        return


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


def _merge_option_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        entries: list[str] = []
        for key in value:
            entry = value[key]
            if isinstance(entry, (list, tuple, dict)):
                entries.extend(_merge_option_values(entry))
            else:
                entries.append(_as_text(entry))
        return [item for item in entries if item]
    if isinstance(value, (list, tuple)):
        merged: list[str] = []
        for item in value:
            if isinstance(item, dict):
                merged.extend(_merge_option_values(item))
            else:
                text = _as_text(item)
                if text:
                    merged.append(text)
        return merged
    text = _as_text(value)
    return [text] if text else []


def _normalize_answer(value: Any, options: list[str] | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if isinstance(value, bool):
            return ""
        if value >= 0:
            return _letter_for_index(int(value))
        return ""
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"[A-Z]", text, flags=re.IGNORECASE):
            return text.upper()
        if re.fullmatch(r"\d+", text):
            return _letter_for_index(int(text))
        if options:
            normalized = text.casefold()
            for index, option in enumerate(options):
                if normalized == option.strip().casefold():
                    return _letter_for_index(index)
                if re.match(r"^[A-Z][.)]\s*", option, flags=re.IGNORECASE):
                    option_text = re.sub(r"^[A-Z][.)]\s*", "", option, flags=re.IGNORECASE)
                    if normalized == option_text.strip().casefold():
                        return _letter_for_index(index)
        return ""
    if isinstance(value, dict):
        for key in ("label", "answer", "key", "correct"):
            if key in value:
                return _normalize_answer(value[key], options)
        if "index" in value:
            return _normalize_answer(value["index"], options)
    return ""


def _letter_for_index(index: int) -> str:
    if index < 0:
        return ""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    letters: list[str] = []
    value = index
    while True:
        value, remainder = divmod(value, 26)
        letters.append(alphabet[remainder])
        if value == 0:
            break
        value -= 1
    return "".join(reversed(letters))


def _question_text(record: dict[str, Any]) -> str:
    for field in ("question", "prompt", "stem", "query", "text"):
        text = _as_text(record.get(field))
        if text:
            return text
    return ""


def _candidate_id(record: dict[str, Any], index: int) -> str:
    for field in ("id", "qid", "question_id", "uuid", "record_id"):
        value = record.get(field)
        if value is not None:
            return str(value)
    question = _question_text(record)
    if question:
        options = _extract_options(record)
        answer_key = ""
        for field in ("answer_idx", "correct_index", "answer_index", "correct_answer", "gold", "label", "answer"):
            answer_key = _normalize_answer(record.get(field), options)
            if answer_key:
                break
        identity = json.dumps(
            {
                "question": question.strip().casefold(),
                "options": [option.strip().casefold() for option in options],
                "answer": answer_key,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        return f"medqa-{digest}"
    return f"medqa-record-{index:05d}"


def _extract_options(record: dict[str, Any]) -> list[str]:
    for field in ("options", "choices", "answers", "answer_choices"):
        options = _merge_option_values(record.get(field))
        if options:
            return options
    if "options_dict" in record:
        return _merge_option_values(record["options_dict"])
    return []


def _contains_patient_context(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in PATIENT_MARKERS)


def _contains_clinical_context(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in CLINICAL_MARKERS)


def _classify_specialty(question_text: str) -> tuple[str, str]:
    lowered = question_text.lower()

    lower_age_match = re.search(
        r"\b(\d{1,3})\s*-\s*years?\s*-\s*old\b|\b(\d{1,3})\s+years?\s+old\b|\bage\s+(\d{1,3})\b",
        lowered,
    )
    if lower_age_match:
        age_value = next((group for group in lower_age_match.groups() if group), None)
        if age_value and int(age_value) < 18:
            return "pediatria", "edad menor de 18 años"

    if re.search(
        r"\b(pregnan\w*|gestation\w*|obstetric\w*|gynecolog\w*|uter\w*|ovarian\w*|fetal\w*|puerper\w*|postpartum|menstrual|vaginal)\b",
        lowered,
    ):
        return "ginecologia_obstetricia", "embarazo o patología ginecológica"

    if re.search(r"\b(child|infant|newborn|pediatric|adolescent|teenager|kid)\b", lowered):
        return "pediatria", "descripción pediátrica"

    if re.search(
        r"\b(appendicitis|appendectomy|hernia|cholecystitis|cholecystectomy|peritonitis|laparotomy|operative|postoperative|resection|gallbladder|bowel obstruction)\b",
        lowered,
    ):
        return "cirugia_general", "cuadro con manejo quirúrgico"

    if re.search(
        r"\b(emergency department|emergency room|trauma|shock|sepsis|cardiac arrest|respiratory distress|altered mental status|unconscious|hemorrhage|arrhythmia)\b",
        lowered,
    ):
        return "emergencias", "presentación aguda o urgente"

    return "medicina_interna", "cuadro clínico adulto general"


def _is_candidate_question(record: dict[str, Any], question: str, option_text: str) -> bool:
    if not question:
        return False
    if len(question) < 40:
        return False
    lowered = question.lower()
    if any(marker in lowered for marker in STUDY_REJECTION_MARKERS):
        return False
    if not _contains_patient_context(question):
        return False
    if not _contains_clinical_context(question + " " + option_text):
        return False
    return True


def _parse_record(record: dict[str, Any], index: int) -> dict[str, Any] | None:
    question = _question_text(record)
    options = _extract_options(record)
    option_text = " ".join(options)
    if not _is_candidate_question(record, question, option_text):
        return None

    answer = ""
    for field in ("answer_idx", "correct_index", "answer_index", "correct_answer", "gold", "label", "answer"):
        answer = _normalize_answer(record.get(field), options)
        if answer:
            break
    specialty, rule = _classify_specialty(question + " " + option_text)
    answer_index = ord(answer[0]) - ord("A") if len(answer) == 1 and answer.isalpha() else -1
    answer_text = options[answer_index] if 0 <= answer_index < len(options) else ""
    return {
        "candidate_id": _candidate_id(record, index),
        "source_dataset": "MedQA",
        "question": question,
        "options": options,
        "answer": answer,
        "answer_text": answer_text,
        "specialty": specialty,
        "classification_rule": rule,
    }


def extract_medqa_candidates(
    raw_root: Path | str | None = None,
    output_path: Path | str | None = None,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    raw_path = Path(raw_root) if raw_root is not None else DATA_RAW_ROOT
    destination = Path(output_path) if output_path is not None else DATA_INTERIM_ROOT / "medqa_candidatos.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)

    files = _iter_jsonl_files(raw_path)
    if not files:
        destination.write_text("", encoding="utf-8")
        summary = {
            "dataset": "MedQA",
            "status": "no_candidate_files_found",
            "raw_root": str(raw_path),
            "files_scanned": [],
            "records_scanned": 0,
            "candidates_kept": 0,
            "specialty_counts": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        summary_path = destination.with_name("medqa_candidatos_summary.json")
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    candidates: list[dict[str, Any]] = []
    records_scanned = 0
    for file_path in files:
        for line_number, line in enumerate(_read_lines(file_path), start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            records_scanned += 1
            candidate = _parse_record(record, len(candidates) + 1)
            if candidate is not None:
                candidates.append(candidate)
                if limit is not None and len(candidates) >= limit:
                    break
        if limit is not None and len(candidates) >= limit:
            break

    specialities = Counter(candidate["specialty"] for candidate in candidates)
    output_lines = [json.dumps(item, ensure_ascii=False) for item in candidates]
    destination.write_text("\n".join(output_lines) + ("\n" if output_lines else ""), encoding="utf-8")

    summary = {
        "dataset": "MedQA",
        "status": "ok",
        "raw_root": str(raw_path),
        "files_scanned": [
            str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)
            for path in files
        ],
        "records_scanned": records_scanned,
        "candidates_kept": len(candidates),
        "specialty_counts": dict(sorted(specialities.items())),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    summary_path = destination.with_name("medqa_candidatos_summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Extrae y filtra candidatos clínicos desde datos MedQA.")
    parser.add_argument("--dataset", choices=["medqa"], default="medqa")
    parser.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DATA_INTERIM_ROOT / "medqa_candidatos.jsonl")
    args = parser.parse_args()

    if args.dataset != "medqa":
        raise SystemExit("Solo está soportado el dataset medqa.")

    result = extract_medqa_candidates(raw_root=args.input_dir or DATA_RAW_ROOT, output_path=args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
