"""Batería con el modelo real (Groq) sobre la familia sintética de dolor torácico (EME-101 a EME-103).

Un mismo guion de estudiante (14 pedidos, de la anamnesis a la imagen) se aplica a los tres casos, que
empiezan con el mismo motivo de consulta. En cada turno comprueba:
  - que responda el agente correcto y se revele el dato esperado (y ninguno de otro dueño);
  - que la respuesta no nombre el diagnóstico ni los diferenciales (fuga);
  - que no afirme síntomas que el caso no tiene (detector de server/ai/agents/invencion.py);
y con los datos revelados sigue cada hipótesis: pasa a «menos probable» cuando se revela alguno de sus
discard_evidence_ids y queda «descartada» cuando se revelan todos. Al final, la misma pregunta debe dar respuestas distintas en los
tres casos.

Usa la misma configuración que el sitio publicado: recuperación directa del caso (sin índice LightRAG)
y sesiones en memoria. Guarda el detalle en resultados_bateria.json.

Uso (desde backend/):  .venv\\Scripts\\python.exe ..\\pruebas\\12_familias_sinteticas\\01_bateria_dolor_toracico\\bateria_familia.py
"""

import json
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
CURATED = Path(__file__).resolve().parents[3] / "data" / "cases" / "curated"
FAMILY = ("EME-101", "EME-102", "EME-103")
# (pedido del estudiante, agente esperado, dato esperado: sufijo del evidence_id)
GUION = [
    ("¿Cómo es el dolor? Descríbalo, por favor", "paciente", "anamnesis.caracteristicas_dolor"),
    ("Pregúntele cuándo empezó y cómo ha evolucionado", "paciente", "anamnesis.inicio_evolucion"),
    ("¿Tiene algún otro síntoma?", "paciente", "sintoma.sintomas_acompanantes"),
    ("Pregúntele por sus antecedentes de enfermedades", "paciente", "antecedente.antecedentes"),
    ("¿Toma algún medicamento?", "paciente", "medicacion.tratamiento_habitual"),
    ("¿Tiene alergias?", "paciente", "antecedente.alergias"),
    ("¿Fuma? ¿Ha hecho algún viaje reciente?", "paciente", "antecedente.habitos"),
    ("¿Alguien en su familia ha tenido problemas del corazón?", "paciente", "antecedente.antecedentes_familiares"),
    ("Voy a realizar la exploración física completa", "medico_asistente", "examen.exploracion_fisica"),
    ("Pido un electrocardiograma de 12 derivaciones", "laboratorio", "estudio.electrocardiograma"),
    ("Solicito troponina", "laboratorio", "lab.troponina"),
    ("Solicito dímero D", "laboratorio", "lab.dimero_d"),
    ("Pido una radiografía de tórax", "radiologia", "imagen.radiografia_torax"),
    ("Solicito una angiotomografía de tórax", "radiologia", "imagen.angiotomografia_torax"),
]


def normalize(text: str) -> str:
    raw = unicodedata.normalize("NFD", text.casefold())
    return "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")


ai_module.settings = replace(settings, rag_embedded_enabled=False, rag_service_url="")
ai_module.get_service.cache_clear()
client = TestClient(app)
status = client.get("/api/ai/status").json()
print(f"LLM: {status['llm_mode']} ({settings.groq_model}) · recuperación: {status['retrieval_mode']} · sesiones: {status['session_store']}")
if status["llm_mode"] != "groq-pool":
    raise SystemExit("La batería necesita Groq: revise GROQ_API_KEYS en el .env.")

resultados = {"guion": [pedido for pedido, _, _ in GUION], "casos": {}}
totales = {"turnos": 0, "agente_y_dato_ok": 0, "fugas": 0, "inventadas": 0, "bloqueadas": 0}
respuestas_por_turno: dict[int, list[str]] = {i: [] for i in range(len(GUION))}

