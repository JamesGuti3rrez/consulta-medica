"""HU-007: reporte final solo poscierre, con propietario validado y sin fuentes ajenas al case_id.

Usa la misma preparación que la suite de TA-011 (dos alumnos y dos invitados, en local con TestClient y
Supabase simulado, o en vivo con servidor y Supabase reales: TA011_MODO, TA011_BASE_URL, TA011_SERVER_LOG).
Con HU007_EVIDENCIA=<carpeta> cada caso guarda su JSON en <carpeta>/logs.
"""
import glob
import json
import re
import time
from pathlib import Path

import pytest

from tests.security.test_ta011_session_authz import (
    CASO_OTRO, CASO_SA, FIXTURES, ID_INEXISTENTE, MENSAJES_SA, NOT_FOUND, PROHIBIDO, SERVER_LOG, VIVO,
    _leer_log_desde, _mundo_local, _mundo_vivo, fugas,
)

ROOT = Path(__file__).resolve().parents[3]
NOT_FINISHED = {"detail": "El reporte estará disponible al terminar la consulta."}
TRATAMIENTO = "Le indico paracetamol para el dolor"
DIAG_A = "Diagnóstico propuesto por A"
HYP_A = [{"name": "Hipótesis activa de A", "discarded": False, "reason": ""},
         {"name": "Hipótesis descartada de A", "discarded": True, "reason": "no encaja con la exploración"}]
KEYS = {"case_id", "finished_at", "patient", "chief_complaint", "diagnosis", "hypotheses", "differentials", "score",
        "key_questions", "tests", "treatment", "revealed_evidence", "recommendations"}
EVIDENCE_ID = re.compile(r"\b[A-Z]{3}-\d{3}\.[a-z_]+\.[a-z0-9_]+")


def _caso_json(case_id: str) -> dict:
    path = FIXTURES / f"{case_id}.json"
    if not path.exists():
        path = ROOT / "data" / "cases" / "curated" / f"{case_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _iniciales(case: dict) -> set[str]:
    public = case["public"]
    return {public["chief_complaint"]["evidence_id"], *(item["evidence_id"] for item in public.get("items", []))}


@pytest.fixture(scope="module")
def rep():
    mundo, limpiar = (_mundo_vivo if VIVO else _mundo_local)()
    try:
        sa = mundo.start(mundo.A)
        assert sa.status_code == 200, sa.text
        mundo.SA = sa.json()["session_id"]
        for text in [*MENSAJES_SA, TRATAMIENTO]:
            reply = mundo.call("POST", f"/api/ai/sessions/{mundo.SA}/message", mundo.A.headers(), {"message": text})
            assert reply.status_code == 200, reply.text
        # Consulta de A que sigue abierta: su reporte todavía no existe.
        so = mundo.start(mundo.A)
        assert so.status_code == 200, so.text
        mundo.extra["SO"] = so.json()["session_id"]
        finish = mundo.call("POST", f"/api/ai/sessions/{mundo.SA}/finish", mundo.A.headers(),
                            {"diagnosis": DIAG_A, "hypotheses": HYP_A, "confirmado": True})
        assert finish.status_code == 200, finish.text
        mundo.extra["finish_SA"] = finish
        for anon, attr in ((mundo.anon1, "SN1"), (mundo.anon2, "SN2")):
            start = mundo.start(anon, CASO_OTRO)
            assert start.status_code == 200, start.text
            setattr(mundo, attr, start.json()["session_id"])
            setattr(mundo, f"token_{attr}", start.json()["session_token"])
            closed = mundo.call("POST", f"/api/ai/sessions/{start.json()['session_id']}/finish",
                                anon.headers(start.json()["session_token"]), {"diagnosis": f"Diagnóstico de {anon.nombre}", "confirmado": True})
            assert closed.status_code == 200, closed.text
        case = _caso_json(CASO_SA)
        mundo.extra["case"] = case
        # Datos del reporte de A que no deben aparecer en ninguna respuesta denegada.
        mundo.marcadores = [mundo.SA, DIAG_A, case["protected"]["diagnosis"]["name"],
                            case["protected"]["treatment_reference"]["summary"][:60]]
        yield mundo
    finally:
        limpiar()


def _report(rep, session_id=None, quien=None, capacidad=None):
    quien = quien or rep.A
    return rep.call("GET", f"/api/ai/sessions/{session_id or rep.SA}/report", quien.headers(capacidad))


# ================================================== A. Solo el dueño y solo poscierre (CA1, CA2)


