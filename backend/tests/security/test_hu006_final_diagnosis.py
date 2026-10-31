"""HU-006: proponer y registrar el diagnóstico final.

Criterios: CA1 campo obligatorio; CA2 validación de texto; CA3 confirmación de cierre; CA4 almacenamiento por
estudiante, case_id, sesión e intento; CA5 no exposición de protected; CA6 evitar doble envío; CA7 pruebas de fallo
y de acceso ajeno.

Usa la preparación de TA-011 (dos alumnos y dos invitados). En local: TestClient y Supabase simulado, con el registro
por la API REST de Supabase (SupabaseDiagnoses sobre el simulador). En vivo (TA011_MODO=vivo): servidor y Supabase
reales; las filas se leen con la clave secreta solo para comprobarlas. Los casos que inyectan fallos solo corren en
local. Con HU006_EVIDENCIA=<carpeta> cada caso guarda su JSON en <carpeta>/logs.
"""
import re
import threading
import time
import uuid

import httpx
import pytest

from tests.security.test_hu007_report import _caso_json
from tests.security.test_ta011_session_authz import (
    CASO_OTRO, CASO_SA, NOT_FOUND, VIVO, _admin_headers, _mundo_local, _mundo_vivo,
)

FINISH = "/api/ai/sessions/{}/finish"
DIAG = "Apendicitis aguda.\nJustificación: dolor migratorio a fosa ilíaca derecha."
HYP = [{"name": "Colecistitis", "discarded": True, "reason": "Murphy negativo"},
       {"name": "Apendicitis", "discarded": False, "reason": ""}]
CONFIRMAR = "Confirma el cierre de la consulta para registrar tu diagnóstico."
NO_REGISTRADO = "No se pudo registrar tu diagnóstico. La consulta sigue abierta: inténtalo de nuevo."
FALTA = "Escribe tu diagnóstico final antes de cerrar la consulta."
REGISTRO_KEYS = {"guardado", "id", "numero_intento"}
FILA_KEYS = {"id", "session_id", "usuario_id", "case_id", "numero_intento", "diagnostico", "hipotesis", "creado_en"}
solo_local = pytest.mark.skipif(VIVO, reason="inyecta fallos en el Supabase simulado: solo en local")


def _body(diagnosis=DIAG, confirmado=True, hypotheses=None, **extra):
    body = {"diagnosis": diagnosis, "hypotheses": HYP if hypotheses is None else hypotheses, **extra}
    if confirmado is not None:
        body["confirmado"] = confirmado
    return body


@pytest.fixture(scope="module")
def dx():
    mundo, limpiar = (_mundo_vivo if VIVO else _mundo_local)()
    mp = pytest.MonkeyPatch()
    try:
        if VIVO:
            from server.config import settings
            admin = httpx.Client(timeout=30, headers=_admin_headers(settings.supabase_secret_key))
            base = f"{settings.supabase_url}/rest/v1/diagnosticos_finales"

            def filas(**filtro):
                params = {k: f"eq.{v}" for k, v in filtro.items()} | {"select": "*", "order": "numero_intento"}
                response = admin.get(base, params=params)
                response.raise_for_status()
                return response.json()
        else:
            import server.api.ai as ai_module
            from server.persistence import SupabaseDiagnoses

            fake = mundo.extra["fake"]
            registry = SupabaseDiagnoses(mundo.extra["supabase_url"], mundo.extra["secret"], client=fake.client())
            # Antes del cambio get_diagnoses no existe y no se usa (raising=False).
            mp.setattr(ai_module, "get_diagnoses", lambda: registry, raising=False)

            def filas(**filtro):
                rows = [r for r in fake.diagnoses if all(str(r[k]) == str(v) for k, v in filtro.items())]
                return sorted(rows, key=lambda r: r["numero_intento"])

        mundo.extra["filas"] = filas
        case = _caso_json(CASO_SA)
        mundo.extra["case"] = case
        mundo.marcadores = [case["protected"]["diagnosis"]["name"],
                            case["protected"]["treatment_reference"]["summary"][:60]]
        yield mundo
    finally:
        mp.undo()
        limpiar()