for case_id in FAMILY:
    case = json.loads((CURATED / f"{case_id}.json").read_text(encoding="utf-8"))
    protected = case["protected"]
    prohibidos = [protected["diagnosis"]["name"], *protected["diagnosis"]["synonyms"], *(d["name"] for d in protected["differentials"])]
    todo_el_caso = {"public_evidence": [case["public"]["chief_complaint"], *case["public"]["items"]],
                    "retrieved_evidence": case["on_request"], "case_title": case["title"]}
    hipotesis = {protected["diagnosis"]["name"]: [], **{d["name"]: d["discard_evidence_ids"] for d in protected["differentials"]}}
    estado = {h: "en pie" for h in hipotesis}
    revelados: set[str] = set()

    sid = client.post("/api/ai/sessions", json={"case_id": case_id}).json()["session_id"]
    print(f"\n{case_id} · {case['public']['patient']['alias']} · diagnóstico: {protected['diagnosis']['name']}")
    print(f"  hipótesis al inicio ({len(hipotesis)}): {'; '.join(hipotesis)}")
    turnos = []
    for i, (pedido, agente, sufijo) in enumerate(GUION):
        r = client.post(f"/api/ai/sessions/{sid}/message", json={"message": pedido})
        datos = r.json() if r.status_code == 200 else {"agent": None, "response": f"HTTP {r.status_code}", "evidence_ids": []}
        esperado = f"{case_id}.{sufijo}"
        ok = r.status_code == 200 and datos["agent"] == agente and esperado in datos["evidence_ids"]
        texto = datos.get("response", "")
        fuga = [t for t in prohibidos if len(t) >= 4 and normalize(t) in normalize(texto)]
        inventa = invented_symptoms(texto, todo_el_caso)
        bloqueada = bool(datos.get("blocked"))
        revelados.update(datos.get("evidence_ids", []))
        cambios = []
        for h, datos_que_descartan in hipotesis.items():
            vistos = set(datos_que_descartan) & revelados
            nuevo = "descartada" if datos_que_descartan and vistos == set(datos_que_descartan) else "menos probable" if vistos else "en pie"
            if nuevo != estado[h]:
                cambios.append(f"{h}: {nuevo}")
                estado[h] = nuevo
        en_pie = [h for h, e in estado.items() if e != "descartada"]
        totales["turnos"] += 1
        totales["agente_y_dato_ok"] += ok
        totales["fugas"] += bool(fuga)
        totales["inventadas"] += bool(inventa)
        totales["bloqueadas"] += bloqueada
        respuestas_por_turno[i].append(normalize(texto))
        marca = "OK" if ok and not fuga and not inventa else "FALLA"
        detalle = []
        if not ok:
            detalle.append(f"esperaba {agente} con {sufijo}, llegó {datos.get('agent')} con {datos.get('evidence_ids')}")
        if fuga:
            detalle.append(f"nombra {fuga}")
        if inventa:
            detalle.append(f"inventa {inventa}")
        print(f"  [{marca}] {i + 1:>2}. {pedido} -> {datos.get('agent')}")
        if datos.get("doctor_question"):
            print(f"        médico tratante: {datos['doctor_question']}")
        print(f"        respuesta: {texto}")
        for linea in detalle:
            print(f"        ! {linea}")
        for cambio in cambios:
            print(f"        hipótesis -> {cambio}")
        turnos.append({"pedido": pedido, "agente_esperado": agente, "agente": datos.get("agent"), "dato_esperado": esperado,
                       "evidencia": datos.get("evidence_ids", []), "medico_tratante": datos.get("doctor_question"),
                       "respuesta": texto, "ok": ok, "fuga": fuga, "inventa": inventa, "bloqueada": bloqueada,
                       "cambios_de_hipotesis": cambios, "estado_de_hipotesis": dict(estado)})
        time.sleep(1.5)
    en_pie = [h for h, e in estado.items() if e != "descartada"]
    final = en_pie == [protected["diagnosis"]["name"]]
    print(f"  {'[OK]' if final else '[FALLA]'} al final queda en pie: {'; '.join(en_pie)}")
    resultados["casos"][case_id] = {"diagnostico": protected["diagnosis"]["name"], "turnos": turnos,
                                    "queda_solo_el_diagnostico": final}

distintas = sum(len(set(textos)) == len(FAMILY) for textos in respuestas_por_turno.values())
print("\nRESUMEN")
print(f"  turnos: {totales['turnos']} ({len(FAMILY)} casos x {len(GUION)} pedidos)")
print(f"  agente y dato correctos: {totales['agente_y_dato_ok']} de {totales['turnos']}")
print(f"  respuestas que nombran el diagnóstico o un diferencial: {totales['fugas']}")
print(f"  respuestas con síntomas inventados: {totales['inventadas']}")
print(f"  respuestas bloqueadas por el filtro de salida: {totales['bloqueadas']}")
print(f"  pedidos con respuesta distinta en los 3 casos: {distintas} de {len(GUION)}")
finales = sum(c["queda_solo_el_diagnostico"] for c in resultados["casos"].values())
print(f"  casos en que al final solo queda el diagnóstico correcto: {finales} de {len(FAMILY)}")
resultados["resumen"] = {**totales, "respuestas_distintas": distintas, "casos_resueltos": finales}
(HERE / "resultados_bateria.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
fallo = totales["agente_y_dato_ok"] < totales["turnos"] or totales["fugas"] or totales["inventadas"] or finales < len(FAMILY)
print(f"\nRESULTADO: {'todas las comprobaciones pasan' if not fallo else 'hay comprobaciones que fallan'}")
sys.exit(1 if fallo else 0)
