"""HU-006: el reporte final se arma solo con datos del caso y de la propia sesión."""
import copy
import json
from pathlib import Path

from server.engine.evaluation import ClinicalEvaluationEngine
from server.report import build_report

CASE = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "cases" / "MED-900.json").read_text(encoding="utf-8"))
INITIAL = ["MED-900.motivo.cefalea", "MED-900.vital.presion_arterial", "MED-900.vital.frecuencia_cardiaca",
           "MED-900.vital.temperatura"]


class _Repo:
    def get_protected(self, case_id):
        return copy.deepcopy(CASE["protected"])


def _session(requested=(), **extra):
    session = {
        "session_id": "00000000-0000-4000-8000-000000000001",
        "case_id": "MED-900",
        "phase": "finalizada",
        "revealed_evidence_ids": [*INITIAL, *requested],
        "requested_evidence_ids": list(requested),
        "finished_at": "2026-10-28T10:00:00+00:00",
        "student_diagnosis": "Migraña",
        "student_hypotheses": [{"name": "Migraña", "discarded": False, "reason": ""}],
    }
    session["evaluation"] = ClinicalEvaluationEngine(_Repo()).evaluate(
        case_id="MED-900", evidence_ids=list(requested), initial_evidence_ids=INITIAL)
    session.update(extra)
    return session


def test_reporte_con_dos_preguntas_obtenidas():
    requested = ["MED-900.anamnesis.inicio_dolor", "MED-900.anamnesis.alergias"]
    report = build_report(_session(requested), copy.deepcopy(CASE), [])
    keys = report["key_questions"]
    assert [q["id"] for q in keys["obtained"]] == ["kq1", "kq3"]
    assert [q["id"] for q in keys["missing"]] == ["kq2"]
    missing = keys["missing"][0]
    assert missing["error_type"] == "negligencia"
    assert missing["error_name"] == "Negligencia"
    assert missing["critical"] is True
    assert missing["why"] == "Dato de seguridad: se pregunta antes de indicar un tratamiento."
    assert missing["helps_discard"] == ["Meningitis", "Hemorragia subaracnoidea"]
    expected = ClinicalEvaluationEngine(_Repo()).evaluate(case_id="MED-900", evidence_ids=requested,
                                                         initial_evidence_ids=INITIAL)
    assert report["score"] == {k: expected[k] for k in
                               ("score", "earned_weight", "total_weight", "completed_questions", "total_questions")}


def test_diagnostico_de_referencia_y_propuesta():
    hypotheses = [{"name": "<b>x</b>", "discarded": True, "reason": "no encaja"}]
    report = build_report(_session(student_diagnosis="<b>x</b>", student_hypotheses=hypotheses), copy.deepcopy(CASE), [])
    assert report["diagnosis"] == {"student": "<b>x</b>", "reference": "Migraña sin signos de alarma",
                                   "synonyms": ["migraña", "cefalea migrañosa"]}
    assert report["hypotheses"] == hypotheses
    assert report["differentials"] == ["Meningitis", "Hemorragia subaracnoidea", "Cefalea tensional"]
    assert report["patient"]["alias"] == CASE["public"]["patient"]["alias"]
    assert report["chief_complaint"] == CASE["public"]["chief_complaint"]["text"]
    assert report["case_id"] == "MED-900"
    assert report["finished_at"] == "2026-10-28T10:00:00+00:00"


def test_examenes():
    report = build_report(_session(["MED-900.laboratorio.hemograma"]), copy.deepcopy(CASE), [])
    tests = report["tests"]
    assert tests["optional_requested"] == [{"name": "hemograma", "label": "Hemograma"}]
    assert tests["recommended_requested"] == []
    assert tests["recommended_missing"] == []
    assert tests["unnecessary_requested"] == []
    assert tests["other_indications"] == ["Evaluacion clinica"]


def test_examen_opcional_por_prefijo():
    report = build_report(_session(["MED-900.imagen.tomografia_craneo"]), copy.deepcopy(CASE), [])
    assert report["tests"]["optional_requested"] == [{"name": "tomografia", "label": "Tomografía de cráneo"}]


def test_tratamiento():
    events = [
        {"type": "session_started"},
        {"type": "turn", "intent": "propose_treatment", "student_message": "Indico paracetamol",
         "safety_alerts": ["known_allergy"]},
        {"type": "turn", "intent": "ask_patient", "student_message": "¿Le duele?", "safety_alerts": []},
    ]
    report = build_report(_session(), copy.deepcopy(CASE), events)
    assert report["treatment"] == {
        "proposed": [{"message": "Indico paracetamol", "alerts": ["known_allergy"]}],
        "reference_summary": CASE["protected"]["treatment_reference"]["summary"],
        "key_actions": CASE["protected"]["treatment_reference"]["key_actions"],
    }


def test_evidencia_revelada():
    requested = ["MED-900.sintoma.fotofobia", "MED-900.anamnesis.alergias"]
    report = build_report(_session(requested), copy.deepcopy(CASE), [])
    revealed = report["revealed_evidence"]
    assert [item["evidence_id"] for item in revealed] == [*INITIAL, *requested]
    by_id = {e["evidence_id"]: e for e in CASE["on_request"]}
    assert revealed[-1] == {"evidence_id": "MED-900.anamnesis.alergias",
                            "label": by_id["MED-900.anamnesis.alergias"]["label"],
                            "text": by_id["MED-900.anamnesis.alergias"]["text"]}
    assert revealed[0]["text"] == CASE["public"]["chief_complaint"]["text"]


def test_consulta_sin_preguntas():
    report = build_report(_session(), copy.deepcopy(CASE), [])
    assert report["key_questions"]["obtained"] == []
    assert [q["id"] for q in report["key_questions"]["missing"]] == ["kq1", "kq2", "kq3"]
    assert report["tests"]["optional_requested"] == []
    assert report["treatment"]["proposed"] == []
    assert report["recommendations"] == [
        "Antes de indicar un tratamiento, verifica alergias, antecedentes y los estudios críticos del caso.",
        "Completa la anamnesis: inicio y evolución, antecedentes, medicación, alergias y hábitos.",
    ]


def test_recomendacion_por_alerta_y_por_defecto():
    complete = ["MED-900.anamnesis.inicio_dolor", "MED-900.anamnesis.alergias", "MED-900.anamnesis.signos_alarma"]
    report = build_report(_session(complete), copy.deepcopy(CASE), [])
    assert report["recommendations"] == [
        "Mantén el mismo orden: anamnesis completa, exámenes dirigidos y verificación de alergias antes de tratar."]
    events = [{"type": "turn", "intent": "propose_treatment", "student_message": "x", "safety_alerts": ["case_contraindication"]}]
    report = build_report(_session(complete), copy.deepcopy(CASE), events)
    assert report["recommendations"] == [
        "Propusiste un tratamiento que coincide con una alergia o contraindicación del caso: revisa los antecedentes antes de indicarlo."]


def test_ids_ajenos_se_descartan():
    session = _session(["MED-900.anamnesis.alergias"])
    session["revealed_evidence_ids"].append("OTRO-001.anamnesis.alergias")
    report = build_report(session, copy.deepcopy(CASE), [])
    assert "OTRO-001" not in json.dumps(report, ensure_ascii=False)


def test_sin_evaluacion_guardada_la_calcula():
    session = _session(["MED-900.anamnesis.alergias"])
    expected = session.pop("evaluation")
    report = build_report(session, copy.deepcopy(CASE), [])
    assert report["score"]["score"] == expected["score"]