def _nueva(dx, quien=None, case_id=CASO_SA):
    quien = quien or dx.A
    response = dx.start(quien, case_id)
    assert response.status_code == 200, response.text
    data = response.json()
    return data["session_id"], data.get("session_token")


def _cerrar(dx, session_id, quien=None, body=None, capacidad=None):
    quien = quien or dx.A
    return dx.call("POST", FINISH.format(session_id), quien.headers(capacidad), _body() if body is None else body)


def _fase(dx, session_id, quien=None, capacidad=None):
    response = dx.call("GET", f"/api/ai/sessions/{session_id}", (quien or dx.A).headers(capacidad))
    return response.json().get("phase") if response.status_code == 200 else f"HTTP {response.status_code}"


def _sin_protected(caso, dx, response):
    for marca in dx.marcadores:
        caso.comprobar(f"sin «{marca[:40]}»", marca not in response.text)
    # La consulta abierta trae "evaluation": null; lo que no puede aparecer es un valor en esas claves.
    for clave in ("protected", "evaluation", "report", "reference"):
        con_valor = re.search(rf'"{clave}"\s*:\s*(?!null)', response.text)
        caso.comprobar(f"sin valor en «{clave}»", con_valor is None, con_valor.group(0) if con_valor else "")


def _rechazo(caso, dx, session_id, response, mensaje, quien=None, capacidad=None):
    caso.comprobar("mensaje exacto", response.status_code == 422 and response.json() == {"detail": mensaje},
                   response.text[:300])
    caso.comprobar("la consulta sigue abierta", _fase(dx, session_id, quien, capacidad) != "finalizada",
                   str(_fase(dx, session_id, quien, capacidad)))
    caso.comprobar("no se registró nada", dx.extra["filas"](session_id=session_id) == [])
    _sin_protected(caso, dx, response)


# ================================================== A. Diagnóstico obligatorio (CA1)


@pytest.mark.hu006(id="HU006-01", criterio="CA1", titulo="Sin diagnóstico no se cierra",
                   nombre="sin_diagnostico_422", esperado="422 «Escribe tu diagnóstico...», consulta abierta, sin registro")
def test_01_sin_diagnostico(dx, caso):
    sid, _ = _nueva(dx)
    for body, desc in (({"confirmado": True}, "cuerpo sin diagnosis"), (_body(diagnosis=None), "diagnosis null"),
                       (None, "sin cuerpo")):
        response = dx.call("POST", FINISH.format(sid), dx.A.headers(), body) if body is not None else \
            dx.call("POST", FINISH.format(sid), dx.A.headers())
        caso.paso(dx.A.nombre, response, {422}, desc)
        _rechazo(caso, dx, sid, response, FALTA)
    caso.exigir()


@pytest.mark.hu006(id="HU006-02", criterio="CA1", titulo="Diagnóstico vacío o solo espacios no se acepta",
                   nombre="diagnostico_vacio_422", esperado="422 en cada texto vacío")
def test_02_diagnostico_vacio(dx, caso):
    sid, _ = _nueva(dx)
    for texto in ("", "   ", "\n\t\n", "  "):
        response = _cerrar(dx, sid, body=_body(diagnosis=texto))
        caso.paso(dx.A.nombre, response, {422}, f"diagnosis={texto!r}")
        _rechazo(caso, dx, sid, response, FALTA)
    caso.exigir()


# ================================================== B. Validación de texto (CA2)


INVALIDOS = [
    ("ab", "El diagnóstico debe tener al menos 3 letras."),
    ("12345 678", "El diagnóstico debe tener al menos 3 letras."),
    ("?!...", "El diagnóstico debe tener al menos 3 letras."),
    ("a" * 2001, "El diagnóstico no puede superar los 2000 caracteres."),
    ("Apendicitis\x00aguda", "El diagnóstico tiene caracteres no permitidos."),
    ("Apendicitis\x1b[31m", "El diagnóstico tiene caracteres no permitidos."),
    ("<script>alert(1)</script> apendicitis", "El diagnóstico no puede contener los signos < ni >."),
    ("Apendicitis <b>aguda</b>", "El diagnóstico no puede contener los signos < ni >."),
]


