"""Batería con el modelo real (Groq) que recorre el guion de los 13 pacientes (guiones.py).

En cada caso hace primero los pedidos de «preguntar», en orden, y luego los de «no preguntar».
- Preguntar: responde el agente esperado, revela los datos esperados y cuenta sus cifras.
- No preguntar: no revela ningún dato nuevo (lo ya revelado en turnos anteriores no cuenta).
- En todos: no nombra el diagnóstico ni los diferenciales, no inventa síntomas y no usa términos
  internos («evidencia», «autorizado», «recuperado»).

Misma configuración que el sitio publicado (recuperación directa del caso, sin índice LightRAG).
Guarda el detalle en resultados_guiones.json.

Uso (desde backend/):  .venv\\Scripts\\python.exe ..\\pruebas\\13_guiones_por_paciente\\bateria_guiones.py [CASO ...]
"""

import json
import re
import sys
import time
import unicodedata
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

import server.api.ai as ai_module
from server.ai.agents.invencion import invented_symptoms
from server.config import settings
from server.main import app

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guiones import GUIONES  # noqa: E402

CURATED = HERE.parents[1] / "data" / "cases" / "curated"
TERMINOS_INTERNOS = re.compile(r"evidencia|autorizad|recuperad|retrieved|evidence", re.IGNORECASE)
NUMEROS = {"1": ("uno", "una", "un"), "2": ("dos",), "3": ("tres",), "4": ("cuatro",), "5": ("cinco",),
           "6": ("seis",), "7": ("siete",), "8": ("ocho",), "9": ("nueve",), "10": ("diez",), "12": ("doce",),
           "15": ("quince",), "20": ("veinte",), "30": ("treinta",), "60": ("sesenta",)}


def normalize(text: str) -> str:
    raw = unicodedata.normalize("NFD", text.casefold())
    return "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")


def cifras_omitidas(dato: str, respuesta: str) -> list[str]:
    en_respuesta = {c.replace(",", ".") for c in re.findall(r"\d+(?:[.,]\d+)?", respuesta)}
    palabras = set(re.findall(r"[a-z]+", normalize(respuesta)))
    return [c for c in dict.fromkeys(re.findall(r"\d+(?:[.,]\d+)?", dato))
            if c.replace(",", ".") not in en_respuesta and not palabras & set(NUMEROS.get(c, ()))]


ai_module.settings = replace(settings, rag_embedded_enabled=False, rag_service_url="")
ai_module.get_service.cache_clear()
client = TestClient(app)
status = client.get("/api/ai/status").json()
print(f"LLM: {status['llm_mode']} ({settings.groq_model}) · recuperación: {status['retrieval_mode']}")
if status["llm_mode"] != "groq-pool":
    raise SystemExit("La batería necesita Groq: revise GROQ_API_KEYS en el .env.")

casos = sys.argv[1:] or list(GUIONES)
resultados: dict[str, dict] = {}
for case_id in casos:
    guion = GUIONES[case_id]
    case = json.loads((CURATED / f"{case_id}.json").read_text(encoding="utf-8"))
    protected = case["protected"]
    prohibidos = [protected["diagnosis"]["name"], *protected["diagnosis"]["synonyms"],
                  *(d["name"] for d in protected["differentials"])]
    todo = {"public_evidence": [case["public"]["chief_complaint"], *case["public"]["items"]],
            "retrieved_evidence": case["on_request"], "case_title": case["title"]}
    textos = {item["evidence_id"]: item.get("text", "") for item in case["on_request"]}
    inicio = client.post("/api/ai/sessions", json={"case_id": case_id}).json()
    sid = inicio["session_id"]
    # El médico asistente devuelve todo lo revelado hasta ese turno: solo cuenta lo nuevo.
    ya_revelados = set(inicio.get("revealed_evidence_ids", []))
    print(f"\n{case_id} · {case['public']['patient']['alias']}")
    turnos, fallos = [], 0
    pasos = [("preguntar", p, a, d) for p, a, d in guion["preguntar"]] + [("no preguntar", p, None, []) for p, _ in guion["no_preguntar"]]
    for tipo, pedido, agente, sufijos in pasos:
        r = client.post(f"/api/ai/sessions/{sid}/message", json={"message": pedido})
        datos = r.json() if r.status_code == 200 else {"agent": None, "response": f"HTTP {r.status_code}", "evidence_ids": []}
        texto = datos.get("response", "")
        revelados = [e for e in datos.get("evidence_ids", []) if e not in ya_revelados]
        ya_revelados.update(datos.get("evidence_ids", []))
        esperados = [f"{case_id}.{s}" for s in sufijos]
        problemas = []
        if r.status_code != 200:
            problemas.append(f"HTTP {r.status_code}")
        if tipo == "preguntar":
            if datos.get("agent") != agente:
                problemas.append(f"respondió {datos.get('agent')}, se esperaba {agente}")
            faltan = [e for e in esperados if e not in revelados]
            if faltan:
                problemas.append(f"no reveló {faltan}")
            omitidas = [c for e in esperados if e in revelados for c in cifras_omitidas(textos[e], texto)]
            if omitidas:
                problemas.append(f"omite las cifras {omitidas}")
        elif revelados:
            problemas.append(f"reveló {revelados} sin que correspondiera")
        fuga = [t for t in prohibidos if len(t) >= 4 and normalize(t) in normalize(texto)]
        if fuga:
            problemas.append(f"nombra {fuga}")
        inventa = invented_symptoms(texto, todo)
        if inventa:
            problemas.append(f"inventa {inventa}")
        if TERMINOS_INTERNOS.search(texto):
            problemas.append("usa términos internos")
        fallos += bool(problemas)
        print(f"  [{'OK' if not problemas else 'FALLA'}] ({tipo}) {pedido} -> {datos.get('agent')}")
        if datos.get("doctor_question"):
            print(f"        médico tratante: {datos['doctor_question']}")
        print(f"        respuesta: {texto}")
        for problema in problemas:
            print(f"        ! {problema}")
        turnos.append({"tipo": tipo, "pedido": pedido, "agente": datos.get("agent"), "medico_tratante": datos.get("doctor_question"),
                       "respuesta": texto, "evidencia": revelados, "problemas": problemas})
        time.sleep(1.5)
    resultados[case_id] = {"turnos": turnos, "fallos": fallos}

total = sum(len(r["turnos"]) for r in resultados.values())
con_fallo = sum(r["fallos"] for r in resultados.values())
print("\nRESUMEN")
for case_id, r in resultados.items():
    print(f"  {case_id}: {len(r['turnos']) - r['fallos']} de {len(r['turnos'])} pedidos correctos")
print(f"  total: {total - con_fallo} de {total}")
(HERE / "resultados_guiones.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\nRESULTADO: {'todos los guiones funcionan' if not con_fallo else f'{con_fallo} pedidos con problemas'}")
sys.exit(1 if con_fallo else 0)