@pytest.mark.hu007(id="HU007-01", criterio="CA2, CA3", titulo="A obtiene el reporte de su consulta cerrada",
                   nombre="A_obtiene_reporte", esperado="200 con todas las secciones del reporte")
def test_01_a_obtiene_reporte(rep, caso):
    response = _report(rep)
    caso.paso(rep.A.nombre, response, {200}, "reporte de SA (cerrada)")
    data = response.json() if response.status_code == 200 else {}
    caso.comprobar("todas las secciones", set(data) == KEYS, f"faltan: {sorted(KEYS - set(data))}")
    caso.comprobar("case_id de la consulta", data.get("case_id") == CASO_SA, str(data.get("case_id")))
    caso.exigir()


@pytest.mark.hu007(id="HU007-02", criterio="CA2", titulo="El invitado obtiene su reporte con su credencial",
                   nombre="invitado_obtiene_reporte", esperado="200 con el reporte de SN1")
def test_02_invitado_obtiene_reporte(rep, caso):
    response = _report(rep, rep.SN1, rep.anon1, rep.token_SN1)
    caso.paso(rep.anon1.nombre + " + credencial de capacidad", response, {200}, "reporte de SN1")
    data = response.json() if response.status_code == 200 else {}
    caso.comprobar("case_id de SN1", data.get("case_id") == CASO_OTRO, str(data.get("case_id")))
    caso.comprobar("diagnóstico del invitado", data.get("diagnosis", {}).get("student") == f"Diagnóstico de {rep.anon1.nombre}")
    caso.exigir()


@pytest.mark.hu007(id="HU007-03", criterio="CA1", titulo="Consulta abierta: el reporte no existe",
                   nombre="consulta_abierta_409", esperado="409 sin diagnóstico de referencia ni preguntas clave")
def test_03_consulta_abierta(rep, caso):
    response = _report(rep, rep.extra["SO"])
    caso.paso(rep.A.nombre, response, {409}, "reporte de una consulta abierta de A")
    caso.comprobar("mensaje exacto", response.json() == NOT_FINISHED if response.status_code == 409 else False, response.text)
    reference = rep.extra["case"]["protected"]["diagnosis"]["name"]
    for marca in (reference, "key_questions", "treatment", "reference"):
        caso.comprobar(f"sin «{marca}»", marca not in response.text)
    caso.exigir()


@pytest.mark.hu007(id="HU007-04", criterio="CA2", titulo="B no obtiene el reporte de A",
                   nombre="B_sobre_reporte_A", esperado="404 sin datos del reporte de A")
def test_04_b_sobre_reporte(rep, caso):
    response = _report(rep, quien=rep.B)
    caso.paso(rep.B.nombre, response, {NOT_FOUND}, "reporte de SA")
    caso.comprobar("sin datos de A", not fugas(rep, response.text), f"encontrados: {fugas(rep, response.text)}")
    caso.exigir()


@pytest.mark.hu007(id="HU007-05", criterio="CA2", titulo="Invitado 2 no obtiene el reporte del invitado 1",
                   nombre="invitado2_sobre_SN1", esperado="404 con su propia credencial")
def test_05_invitado2_sobre_sn1(rep, caso):
    response = _report(rep, rep.SN1, rep.anon2, rep.token_SN2)
    caso.paso(rep.anon2.nombre + " + credencial de capacidad", response, {NOT_FOUND}, "reporte de SN1")
    caso.comprobar("sin el diagnóstico del invitado 1", f"Diagnóstico de {rep.anon1.nombre}" not in response.text)
    caso.exigir()


@pytest.mark.hu007(id="HU007-06", criterio="CA2", titulo="Sin credencial no hay reporte",
                   nombre="sin_credencial_401", esperado="401 en SA y SN1")
def test_06_sin_credencial(rep, caso):
    for session_id, etiqueta in ((rep.SA, "SA"), (rep.SN1, "SN1")):
        response = rep.call("GET", f"/api/ai/sessions/{session_id}/report")
        caso.paso("sin credencial", response, {401}, f"reporte de {etiqueta}")
        caso.comprobar(f"{etiqueta}: sin datos", not fugas(rep, response.text))
    caso.exigir()


@pytest.mark.hu007(id="HU007-07", criterio="CA2", titulo="Reporte ajeno igual a inexistente",
                   nombre="ajeno_igual_a_inexistente", esperado="Mismo código y mismo cuerpo")