@pytest.mark.hu006(id="HU006-03", criterio="CA2", titulo="Textos inválidos se rechazan con su motivo",
                   nombre="textos_invalidos_422", esperado="422 con el motivo de cada uno; la consulta sigue abierta")
def test_03_textos_invalidos(dx, caso):
    sid, _ = _nueva(dx)
    for texto, mensaje in INVALIDOS:
        response = _cerrar(dx, sid, body=_body(diagnosis=texto))
        caso.paso(dx.A.nombre, response, {422}, f"diagnosis={texto[:40]!r}")
        _rechazo(caso, dx, sid, response, mensaje)
    caso.exigir()


@pytest.mark.hu006(id="HU006-04", criterio="CA2", titulo="Tipos incorrectos se rechazan",
                   nombre="tipos_incorrectos_422", esperado="422 si diagnosis o confirmado no tienen el tipo esperado")
def test_04_tipos_incorrectos(dx, caso):
    sid, _ = _nueva(dx)
    for body, desc in ((_body(diagnosis=12345), "diagnosis numérico"), (_body(diagnosis=["Apendicitis"]), "diagnosis lista"),
                       (_body(confirmado="quizás"), "confirmado texto"), (_body(hypotheses="no es lista"), "hipótesis texto")):
        response = _cerrar(dx, sid, body=body)
        caso.paso(dx.A.nombre, response, {422}, desc)
        caso.comprobar("la consulta sigue abierta", _fase(dx, sid) != "finalizada")
        caso.comprobar("no se registró nada", dx.extra["filas"](session_id=sid) == [])
    caso.exigir()


@pytest.mark.hu006(id="HU006-05", criterio="CA2, CA4", titulo="El texto válido se registra normalizado",
                   nombre="texto_normalizado", esperado="200; espacios sobrantes y líneas vacías repetidas se quitan")
def test_05_texto_normalizado(dx, caso):
    sid, _ = _nueva(dx)
    response = _cerrar(dx, sid, body=_body(diagnosis="   Apendicitis    aguda.\r\n\r\n\r\n\r\nJustificación:  dolor  "))
    caso.paso(dx.A.nombre, response, {200}, "texto con espacios sobrantes")
    filas = dx.extra["filas"](session_id=sid)
    caso.comprobar("una fila", len(filas) == 1, str(len(filas)))
    caso.comprobar("texto normalizado", bool(filas) and filas[0]["diagnostico"] == "Apendicitis aguda.\n\nJustificación: dolor",
                   repr(filas[0]["diagnostico"]) if filas else "")
    caso.exigir()


# ================================================== C. Confirmación de cierre (CA3)


@pytest.mark.hu006(id="HU006-06", criterio="CA3", titulo="Sin confirmación no se cierra",
                   nombre="sin_confirmacion_422", esperado="422 «Confirma el cierre...» sin confirmado o con false")
def test_06_sin_confirmacion(dx, caso):
    sid, _ = _nueva(dx)
    for body, desc in ((_body(confirmado=None), "sin el campo confirmado"), (_body(confirmado=False), "confirmado=false")):
        response = _cerrar(dx, sid, body=body)
        caso.paso(dx.A.nombre, response, {422}, desc)
        _rechazo(caso, dx, sid, response, CONFIRMAR)
    caso.exigir()


@pytest.mark.hu006(id="HU006-07", criterio="CA3", titulo="Tras un rechazo, la consulta sigue usable",
                   nombre="rechazo_y_sigue", esperado="422 y después la consulta responde mensajes y se cierra con 200")
