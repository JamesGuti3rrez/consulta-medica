"""HU-006: el reporte de cada uno de los 43 casos curados usa solo datos de su propio caso (CA3, CA4)."""
import json
import re
from pathlib import Path

import pytest

from server.engine.disclosure.policy import DisclosurePolicy
from server.engine.evaluation.report import build_report

CURATED = Path(__file__).resolve().parents[3] / "data" / "cases" / "curated"
CASES = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in sorted(CURATED.glob("*.json"))}
EVIDENCE_ID = re.compile(r"\b[A-Z]{3}-\d{3}\.[a-z_]+\.[a-z0-9_]+")
NAMES = {case_id: {case["protected"]["diagnosis"]["name"], *(d["name"] for d in case["protected"]["differentials"])}
         for case_id, case in CASES.items()}


def _report(case: dict, all_evidence: bool) -> dict:
    initial = DisclosurePolicy.initial_evidence_ids(case)
    requested = [item["evidence_id"] for item in case["on_request"]] if all_evidence else []
    session = {"case_id": case["case_id"], "phase": "finalizada", "finished_at": "2026-10-28T10:00:00+00:00",
               "revealed_evidence_ids": [*initial, *requested], "requested_evidence_ids": requested,
               "student_diagnosis": "Propuesta", "student_hypotheses": []}
    return build_report(session, case, [])


def fuentes_ajenas(case_id: str, report: dict) -> list[str]:
    """Ids de evidencia de otro caso y nombres de diagnósticos o diferenciales de otro caso que no estén en este."""
    text = json.dumps(report, ensure_ascii=False)
    own = json.dumps(CASES[case_id], ensure_ascii=False) if case_id in CASES else ""
    ajenos = [eid for eid in EVIDENCE_ID.findall(text) if not eid.startswith(case_id + ".")]
    for other_id, names in NAMES.items():
        if other_id != case_id:
            ajenos += [name for name in names if name in text and name not in own]
    return sorted(set(ajenos))


def test_hay_43_casos_curados():
    assert len(CASES) == 43


@pytest.mark.parametrize("all_evidence", [True, False], ids=["toda_la_evidencia", "sin_evidencia"])
@pytest.mark.parametrize("case_id", sorted(CASES))
def test_reporte_solo_con_datos_del_caso(case_id, all_evidence):
    case = CASES[case_id]
    report = _report(case, all_evidence)
    assert report["case_id"] == case_id
    assert fuentes_ajenas(case_id, report) == []
    keys = report["key_questions"]
    assert all(len(q["topic"]) <= 120 for q in keys["obtained"] + keys["missing"])
    assert report["diagnosis"]["reference"] == case["protected"]["diagnosis"]["name"]
    assert all(item["text"] for item in report["revealed_evidence"])
    if all_evidence:
        assert keys["missing"] == []
        assert report["score"]["score"] == 100.0
    else:
        assert keys["obtained"] == []


def test_el_verificador_detecta_fuentes_ajenas():
    # Control negativo: si el reporte trajera datos de otro caso, la prueba de arriba lo marcaría.
    report = _report(CASES["EME-101"], True)
    report["revealed_evidence"].append({"evidence_id": "CIR-005.lab.factores_coagulacion", "label": "x", "text": "x"})
    report["differentials"].append("Hemofilia A")
    assert fuentes_ajenas("EME-101", report) == ["CIR-005.lab.factores_coagulacion", "Hemofilia A"]