def test_07_ajeno_igual_inexistente(rep, caso):
    ajeno = _report(rep, quien=rep.B)
    nada = _report(rep, ID_INEXISTENTE, rep.B)
    caso.paso(rep.B.nombre, ajeno, {NOT_FOUND}, "reporte de SA (ajena)")
    caso.paso(rep.B.nombre, nada, {NOT_FOUND}, "reporte de un UUID inexistente")
    caso.comprobar("mismo código", ajeno.status_code == nada.status_code, f"{ajeno.status_code} vs {nada.status_code}")
    caso.comprobar("mismo cuerpo", ajeno.text == nada.text)
    caso.exigir()


@pytest.mark.hu007(id="HU007-08", criterio="CA1, CA3", titulo="El reporte del cierre es el mismo y no cambia",
                   nombre="reporte_estable", esperado="finish.report igual a GET /report en tres lecturas")
def test_08_reporte_estable(rep, caso):
    finish = rep.extra["finish_SA"]
    caso.paso(rep.A.nombre, finish, {200}, "respuesta del cierre de SA (con el reporte)")
    lecturas = [_report(rep) for _ in range(3)]
    for i, response in enumerate(lecturas, 1):
        caso.paso(rep.A.nombre, response, {200}, f"lectura {i} del reporte")
    caso.comprobar("finish.report == GET /report", finish.json().get("report") == lecturas[0].json())
    caso.comprobar("tres lecturas idénticas", len({r.text for r in lecturas}) == 1)
    caso.exigir()


# ================================================== B. Contenido del reporte (CA3)


@pytest.mark.hu007(id="HU007-09", criterio="CA3", titulo="Propuesta del alumno y diagnóstico de referencia",
                   nombre="propuesta_y_referencia", esperado="Diagnóstico e hipótesis del primer cierre; referencia del caso")
def test_09_propuesta(rep, caso):
    otra = rep.call("POST", f"/api/ai/sessions/{rep.SA}/finish", rep.A.headers(),
                    {"diagnosis": "Cambio después del cierre", "hypotheses": [], "confirmado": True})
    caso.paso(rep.A.nombre, otra, {200}, "cerrar SA otra vez con otro diagnóstico",
              {"diagnosis": "Cambio después del cierre", "hypotheses": [], "confirmado": True})
    response = _report(rep)
    caso.paso(rep.A.nombre, response, {200}, "reporte de SA")
    data = response.json()
    reference = rep.extra["case"]["protected"]["diagnosis"]
    caso.comprobar("diagnóstico del alumno", data["diagnosis"]["student"] == DIAG_A, data["diagnosis"]["student"])
    caso.comprobar("hipótesis del alumno", data["hypotheses"] == HYP_A)
    caso.comprobar("diagnóstico de referencia", data["diagnosis"]["reference"] == reference["name"])
    caso.comprobar("sinónimos", data["diagnosis"]["synonyms"] == reference.get("synonyms", []))
    caso.comprobar("diferenciales del caso",
                   data["differentials"] == [d["name"] for d in rep.extra["case"]["protected"]["differentials"]])
    caso.exigir()


def _scored(case: dict) -> list[dict]:
    questions = case["protected"]["evaluation"]["key_questions"]
    initial = _iniciales(case)
    return [q for q in questions if not set(q["evidence_ids"]).issubset(initial)] or questions


@pytest.mark.hu007(id="HU007-10", criterio="CA3", titulo="Puntaje y preguntas clave cuadran",
                   nombre="puntaje", esperado="Pesos obtenidos = earned_weight; preguntas = las puntuables del caso")
def test_10_puntaje(rep, caso):
    response = _report(rep)
    caso.paso(rep.A.nombre, response, {200}, "reporte de SA")
    data = response.json()
    obtained, missing = data["key_questions"]["obtained"], data["key_questions"]["missing"]
    score = data["score"]
    caso.comprobar("earned_weight = suma de obtenidas", score["earned_weight"] == sum(q["weight"] for q in obtained))
    caso.comprobar("total_weight = obtenidas + faltantes",
                   score["total_weight"] == sum(q["weight"] for q in obtained + missing))
    caso.comprobar("preguntas = puntuables del caso",
                   sorted(q["id"] for q in obtained + missing) == sorted(q["id"] for q in _scored(rep.extra["case"])))
    evaluation = rep.extra["finish_SA"].json()["evaluation"]
    caso.comprobar("mismo puntaje que la evaluación del cierre", score["score"] == evaluation["score"],
                   f"{score['score']} vs {evaluation['score']}")
    caso.exigir()