def test_07_rechazo_y_sigue(dx, caso):
    sid, _ = _nueva(dx)
    caso.paso(dx.A.nombre, _cerrar(dx, sid, body=_body(confirmado=False)), {422}, "cierre sin confirmar")
    mensaje = dx.call("POST", f"/api/ai/sessions/{sid}/message", dx.A.headers(), {"message": "¿Tiene fiebre?"})
    caso.paso(dx.A.nombre, mensaje, {200}, "sigue preguntando")
    caso.paso(dx.A.nombre, _cerrar(dx, sid), {200}, "cierre confirmado")
    caso.comprobar("finalizada", _fase(dx, sid) == "finalizada")
    caso.exigir()


# ================================================== D. Registro por estudiante, caso, sesión e intento (CA4)


@pytest.mark.hu006(id="HU006-08", criterio="CA4", titulo="A registra su diagnóstico con su número de intento",
                   nombre="A_registra_intento", esperado="200; fila con alumno, case_id, sesión, intento, texto e hipótesis")
def test_08_registro(dx, caso):
    previos = len(dx.extra["filas"](usuario_id=dx.A.user_id, case_id=CASO_OTRO))
    sid, _ = _nueva(dx, case_id=CASO_OTRO)
    response = _cerrar(dx, sid)
    caso.paso(dx.A.nombre, response, {200}, "cierre confirmado")
    data = response.json() if response.status_code == 200 else {}
    registro = data.get("registro", {})
    caso.comprobar("registro con sus claves", set(registro) == REGISTRO_KEYS, str(registro))
    caso.comprobar("guardado", registro.get("guardado") is True)
    caso.comprobar("intento siguiente", registro.get("numero_intento") == previos + 1, str(registro.get("numero_intento")))
    filas = dx.extra["filas"](session_id=sid)
    caso.comprobar("una fila", len(filas) == 1, str(len(filas)))
    fila = filas[0] if filas else {}
    caso.comprobar("columnas de la fila", set(fila) == FILA_KEYS, str(sorted(fila)))
    caso.comprobar("usuario A", fila.get("usuario_id") == dx.A.user_id)
    caso.comprobar("case_id", fila.get("case_id") == CASO_OTRO, str(fila.get("case_id")))
    caso.comprobar("session_id", str(fila.get("session_id")) == sid)
    caso.comprobar("id del registro", str(fila.get("id")) == str(registro.get("id")))
    caso.comprobar("diagnóstico", fila.get("diagnostico") == DIAG)
    caso.comprobar("hipótesis", fila.get("hipotesis") == HYP, str(fila.get("hipotesis")))
    caso.comprobar("consulta finalizada", data.get("phase") == "finalizada")
    caso.exigir()


@pytest.mark.hu006(id="HU006-09", criterio="CA4", titulo="Los intentos se numeran por alumno y caso",
                   nombre="numeracion_de_intentos", esperado="A: 1, 2, 3 en el mismo caso; B empieza en 1")
def test_09_numeracion(dx, caso):
    previos = len(dx.extra["filas"](usuario_id=dx.A.user_id, case_id=CASO_SA))
    numeros = []
    for i in range(3):
        sid, _ = _nueva(dx)
        response = _cerrar(dx, sid, body=_body(diagnosis=f"Apendicitis aguda, intento {i + 1}"))
        caso.paso(dx.A.nombre, response, {200}, f"consulta {i + 1} de A en {CASO_SA}")
        numeros.append(response.json().get("registro", {}).get("numero_intento") if response.status_code == 200 else None)
    caso.comprobar("A: números consecutivos", numeros == [previos + 1, previos + 2, previos + 3], str(numeros))
    sid_b, _ = _nueva(dx, dx.B)
    response = _cerrar(dx, sid_b, dx.B)
    caso.paso(dx.B.nombre, response, {200}, f"primera consulta de B en {CASO_SA}")
    caso.comprobar("B: intento 1", response.json().get("registro", {}).get("numero_intento") == 1 if response.status_code == 200 else False)
    filas_a = dx.extra["filas"](usuario_id=dx.A.user_id, case_id=CASO_SA)
    caso.comprobar("filas de A sin huecos", [f["numero_intento"] for f in filas_a] == list(range(1, len(filas_a) + 1)),
                   str([f["numero_intento"] for f in filas_a]))
    caso.exigir()


