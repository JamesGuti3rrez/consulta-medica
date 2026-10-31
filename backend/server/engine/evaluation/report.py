"""Reporte final de una consulta cerrada (HU-007).

Se arma solo con el caso de la consulta y con la propia sesión: no consulta el RAG ni el modelo de lenguaje, y
descarta cualquier evidencia cuyo id no pertenezca al caso.
"""
from __future__ import annotations

from typing import Any

from server.engine.disclosure.policy import DisclosurePolicy

ERROR_NAMES = {
    "negligencia": "Negligencia",
    "anamnesis_incompleta": "Anamnesis incompleta",
    "razonamiento_clinico": "Razonamiento clínico",
}
# Por qué importaba un dato que faltó, según su tipo de omisión. Frases fijas: no se escribe texto clínico nuevo.
WHY = {
    "negligencia": "Dato de seguridad: se pregunta antes de indicar un tratamiento.",
    "anamnesis_incompleta": "Forma parte de una historia clínica completa.",
    "razonamiento_clinico": "Orienta o confirma el diagnóstico del caso.",
}
# Las mismas recomendaciones que mostraba la hoja de evaluación (frontend/public/js/simulacion.js).
RECOMMENDATIONS = {
    "negligencia": "Antes de indicar un tratamiento, verifica alergias, antecedentes y los estudios críticos del caso.",
    "anamnesis_incompleta": "Completa la anamnesis: inicio y evolución, antecedentes, medicación, alergias y hábitos.",
    "razonamiento_clinico": "Pide la exploración y los exámenes que confirmen o descarten cada una de tus hipótesis.",
}
SAFETY_RECOMMENDATION = ("Propusiste un tratamiento que coincide con una alergia o contraindicación del caso: "
                         "revisa los antecedentes antes de indicarlo.")
DEFAULT_RECOMMENDATION = ("Mantén el mismo orden: anamnesis completa, exámenes dirigidos y verificación de alergias "
                          "antes de tratar.")
SCORE_KEYS = ("score", "earned_weight", "total_weight", "completed_questions", "total_questions")


