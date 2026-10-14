"""Prueba la API de sesiones con todos los casos curados, solo en memoria."""

from __future__ import annotations

import json
import sys
from collections import Counter
from functools import partial
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import server.api.ai as ai_module
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import LocalDevelopmentProvider
from server.cases import CanonicalCaseRepository
from server.config import settings
from server.domain import AgentRole, Intent
from server.engine.disclosure.policy import DisclosurePolicy
from server.orchestration import InMemorySessionStore
from server.orchestration.router import DecisionRouter
from server.main import app

CASES_DIR = ROOT / "data" / "cases" / "curated"
RESULTS_DIR = Path(__file__).resolve().parent / "resultados"
RESULTS_PATH = RESULTS_DIR / "resultados_casos_curados.json"

INTENT_BY_POLICY = {
    ("paciente", "al_preguntar"): Intent.ASK_PATIENT,
    ("medico_asistente", "al_examinar"): Intent.EXAMINE,
    ("laboratorio", "al_solicitar_examen"): Intent.REQUEST_LAB,
    ("radiologia", "al_solicitar_examen"): Intent.REQUEST_RADIOLOGY,
    ("especialista", "al_preguntar"): Intent.REQUEST_SPECIALIST,
}

AGENT_BY_OWNER = {
    "paciente": "paciente",
    "medico_asistente": "medico_asistente",
    "laboratorio": "laboratorio",
    "radiologia": "radiologia",
    "especialista": "especialista",
}


def _message_for(owner: str, requirements: list[str]) -> str:
    topics = " y ".join(requirements).replace("_", " ")
    if owner == "paciente":
        return f"¿Puede contarme sobre {topics}?"
    if owner == "medico_asistente":
        return f"Voy a realizar la exploración física para revisar {topics}."
    if owner == "laboratorio":
        return f"Solicito un examen de laboratorio: {topics}."
    if owner == "radiologia":
        return f"Solicito una imagen para revisar {topics}."
    if owner == "especialista":
        return f"Solicito una interconsulta con {topics}."
    raise ValueError(f"Rol de caso no reconocido: {owner}")


def _request_json(client: TestClient, method: str, url: str, **kwargs) -> dict[str, Any]:
    response = client.request(method, url, **kwargs)
    if response.status_code != 200:
        raise RuntimeError(f"{method} {url} respondió HTTP {response.status_code}: {response.text}")
    return response.json()


def _prepare_test_api() -> None:
    ai_module.CASES_DIR = CASES_DIR
    ai_module.CanonicalCaseRepository = partial(
        CanonicalCaseRepository,
        accepted_statuses=("curado",),
    )
    ai_module.settings = settings.__class__(
        **{
            **settings.__dict__,
            "rag_embedded_enabled": False,
            "rag_service_url": "",
            "session_store": "memoria",
        }
    )
    ai_module.STORE = InMemorySessionStore()
    ai_module.build_gateway = lambda: LLMGateway([LocalDevelopmentProvider()])
    ai_module.get_service.cache_clear()


def _curated_case_documents() -> list[dict[str, Any]]:
    paths = sorted(CASES_DIR.glob("*.json"))
    if not paths:
        raise RuntimeError(f"No se encontraron casos JSON en {CASES_DIR}.")
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    by_specialty = Counter(case["specialty"] for case in cases)
    if any(case["status"] != "curado" for case in cases):
        raise RuntimeError("La carpeta contiene un caso cuyo status no es curado.")
    print(f"Casos curados encontrados: {len(cases)}")
    for specialty, count in sorted(by_specialty.items()):
        print(f"  {specialty}: {count}")
    return cases


def _plans_for_case(case: dict[str, Any]) -> list[dict[str, Any]]:
    policy_engine = DisclosurePolicy()
    router = DecisionRouter()
    plan_by_message: dict[str, dict[str, Any]] = {}

    for item in case["on_request"]:
        policy = item["reveal_policy"]
        owner = policy["owner"]
        intent = INTENT_BY_POLICY.get((owner, policy["mode"]))
        if intent is None:
            raise RuntimeError(
                f"{case['case_id']}: política sin prueba configurada: {owner}/{policy['mode']}."
            )

        message = _message_for(owner, policy["requires"])
        decision = router.route(message)
        expected_agent = AGENT_BY_OWNER[owner]
        if decision.target.value != expected_agent or decision.intent != intent:
            raise RuntimeError(
                f"{case['case_id']}: el guion '{message}' se enruta a "
                f"{decision.target.value}/{decision.intent.value}, se esperaba {expected_agent}/{intent.value}."
            )

        authorized_ids = policy_engine.authorize(
            case=case,
            role=AgentRole(owner),
            intent=intent,
            student_message=message,
        ).allowed_evidence_ids
        if item["evidence_id"] not in authorized_ids:
            raise RuntimeError(
                f"{case['case_id']}: el guion no autoriza su evidencia {item['evidence_id']}."
            )

        plan_by_message[message] = {
            "message": message,
            "intent": intent,
            "agent": expected_agent,
            "evidence_ids": authorized_ids,
        }

    return list(plan_by_message.values())