@pytest.mark.hu006(id="HU006-10", criterio="CA4", titulo="El invitado cierra pero no se registra",
                   nombre="invitado_sin_registro", esperado="200 con registro guardado=false, motivo invitado; sin fila")
def test_10_invitado(dx, caso):
    sid, token = _nueva(dx, dx.anon1, CASO_OTRO)
    response = _cerrar(dx, sid, dx.anon1, capacidad=token)
    caso.paso(dx.anon1.nombre + " + credencial", response, {200}, "cierre confirmado del invitado")
    registro = response.json().get("registro") if response.status_code == 200 else None
    caso.comprobar("registro del invitado", registro == {"guardado": False, "motivo": "invitado"}, str(registro))
    caso.comprobar("sin fila", dx.extra["filas"](session_id=sid) == [])
    caso.comprobar("finalizada", _fase(dx, sid, dx.anon1, token) == "finalizada")
    caso.exigir()


@pytest.mark.hu006(id="HU006-11", criterio="CA1, CA2, CA3", titulo="El invitado también debe escribir y confirmar",
                   nombre="invitado_validado", esperado="422 sin diagnóstico y sin confirmación")
def test_11_invitado_validado(dx, caso):
    sid, token = _nueva(dx, dx.anon2, CASO_OTRO)
    for body, mensaje in ((_body(diagnosis="  "), FALTA), (_body(confirmado=False), CONFIRMAR)):
        response = _cerrar(dx, sid, dx.anon2, body, token)
        caso.paso(dx.anon2.nombre + " + credencial", response, {422}, mensaje)
        _rechazo(caso, dx, sid, response, mensaje, dx.anon2, token)
    caso.exigir()


# ================================================== E. Doble envío (CA6)


@pytest.mark.hu006(id="HU006-12", criterio="CA6", titulo="Un segundo envío no cambia el registro",
                   nombre="segundo_envio_igual", esperado="200 con el mismo registro; el texto nuevo no se guarda; una fila")
def test_12_segundo_envio(dx, caso):
    sid, _ = _nueva(dx)
    primero = _cerrar(dx, sid)
    caso.paso(dx.A.nombre, primero, {200}, "primer envío")
    segundo = _cerrar(dx, sid, body=_body(diagnosis="Colecistitis aguda (cambio de opinión)"))
    caso.paso(dx.A.nombre, segundo, {200}, "segundo envío con otro texto")
    r1 = primero.json().get("registro", {}) if primero.status_code == 200 else {}
    r2 = segundo.json().get("registro", {}) if segundo.status_code == 200 else {}
    caso.comprobar("mismo registro", r1 == r2 and r1.get("id"), f"{r1} / {r2}")
    filas = dx.extra["filas"](session_id=sid)
    caso.comprobar("una fila", len(filas) == 1, str(len(filas)))
    caso.comprobar("diagnóstico del primer envío", bool(filas) and filas[0]["diagnostico"] == DIAG)
    if primero.status_code == 200 and segundo.status_code == 200:
        caso.comprobar("misma evaluación", primero.json().get("evaluation") == segundo.json().get("evaluation"))
        reporte = segundo.json().get("report", {})
        caso.comprobar("el reporte muestra el primer diagnóstico", reporte.get("diagnosis", {}).get("student") == DIAG)
    caso.exigir()


@pytest.mark.hu006(id="HU006-13", criterio="CA6", titulo="Envíos simultáneos registran una sola vez",
                   nombre="envios_simultaneos", esperado="8 envíos a la vez: todos 200 con el mismo registro; una fila")