def build_report(session: dict[str, Any], case: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    if session.get("phase") != "finalizada" or not session.get("finished_at"):
        raise ValueError("El reporte solo está disponible al finalizar la consulta.")
    case_id = case["case_id"]
    own = f"{case_id}."
    public, protected = case["public"], case["protected"]
    initial = DisclosurePolicy.initial_evidence_ids(case)
    requested = [eid for eid in session.get("requested_evidence_ids", []) if eid.startswith(own)]
    observed = set(requested) | set(initial)

    alerts = [code for event in events if event.get("type") == "turn" for code in event.get("safety_alerts") or []]
    key_questions = _key_questions(protected, initial, observed)
    evaluation = session.get("evaluation") or _score(key_questions)
    return {
        "case_id": case_id,
        "finished_at": session.get("finished_at"),
        "patient": {key: public["patient"].get(key) for key in ("alias", "age_years", "sex")},
        "chief_complaint": public["chief_complaint"]["text"],
        "diagnosis": {
            "student": session.get("student_diagnosis") or "",
            "reference": protected["diagnosis"]["name"],
            "synonyms": list(protected["diagnosis"].get("synonyms", [])),
        },
        "hypotheses": list(session.get("student_hypotheses") or []),
        "differentials": [item["name"] for item in protected["differentials"]],
        "score": {key: evaluation[key] for key in SCORE_KEYS},
        "key_questions": key_questions,
        "tests": _tests(case, requested),
        "treatment": {
            "proposed": [
                {"message": event.get("student_message", ""), "alerts": list(event.get("safety_alerts") or [])}
                for event in events
                if event.get("type") == "turn" and event.get("intent") == "propose_treatment"
            ],
            "reference_summary": protected["treatment_reference"]["summary"],
            "key_actions": list(protected["treatment_reference"].get("key_actions", [])),
        },
        "revealed_evidence": _revealed(case, session.get("revealed_evidence_ids", []), own),
        **({"synthetic_exams": [entry["evidence"] for entry in session.get("synthetic_exam_results", {}).values()
                            if entry.get("evidence", {}).get("evidence_id") in session.get("revealed_evidence_ids", [])
                            and entry["evidence"]["evidence_id"].startswith(own)]}
           if session.get("synthetic_exam_results") else {}),
        "recommendations": _recommendations(key_questions["missing"], alerts),
    }


def _score(key_questions: dict[str, list]) -> dict[str, Any]:
    """El mismo cálculo que ClinicalEvaluationEngine.evaluate, para consultas sin evaluación guardada."""
    earned = sum(q["weight"] for q in key_questions["obtained"])
    total = earned + sum(q["weight"] for q in key_questions["missing"])
    return {
        "score": round(earned * 100 / total, 2),
        "earned_weight": earned,
        "total_weight": total,
        "completed_questions": len(key_questions["obtained"]),
        "total_questions": len(key_questions["obtained"]) + len(key_questions["missing"]),
    }


def _key_questions(protected: dict[str, Any], initial: list[str], observed: set[str]) -> dict[str, list]:
    # Mismas preguntas que puntúa el motor: las que entrega el doctor al presentar el caso no cuentan.
    questions = protected["evaluation"]["key_questions"]
    scored = [q for q in questions if not set(q["evidence_ids"]).issubset(initial)] or questions
    obtained, missing = [], []
    for question in scored:
        error_type = question["error_if_missing"]
        item = {
            "id": question["id"],
            "topic": question["topic"],
            "weight": question["weight"],
            "critical": bool(question.get("critical")),
            "error_type": error_type,
            "error_name": ERROR_NAMES.get(error_type, error_type),
            "why": WHY.get(error_type, ""),
            "helps_discard": [
                differential["name"] for differential in protected["differentials"]
                if set(differential.get("discard_evidence_ids", [])) & set(question["evidence_ids"])
            ],
        }
        (obtained if set(question["evidence_ids"]).issubset(observed) else missing).append(item)
    return {"obtained": obtained, "missing": missing}


def _tests(case: dict[str, Any], requested: list[str]) -> dict[str, list]:
    tests = case["protected"]["evaluation"].get("tests", {})
    evidence = {item["evidence_id"]: item for item in case["on_request"]}
    result = {key: [] for key in ("recommended_requested", "recommended_missing", "optional_requested",
                                  "unnecessary_requested", "other_indications")}
    for group in ("recommended", "optional", "unnecessary"):
        for name in tests.get(group, []):
            match = _evidence_for_test(name, evidence)
            if match is None:
                result["other_indications"].append(name.replace("_", " ").capitalize())
                continue
            entry = {"name": name, "label": evidence[match]["label"]}
            if match in requested:
                result[f"{group}_requested"].append(entry)
            elif group == "recommended":
                result["recommended_missing"].append(entry)
    return result


def _evidence_for_test(name: str, evidence: dict[str, dict]) -> str | None:
    """El examen corresponde a la evidencia cuyo último segmento es su nombre o empieza por «nombre_»."""
    for evidence_id in evidence:
        last = evidence_id.rsplit(".", 1)[-1]
        if last == name or last.startswith(f"{name}_"):
            return evidence_id
    return None


def _revealed(case: dict[str, Any], revealed_ids: list[str], own: str) -> list[dict[str, str]]:
    public = case["public"]
    sources = {public["chief_complaint"]["evidence_id"]: public["chief_complaint"]}
    sources.update({item["evidence_id"]: item for item in public.get("items", [])})
    sources.update({item["evidence_id"]: item for item in case["on_request"]})
    return [
        {"evidence_id": eid, "label": sources[eid].get("label", ""), "text": _evidence_text(sources[eid])}
        for eid in dict.fromkeys(revealed_ids)
        if eid.startswith(own) and eid in sources
    ]


def _evidence_text(item: dict[str, Any]) -> str:
    """El texto del dato; los que solo traen valor y unidad (signos vitales) se muestran como «74 /min»."""
    if item.get("text"):
        return item["text"]
    return " ".join(str(part) for part in (item.get("value"), item.get("unit")) if part not in (None, "")).strip()


def _recommendations(missing: list[dict], alerts: list[str]) -> list[str]:
    types = list(dict.fromkeys(item["error_type"] for item in missing))
    result = [RECOMMENDATIONS[t] for t in RECOMMENDATIONS if t in types]
    if alerts:
        result.append(SAFETY_RECOMMENDATION)
    return result or [DEFAULT_RECOMMENDATION]
