import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

def load_case(case_id: str = "case_001") -> dict[str, Any]:
    path = ROOT / "data" / "cases" / f"{case_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))

def load_questions() -> list[dict[str, Any]]:
    path = ROOT / "data" / "questions" / "questions.json"
    return json.loads(path.read_text(encoding="utf-8"))

def evidence_map(case: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}

    def walk(obj):
        if isinstance(obj, dict):
            if "evidence_id" in obj:
                eid = str(obj["evidence_id"])
                if "text" in obj:
                    out[eid] = str(obj["text"])
                elif "finding" in obj:
                    out[eid] = str(obj["finding"])
                elif "value" in obj:
                    out[eid] = f'{obj["value"]} {obj.get("unit","")}'.strip()
                else:
                    out[eid] = json.dumps(obj, ensure_ascii=False)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(case)
    return out