@pytest.mark.hu007(id="HU007-11", criterio="CA3", titulo="Por qué de cada pregunta que faltó",
                   nombre="por_que", esperado="Tipo, crítico y diferenciales que ayudaba a descartar, del caso")
def test_11_por_que(rep, caso):
    response = _report(rep)
    caso.paso(rep.A.nombre, response, {200}, "reporte de SA")
    case = rep.extra["case"]["protected"]
    by_id = {q["id"]: q for q in case["evaluation"]["key_questions"]}
    for item in response.json()["key_questions"]["missing"]:
        source = by_id[item["id"]]
        expected = [d["name"] for d in case["differentials"]
                    if set(d.get("discard_evidence_ids", [])) & set(source["evidence_ids"])]
        caso.comprobar(f"{item['id']}: tipo", item["error_type"] == source["error_if_missing"])
        caso.comprobar(f"{item['id']}: crítico", item["critical"] == bool(source.get("critical")))
        caso.comprobar(f"{item['id']}: diferenciales", item["helps_discard"] == expected, str(item["helps_discard"]))
        caso.comprobar(f"{item['id']}: tiene por qué", bool(item["why"]))
    caso.nota(f"Preguntas que faltaron: {len(response.json()['key_questions']['missing'])}")
    caso.exigir()


@pytest.mark.hu007(id="HU007-12", criterio="CA3", titulo="Exámenes clasificados según el caso",
                   nombre="examenes", esperado="Pedidos y no pedidos según tests del caso y la evidencia pedida")
def test_12_examenes(rep, caso):
    state = rep.call("GET", f"/api/ai/sessions/{rep.SA}", rep.A.headers())
    caso.paso(rep.A.nombre, state, {200}, "estado de SA (evidencia revelada)")
    response = _report(rep)
    caso.paso(rep.A.nombre, response, {200}, "reporte de SA")
    case = rep.extra["case"]
    requested = set(state.json()["revealed_evidence_ids"]) - _iniciales(case)
    tests = response.json()["tests"]
    evidence = [e["evidence_id"] for e in case["on_request"]]
    for name in case["protected"]["evaluation"].get("tests", {}).get("recommended", []):
        match = next((e for e in evidence if e.rsplit(".", 1)[-1] == name or e.rsplit(".", 1)[-1].startswith(name + "_")), None)
        where = ("other_indications" if match is None else
                 "recommended_requested" if match in requested else "recommended_missing")
        names = tests[where] if where == "other_indications" else [t["name"] for t in tests[where]]
        expected = name.replace("_", " ").capitalize() if where == "other_indications" else name
        caso.comprobar(f"{name} en {where}", expected in names)
    caso.exigir()


@pytest.mark.hu007(id="HU007-13", criterio="CA3", titulo="Tratamiento propuesto y de referencia",
                   nombre="tratamiento", esperado="La propuesta de A con sus alertas y el tratamiento de referencia del caso")
def test_13_tratamiento(rep, caso):
    events = rep.call("GET", f"/api/ai/sessions/{rep.SA}/events", rep.A.headers())
    caso.paso(rep.A.nombre, events, {200}, "eventos de SA")
    response = _report(rep)
    caso.paso(rep.A.nombre, response, {200}, "reporte de SA")
    treatment = response.json()["treatment"]
    turn = next(e for e in events.json() if e.get("student_message") == TRATAMIENTO)
    caso.comprobar("la propuesta se reconoció como tratamiento", turn.get("intent") == "propose_treatment", str(turn.get("intent")))
    caso.comprobar("propuesta con sus alertas",
                   {"message": TRATAMIENTO, "alerts": turn.get("safety_alerts", [])} in treatment["proposed"])
    reference = rep.extra["case"]["protected"]["treatment_reference"]
    caso.comprobar("resumen de referencia", treatment["reference_summary"] == reference["summary"])
    caso.comprobar("acciones clave", treatment["key_actions"] == reference.get("key_actions", []))
    caso.exigir()


@pytest.mark.hu007(id="HU007-14", criterio="CA3", titulo="Evidencia revelada",
                   nombre="evidencia_revelada", esperado="Los mismos datos que la consulta reveló, con su texto del caso")