def test_13_simultaneos(dx, caso):
    sid, _ = _nueva(dx)
    respuestas = [None] * 8
    barrera = threading.Barrier(8)

    def enviar(i):
        barrera.wait()
        respuestas[i] = _cerrar(dx, sid, body=_body(diagnosis=f"Apendicitis aguda, envío {i}"))

    hilos = [threading.Thread(target=enviar, args=(i,)) for i in range(8)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    for i, response in enumerate(respuestas):
        caso.paso(dx.A.nombre, response, {200}, f"envío simultáneo {i}")
    ids = {r.json().get("registro", {}).get("id") for r in respuestas if r.status_code == 200}
    caso.comprobar("un solo id de registro", len(ids) == 1, str(ids))
    filas = dx.extra["filas"](session_id=sid)
    caso.comprobar("una fila", len(filas) == 1, str(len(filas)))
    if filas:
        reporte = dx.call("GET", f"/api/ai/sessions/{sid}/report", dx.A.headers()).json()
        caso.comprobar("el reporte muestra el texto registrado",
                       reporte.get("diagnosis", {}).get("student") == filas[0]["diagnostico"],
                       f"{reporte.get('diagnosis', {}).get('student')} / {filas[0]['diagnostico']}")
    caso.exigir()


@pytest.mark.hu006(id="HU006-14", criterio="CA2, CA6", titulo="Un envío inválido sobre una consulta cerrada no la altera",
                   nombre="invalido_tras_cierre", esperado="422 y el registro sigue igual")
def test_14_invalido_tras_cierre(dx, caso):
    sid, _ = _nueva(dx)
    caso.paso(dx.A.nombre, _cerrar(dx, sid), {200}, "cierre")
    response = _cerrar(dx, sid, body=_body(diagnosis="<b>x</b>"))
    caso.paso(dx.A.nombre, response, {422}, "envío inválido después del cierre")
    filas = dx.extra["filas"](session_id=sid)
    caso.comprobar("una fila sin cambios", len(filas) == 1 and filas[0]["diagnostico"] == DIAG)
    caso.exigir()


# ================================================== F. Fallos (CA7)


@solo_local
@pytest.mark.hu006(id="HU006-15", criterio="CA7", titulo="Si el registro falla, la consulta no se cierra",
                   nombre="registro_falla_503", esperado="503 «No se pudo registrar...»; abierta; sin evaluación; reintento 200")
def test_15_registro_falla(dx, caso):
    fake = dx.extra["fake"]
    sid, _ = _nueva(dx)
    for falla in (500, 503, "sin_red"):
        fake.fail_tables["diagnosticos_finales"] = falla
        try:
            response = _cerrar(dx, sid)
        finally:
            fake.fail_tables.pop("diagnosticos_finales", None)
        caso.paso(dx.A.nombre, response, {503}, f"Supabase: {falla}")
        caso.comprobar("mensaje exacto", response.status_code == 503 and response.json() == {"detail": NO_REGISTRADO},
                       response.text[:200])
        caso.comprobar("sigue abierta", _fase(dx, sid) != "finalizada")
        _sin_protected(caso, dx, response)
    reintento = _cerrar(dx, sid)
    caso.paso(dx.A.nombre, reintento, {200}, "reintento con Supabase disponible")
    caso.comprobar("una fila tras el reintento", len(dx.extra["filas"](session_id=sid)) == 1)
    caso.exigir()


@solo_local
@pytest.mark.hu006(id="HU006-16", criterio="CA6, CA7", titulo="Si falla el cierre después de registrar, el reintento no duplica",
                   nombre="cierre_falla_tras_registro", esperado="503; reintento 200 con el mismo registro; una fila")
def test_16_cierre_falla_tras_registro(dx, caso):
    import server.api.ai as ai_module
    from server.orchestration import SessionStoreError

    sid, _ = _nueva(dx)
    service = ai_module.get_service()
    original = service.store.save
    fallos = {"pendientes": 1}

    def save_que_falla(state):
        if state.get("session_id") == sid and state.get("phase") == "finalizada" and fallos["pendientes"]:
            fallos["pendientes"] -= 1
            raise SessionStoreError("Supabase respondió HTTP 500 en sma_sesiones (simulado)")
        return original(state)

    service.store.save = save_que_falla
    try:
        response = _cerrar(dx, sid)
    finally:
        service.store.save = original
    caso.paso(dx.A.nombre, response, {503}, "el registro se guarda, el cierre de la sesión falla")
    caso.comprobar("sigue abierta", _fase(dx, sid) != "finalizada")
    reintento = _cerrar(dx, sid, body=_body(diagnosis="Texto distinto en el reintento"))
    caso.paso(dx.A.nombre, reintento, {200}, "reintento")
    filas = dx.extra["filas"](session_id=sid)
    caso.comprobar("una fila", len(filas) == 1, str(len(filas)))
    caso.comprobar("vale el texto registrado primero", bool(filas) and filas[0]["diagnostico"] == DIAG)
    if reintento.status_code == 200:
        caso.comprobar("el reporte usa el registrado",
                       reintento.json().get("report", {}).get("diagnosis", {}).get("student") == DIAG)
    caso.exigir()


@pytest.mark.hu006(id="HU006-17", criterio="CA7", titulo="Consulta inexistente",
                   nombre="consulta_inexistente_404", esperado="404 y nada registrado")
def test_17_inexistente(dx, caso):
    sid = str(uuid.uuid4())
    response = _cerrar(dx, sid)
    caso.paso(dx.A.nombre, response, {NOT_FOUND}, "consulta que no existe")
    caso.comprobar("nada registrado", dx.extra["filas"](session_id=sid) == [])
    caso.exigir()


# ================================================== G. Acceso ajeno (CA7, CA5)


@pytest.mark.hu006(id="HU006-18", criterio="CA7", titulo="B no puede cerrar ni registrar en la consulta de A",
                   nombre="B_sobre_A_404", esperado="404; la consulta de A sigue abierta y sin registro")
def test_18_b_sobre_a(dx, caso):
    sid, _ = _nueva(dx)
    response = _cerrar(dx, sid, dx.B)
    caso.paso(dx.B.nombre, response, {NOT_FOUND}, "cierre de la consulta de A")
    caso.comprobar("A la ve abierta", _fase(dx, sid) != "finalizada")
    caso.comprobar("sin registro", dx.extra["filas"](session_id=sid) == [])
    _sin_protected(caso, dx, response)
    caso.paso(dx.A.nombre, _cerrar(dx, sid), {200}, "A la cierra después")
    filas = dx.extra["filas"](session_id=sid)
    caso.comprobar("el registro es de A", bool(filas) and filas[0]["usuario_id"] == dx.A.user_id)
    caso.exigir()


@pytest.mark.hu006(id="HU006-19", criterio="CA7", titulo="Sin credencial o con credencial inválida",
                   nombre="sin_credencial_401", esperado="401 sin credencial, con token malformado y con capacidad malformada")
def test_19_sin_credencial(dx, caso):
    sid, _ = _nueva(dx)
    for headers, desc in (({}, "sin credencial"), ({"Authorization": "Bearer no-es-un-jwt"}, "token malformado"),
                          ({"X-Session-Token": "corta"}, "capacidad malformada")):
        response = dx.call("POST", FINISH.format(sid), headers, _body())
        caso.paso("Anónimo", response, {401}, desc)
        _sin_protected(caso, dx, response)
    caso.comprobar("sigue abierta", _fase(dx, sid) != "finalizada")
    caso.comprobar("sin registro", dx.extra["filas"](session_id=sid) == [])
    caso.exigir()


@pytest.mark.hu006(id="HU006-20", criterio="CA7", titulo="Un invitado no cierra la consulta de otro invitado",
                   nombre="invitado2_sobre_invitado1", esperado="404 con su propia credencial; la otra sigue abierta")
def test_20_invitado_sobre_invitado(dx, caso):
    sid1, token1 = _nueva(dx, dx.anon1, CASO_OTRO)
    _, token2 = _nueva(dx, dx.anon2, CASO_OTRO)
    response = _cerrar(dx, sid1, dx.anon2, capacidad=token2)
    caso.paso(dx.anon2.nombre + " + su credencial", response, {NOT_FOUND}, "cierre de la consulta del invitado 1")
    caso.comprobar("sigue abierta", _fase(dx, sid1, dx.anon1, token1) != "finalizada")
    caso.exigir()


@pytest.mark.hu006(id="HU006-21", criterio="CA7", titulo="Un alumno no cierra la consulta de un invitado ni al revés",
                   nombre="alumno_e_invitado_cruzados", esperado="404 en ambos sentidos")
def test_21_cruzados(dx, caso):
    sid_inv, token = _nueva(dx, dx.anon1, CASO_OTRO)
    sid_a, _ = _nueva(dx)
    caso.paso(dx.A.nombre, _cerrar(dx, sid_inv), {NOT_FOUND}, "A sobre la consulta del invitado")
    caso.paso(dx.anon1.nombre + " + su credencial", _cerrar(dx, sid_a, dx.anon1, capacidad=token), {NOT_FOUND},
              "invitado sobre la consulta de A")
    caso.comprobar("sin registro en la de A", dx.extra["filas"](session_id=sid_a) == [])
    caso.exigir()


@pytest.mark.hu006(id="HU006-22", criterio="CA7", titulo="El dueño no se cambia por el cuerpo de la petición",
                   nombre="usuario_en_cuerpo", esperado="200; la fila queda a nombre del dueño, no del usuario_id enviado")
def test_22_usuario_en_cuerpo(dx, caso):
    sid, _ = _nueva(dx)
    response = _cerrar(dx, sid, body=_body(usuario_id=dx.B.user_id, case_id="OTRO-999", numero_intento=99,
                                           session_id=str(uuid.uuid4())))
    caso.paso(dx.A.nombre, response, {200}, "cuerpo con usuario_id, case_id, numero_intento y session_id ajenos")
    filas = dx.extra["filas"](session_id=sid)
    fila = filas[0] if filas else {}
    caso.comprobar("dueño A", fila.get("usuario_id") == dx.A.user_id)
    caso.comprobar("case_id de la consulta", fila.get("case_id") == CASO_SA)
    caso.comprobar("intento calculado por el servidor", fila.get("numero_intento") != 99, str(fila.get("numero_intento")))
    caso.exigir()


# ================================================== H. Sin protected (CA5)


@pytest.mark.hu006(id="HU006-23", criterio="CA5", titulo="La fila registrada no contiene protected",
                   nombre="fila_sin_protected", esperado="solo las columnas del registro, sin diagnóstico de referencia ni tratamiento")
def test_23_fila_sin_protected(dx, caso):
    sid, _ = _nueva(dx)
    caso.paso(dx.A.nombre, _cerrar(dx, sid), {200}, "cierre")
    filas = dx.extra["filas"](session_id=sid)
    texto = str(filas)
    caso.comprobar("columnas exactas", bool(filas) and set(filas[0]) == FILA_KEYS)
    for marca in dx.marcadores:
        caso.comprobar(f"sin «{marca[:40]}»", marca not in texto)
    caso.exigir()


@pytest.mark.hu006(id="HU006-24", criterio="CA5", titulo="Antes del cierre no hay protected ni registro",
                   nombre="antes_del_cierre", esperado="la consulta abierta no expone evaluación, reporte ni registro")
def test_24_antes_del_cierre(dx, caso):
    sid, _ = _nueva(dx)
    response = dx.call("GET", f"/api/ai/sessions/{sid}", dx.A.headers())
    caso.paso(dx.A.nombre, response, {200}, "leer la consulta abierta")
    _sin_protected(caso, dx, response)
    caso.comprobar("sin registro", '"registro"' not in response.text)
    caso.exigir()


@pytest.mark.hu006(id="HU006-25", criterio="CA4, CA5", titulo="El cierre responde solo lo necesario del registro",
                   nombre="respuesta_del_registro", esperado="registro con guardado, id y numero_intento; nada del usuario")
def test_25_respuesta(dx, caso):
    sid, _ = _nueva(dx)
    response = _cerrar(dx, sid)
    caso.paso(dx.A.nombre, response, {200}, "cierre")
    registro = response.json().get("registro", {}) if response.status_code == 200 else {}
    caso.comprobar("claves exactas", set(registro) == REGISTRO_KEYS, str(registro))
    caso.comprobar("sin el id del usuario", dx.A.user_id not in str(registro))
    caso.exigir()
