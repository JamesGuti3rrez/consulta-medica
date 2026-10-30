"""TA-027: informe de hallazgos y bloqueo previo de casos alterados."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from server.auth import AuthUser, current_user
from server.cases.catalog import CURATED_CASES_DIR
from server.cases.consistency import review_case
from server.cases.repository import CanonicalCaseRepository, CaseValidationError
from server.cases.uploads import prepare_cases
from server.main import app

TASK = "TA-027"


@pytest.mark.parametrize("path", sorted(CURATED_CASES_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_current_curated_case_has_classified_consistency_report(path):
    report = review_case(json.loads(path.read_text(encoding="utf-8")))
    assert report["can_present"] and report["status"] == "apto"
    assert report["version"] and len(report["fingerprint"]) == 64
    assert all({"code", "severity", "path", "message", "evidence_ids"} <= set(f) for f in report["findings"])


@pytest.mark.parametrize("mutation", ["missing", "foreign", "exposed", "implausible", "policy", "contradiction"])
def test_intentionally_altered_case_is_not_presented_or_published(api, tmp_path, mutation):
    _, service, _ = api
    case = service.repository.get_case("MED-008")
    if mutation == "missing":
        del case["protected"]["diagnosis"]
    elif mutation == "foreign":
        case["on_request"][0]["evidence_id"] = "CIR-005.sintoma.ajeno"
    elif mutation == "exposed":
        case["public"]["patient"]["alias"] = "CARCINOMA DE CELULAS BASALES"
    elif mutation == "implausible":
        case["public"]["items"].append({"evidence_id": "MED-008.vital.temperatura", "label": "Temperatura",
            "category": "signo_vital", "value": 99, "unit": "Cel"})
    elif mutation == "policy":
        case["on_request"][0]["reveal_policy"]["owner"] = "laboratorio"
    else:
        item = deepcopy(case["on_request"][0]); item["evidence_id"] += "_otra"; item["text"] = "Dato temporal contradictorio."
        case["on_request"].append(item)
    report = review_case(case)
    assert not report["can_present"] and report["requires_human_review"]
    assert any(f["severity"] in {"error", "revision"} for f in report["findings"])
    (tmp_path / "MED-008.json").write_text(json.dumps(case), encoding="utf-8")
    with pytest.raises(CaseValidationError):
        CanonicalCaseRepository(tmp_path).get_conversation_case("MED-008")
    _, errors, _ = prepare_cases([case], [], "docente")
    assert errors


@pytest.mark.parametrize("role,expected", [("profesor", 200), ("administrativo", 200), ("alumno", 403), (None, 401)])
def test_consistency_report_is_available_only_to_staff(api, role, expected):
    client, service, _ = api
    def user():
        if role is None:
            raise HTTPException(401, "Sin credencial")
        return AuthUser(id="docente-prueba", email="docente@example.com", role=role)
    app.dependency_overrides[current_user] = user
    try:
        response = client.post("/api/docente/consistencia", json={"caso": service.repository.get_case("MED-008")})
        assert response.status_code == expected
        if expected == 200:
            assert response.json()["can_present"]
        else:
            assert "findings" not in response.json()
    finally:
        app.dependency_overrides.pop(current_user, None)


@pytest.mark.parametrize("invalid", [None, [], {}, {"case_id": "MED-008", "public": {}}])
def test_incomplete_document_returns_report_instead_of_crashing(invalid):
    report = review_case(invalid)
    assert report["status"] == "bloqueado" and report["findings"][0]["code"] == "CV001"


def test_invalid_case_is_rejected_by_session_api_before_creating_state(api, tmp_path, monkeypatch):
    client, service, _ = api
    case = service.repository.get_case("MED-008")
    case["public"]["patient"]["alias"] = "Carcinoma basocelular"
    (tmp_path / "MED-008.json").write_text(json.dumps(case), encoding="utf-8")
    service.repository = CanonicalCaseRepository(tmp_path)
    created = []
    monkeypatch.setattr(service.store, "create", lambda state: created.append(state))
    response = client.post("/api/ai/sessions", json={"case_id": "MED-008"})
    assert response.status_code == 409 and not created
    assert "carcinoma" not in response.text.lower() and "session_token" not in response.json()