def test_14_evidencia(rep, caso):
    state = rep.call("GET", f"/api/ai/sessions/{rep.SA}", rep.A.headers())
    caso.paso(rep.A.nombre, state, {200}, "estado de SA")
    response = _report(rep)
    caso.paso(rep.A.nombre, response, {200}, "reporte de SA")
    revealed = response.json()["revealed_evidence"]
    case = rep.extra["case"]
    def texto(item):
        return item.get("text") or f"{item.get('value')} {item.get('unit')}"
    texts = {case["public"]["chief_complaint"]["evidence_id"]: case["public"]["chief_complaint"]["text"],
             **{i["evidence_id"]: texto(i) for i in case["public"].get("items", [])},
             **{i["evidence_id"]: texto(i) for i in case["on_request"]}}
    caso.comprobar("mismos ids y orden", [r["evidence_id"] for r in revealed] == state.json()["revealed_evidence_ids"])
    caso.comprobar("texto del caso", all(r["text"] == texts.get(r["evidence_id"]) for r in revealed))
    caso.nota(f"Datos revelados: {len(revealed)}")
    caso.exigir()


@pytest.mark.hu007(id="HU007-15", criterio="CA4", titulo="Ninguna fuente ajena al case_id",
                   nombre="sin_fuentes_ajenas", esperado="Ids solo del caso; ningún diagnóstico ni diferencial de otro caso")
def test_15_sin_fuentes_ajenas(rep, caso):
    response = _report(rep)
    caso.paso(rep.A.nombre, response, {200}, "reporte de SA")
    text = json.dumps(response.json(), ensure_ascii=False)
    ajenos = sorted({eid for eid in EVIDENCE_ID.findall(text) if not eid.startswith(CASO_SA + ".")})
    caso.comprobar("ids de evidencia del caso", not ajenos, f"ajenos: {ajenos}")
    propios = {rep.extra["case"]["protected"]["diagnosis"]["name"],
               *(d["name"] for d in rep.extra["case"]["protected"]["differentials"])}
    otros = set()
    for path in glob.glob(str(ROOT / "data" / "cases" / "curated" / "*.json")):
        other = json.loads(Path(path).read_text(encoding="utf-8"))
        if other["case_id"] != CASO_SA:
            otros |= {other["protected"]["diagnosis"]["name"], *(d["name"] for d in other["protected"]["differentials"])}
    encontrados = sorted(n for n in otros - propios if n in text)
    caso.comprobar("sin diagnósticos ni diferenciales de otros casos", not encontrados, f"encontrados: {encontrados}")
    caso.nota(f"Nombres de otros casos revisados: {len(otros - propios)}")
    caso.exigir()


# ================================================== C. Errores y trazabilidad


@pytest.mark.hu007(id="HU007-16", criterio="CA2", titulo="Errores sin detalles internos",
                   nombre="errores_sin_detalles", esperado="401, 404 y 409 sin rutas, trazas, SQL ni claves")
def test_16_errores(rep, caso):
    respuestas = [("sin credencial", rep.call("GET", f"/api/ai/sessions/{rep.SA}/report"), {401}),
                  (rep.B.nombre, _report(rep, quien=rep.B), {NOT_FOUND}),
                  (rep.A.nombre, _report(rep, rep.extra["SO"]), {409}),
                  (rep.A.nombre, rep.call("GET", "/api/ai/sessions/no-es-un-uuid/report", rep.A.headers()), {NOT_FOUND})]
    for quien, response, esperado in respuestas:
        caso.paso(quien, response, esperado, f"GET {response.request.url.path}")
        encontrados = [p for p in PROHIBIDO if p in response.text]
        caso.comprobar(f"{response.status_code}: sin detalles internos", not encontrados, str(encontrados))
    caso.exigir()


@pytest.mark.logs_servidor
@pytest.mark.hu007(id="HU007-17", criterio="CA2", titulo="Intento ajeno sobre /report en el log",
                   nombre="log_reporte_ajeno", esperado="Línea [autorizacion] 404 GET .../report con quién y motivo")
def test_17_log(rep, caso, capsys):
    capsys.readouterr()
    offset = Path(SERVER_LOG).stat().st_size if VIVO else 0
    response = _report(rep, quien=rep.B)
    caso.paso(rep.B.nombre, response, {NOT_FOUND}, "reporte de SA")
    if VIVO:
        time.sleep(1.5)
        log = _leer_log_desde(offset)
    else:
        log = capsys.readouterr().out
    lineas = [line for line in log.splitlines() if "[autorizacion]" in line and "/report" in line]
    caso.comprobar("una línea [autorizacion] del intento", len(lineas) >= 1, f"líneas: {len(lineas)}")
    caso.comprobar("código 404 y motivo", any(" 404 " in line and "motivo=ajena" in line for line in lineas))
    caso.comprobar("quién (id de B)", any(rep.B.user_id in line for line in lineas))
    for line in lineas:
        caso.nota(line.strip())
    caso.exigir()
