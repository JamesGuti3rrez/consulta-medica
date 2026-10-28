"""Batería: con el guion de cada paciente, ¿el estudiante llega a un solo diagnóstico? (decisión 0002)

Recorre los 13 casos curados con los pedidos de «preguntar» de pruebas/13_guiones_por_paciente/guiones.py,
contra la misma API del simulador. En cada turno comprueba que responda el agente esperado, que revele
los datos esperados y que la respuesta no nombre el diagnóstico ni los diferenciales. Con los datos
revelados (más los que el doctor presenta al inicio) sigue cada diagnóstico diferencial: queda
«descartado» cuando se revelaron todos sus discard_evidence_ids. Al final del guion no debe quedar
ningún diferencial en pie: solo el diagnóstico del caso.

Uso (desde backend/):
    .venv\\Scripts\\python.exe ..\\pruebas\\18_casos_con_un_solo_diagnostico\\bateria_un_solo_diagnostico.py [--local] [CASO ...]

--local usa el proveedor determinístico (sin Groq, sin costo); sin él responde el modelo configurado en
.env, como en el sitio publicado. Guarda el detalle en resultados/ (resultados_local.json o
resultados_groq.json).
"""

from __future__ import annotations

import json
import sys
import time
import unicodedata
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "pruebas" / "13_guiones_por_paciente"))
sys.stdout.reconfigure(encoding="utf-8")

import server.api.ai as ai_module  # noqa: E402
from guiones import GUIONES  # noqa: E402
from server.ai.llm.gateway import LLMGateway  # noqa: E402
from server.ai.llm.providers import LocalDevelopmentProvider  # noqa: E402
from server.engine.disclosure.policy import DisclosurePolicy  # noqa: E402
from server.main import app  # noqa: E402
from server.orchestration import InMemorySessionStore  # noqa: E402

CURATED = ROOT / "data" / "cases" / "curated"
REVIEW = ROOT / "data" / "cases" / "reviews" / "medqa_lote_curacion.json"


def _complements() -> dict[str, set[str]]:
    """Claves de los datos que agregó el equipo, por caso (marca «complemento» del reparto)."""
    distribution = json.loads(REVIEW.read_text(encoding="utf-8"))["distribution"]
    return {case_id: {entry["key"] for entry in dist["on_request"] if "complemento" in entry}
            for case_id, dist in distribution.items()}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def _prepare(local: bool) -> str:
    ai_module.settings = replace(ai_module.settings, rag_embedded_enabled=False, rag_service_url="", session_store="memoria")
    ai_module.STORE = InMemorySessionStore()
    if local:
        ai_module.build_gateway = lambda: LLMGateway([LocalDevelopmentProvider()])
    ai_module.get_service.cache_clear()
    return "local" if local else ("groq" if ai_module.settings.groq_api_keys else "local")


def run_case(client: TestClient, case: dict, pause: float, complements: set[str]) -> dict:
    case_id = case["case_id"]
    protected = case["protected"]
    forbidden = {_normalize(protected["diagnosis"]["name"])} | {_normalize(d["name"]) for d in protected["differentials"]}
    session = client.post("/api/ai/sessions", json={"case_id": case_id}).json()
    revealed = set(DisclosurePolicy.initial_evidence_ids(case))
    turns, problems = [], []
    for message, agent, expected in GUIONES[case_id]["preguntar"]:
        # TA-011: la consulta de invitado se continúa con su credencial de capacidad.
        reply = client.post(f"/api/ai/sessions/{session['session_id']}/message", json={"message": message},
                            headers={"X-Session-Token": session["session_token"]})
        if reply.status_code != 200:
            problems.append(f"«{message}»: HTTP {reply.status_code}")
            continue
        body = reply.json()
        got = body.get("evidence_ids", [])
        revealed.update(got)
        missing = [suffix for suffix in expected if f"{case_id}.{suffix}" not in got]
        leaks = sorted(name for name in forbidden if name in _normalize(body.get("response", "")))
        if body.get("agent") != agent:
            problems.append(f"«{message}»: respondió {body.get('agent')}, se esperaba {agent}")
        if missing:
            problems.append(f"«{message}»: no reveló {missing}")
        if leaks:
            problems.append(f"«{message}»: la respuesta nombra {leaks}")
        team = sorted(suffix for suffix in expected if suffix.rsplit(".", 1)[-1] in complements)
        turns.append({"message": message, "agent": body.get("agent"), "evidence_ids": got,
                      "response": body.get("response", ""), "leaks": leaks, "complements": team})
        time.sleep(pause)
    standing = [d["name"] for d in protected["differentials"]
                if not d["discard_evidence_ids"] or not set(d["discard_evidence_ids"]) <= revealed]
    if standing:
        problems.append(f"diferenciales en pie al final: {standing}")
    return {"case_id": case_id, "diagnosis": protected["diagnosis"]["name"],
            "differentials": [d["name"] for d in protected["differentials"]], "standing": standing,
            "turns": turns, "problems": problems}


def main(args: list[str]) -> int:
    local = "--local" in args
    wanted = [arg for arg in args if not arg.startswith("--")]
    mode = _prepare(local)
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(CURATED.glob("*.json"))]
    cases = [case for case in cases if not wanted or case["case_id"] in wanted]
    print(f"Modelo: {mode} | casos: {len(cases)}\n")
    results = []
    complements = _complements()
    with TestClient(app) as client:
        for case in cases:
            result = run_case(client, case, pause=0.0 if mode == "local" else 1.5,
                              complements=complements.get(case["case_id"], set()))
            results.append(result)
            estado = "OK" if not result["problems"] else "FALLA"
            descartados = len(result["differentials"]) - len(result["standing"])
            print(f"{estado:5} {result['case_id']}  {len(result['turns']):>2} pedidos  "
                  f"diferenciales descartados {descartados}/{len(result['differentials'])}  -> queda: {result['diagnosis']}"
                  if not result["standing"] else
                  f"{estado:5} {result['case_id']}  {len(result['turns']):>2} pedidos  en pie: {result['standing']}")
            for problem in result["problems"]:
                print(f"        - {problem}")
            # Lo que el estudiante lee de cada dato agregado por el equipo (decisión 0002).
            for turn in result["turns"]:
                if turn["complements"]:
                    print(f"        complemento «{turn['message']}» -> {turn['response']}")
    out = HERE / "resultados" / f"resultados_{mode}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(not r["problems"] for r in results)
    print(f"\nRESUMEN: {ok} de {len(results)} casos llegan a un solo diagnóstico sin problemas")
    print(f"Detalle: {out.relative_to(ROOT)}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