def _check_treatment_safety(client: TestClient, session_id: str, case: dict[str, Any]) -> list[str]:
    expected_alerts: set[str] = set()
    treatment_parts: list[str] = []

    contraindications = case["protected"]["contraindications"]
    if contraindications:
        treatment_parts.extend(item["drug_or_class"] for item in contraindications)
        expected_alerts.add("case_contraindication")

    public = case["public"]
    if public.get("allergies_recorded") and public.get("allergies"):
        treatment_parts.extend(public["allergies"])
        expected_alerts.add("known_allergy")

    if not treatment_parts:
        return []

    result = _request_json(
        client,
        "POST",
        f"/api/ai/sessions/{session_id}/message",
        json={"message": f"Mi tratamiento es administrar {' y '.join(treatment_parts)}."},
    )
    if result.get("agent") != "medico_asistente":
        raise RuntimeError(
            f"{case['case_id']}: la propuesta de tratamiento se enrutó a {result.get('agent')}."
        )

    alerts = {alert["code"] for alert in result.get("safety_alerts", [])}
    missing = expected_alerts - alerts
    if missing:
        raise RuntimeError(
            f"{case['case_id']}: faltan alertas de seguridad {sorted(missing)}; recibidas: {sorted(alerts)}."
        )
    return sorted(alerts)


def run() -> list[dict[str, Any]]:
    cases = _curated_case_documents()
    _prepare_test_api()
    results: list[dict[str, Any]] = []

    try:
        with TestClient(app) as client:
            status = _request_json(client, "GET", "/api/ai/status")
            print("Proveedor LLM: local-development; recuperador: deterministic-case-fallback")

            for case in cases:
                case_id = case["case_id"]
                print(f"Probando {case_id} ({case['specialty']}) ...")
                session = _request_json(
                    client,
                    "POST",
                    "/api/ai/sessions",
                    json={"case_id": case_id},
                )
                session_id = session["session_id"]
                initial_vitals = session["avatar_state"]["vitals"]
                plans = _plans_for_case(case)
                turns: list[dict[str, Any]] = []

                for plan in plans:
                    response = _request_json(
                        client,
                        "POST",
                        f"/api/ai/sessions/{session_id}/message",
                        json={"message": plan["message"]},
                    )
                    if response.get("agent") != plan["agent"]:
                        raise RuntimeError(
                            f"{case_id}: se esperaba {plan['agent']} y respondió {response.get('agent')}."
                        )
                    returned_ids = response.get("evidence_ids", [])
                    if returned_ids != plan["evidence_ids"]:
                        raise RuntimeError(
                            f"{case_id}: evidencia esperada {plan['evidence_ids']}; recibida {returned_ids}."
                        )
                    turns.append({
                        "message": plan["message"],
                        "intent": plan["intent"].value,
                        "agent": response["agent"],
                        "expected_evidence_ids": plan["evidence_ids"],
                        "evidence_ids": returned_ids,
                        "safety_alerts": [item["code"] for item in response.get("safety_alerts", [])],
                    })

                treatment_alerts = _check_treatment_safety(client, session_id, case)
                state = _request_json(client, "GET", f"/api/ai/sessions/{session_id}")
                vitals_preserved = state["avatar_state"]["vitals"] == initial_vitals
                if not vitals_preserved:
                    raise RuntimeError(f"{case_id}: cambiaron los signos vitales del avatar.")

                finished = _request_json(client, "POST", f"/api/ai/sessions/{session_id}/finish")
                evaluation = finished.get("evaluation")
                if not evaluation:
                    raise RuntimeError(f"{case_id}: la API no devolvió la evaluación final.")

                results.append({
                    "case_id": case_id,
                    "specialty": case["specialty"],
                    "source_dataset": case["source"]["dataset"],
                    "status": case["status"],
                    "verified_turns": len(turns),
                    "all_roles_and_evidence_correct": True,
                    "treatment_safety_alerts": treatment_alerts,
                    "vitals_preserved": vitals_preserved,
                    "evaluation": evaluation,
                    "turns": turns,
                })

    finally:
        ai_module.get_service.cache_clear()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nRESULTADOS")
    print(f"{'CASO':10} {'ESPECIALIDAD':30} {'TURNOS':>6} {'PUNTAJE':>8} {'EVALUACIÓN':>12} ALERTAS")
    for result in results:
        evaluation = result["evaluation"]
        completed = f"{evaluation['completed_questions']}/{evaluation['total_questions']}"
        alerts = ", ".join(result["treatment_safety_alerts"]) or "-"
        print(
            f"{result['case_id']:10} {result['specialty']:30} {result['verified_turns']:>6} "
            f"{evaluation['score']:>7.2f}% {completed:>12} {alerts}"
        )
    print(f"\nDetalle guardado en: {RESULTS_PATH}")
    return results


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"\nPRUEBA FALLIDA: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
