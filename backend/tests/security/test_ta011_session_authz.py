"""TA-011: autorización de sesiones y eventos del simulador (/api/ai/sessions...).

Política verificada (pruebas/25_autorizacion_sesiones/02_politica_acceso.md):
- Sesión de un alumno registrado: solo su propio token de Supabase (Authorization: Bearer) la abre.
- Sesión de invitado: al crearla recibe una credencial de capacidad (session_token, 256 bits) que se envía
  en la cabecera X-Session-Token; solo quien la presenta abre esa sesión.
- Sin credencial o con credencial malformada o rechazada por Supabase: 401.
- Credencial válida pero de otra sesión: 404 con el mismo cuerpo que una sesión inexistente.
- Sesión cerrada: no admite mensajes (409); cerrar otra vez devuelve el mismo resultado.

Dos modos, mismos casos:
- TA011_MODO=local (por defecto): TestClient en proceso, Supabase Auth simulado (tests/fakes_supabase.py),
  caso de fixtures MED-900 y LLM local. Los casos marcados «vivo» se excluyen con -m "not vivo".
- TA011_MODO=vivo: servidor real en TA011_BASE_URL y el Supabase del .env. Crea dos alumnos temporales
  (alumno.prueba.*@example.com) y los borra al final. La clave secreta de Supabase SOLO se usa en la
  preparación y la limpieza (crear/borrar usuarios y borrar las sesiones creadas); ninguna petición de
  prueba la lleva.

Con TA011_EVIDENCIA=<carpeta> cada caso guarda su JSON en <carpeta>/logs (tokens enmascarados).
"""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path

import httpx
import pytest

from tests.security.ta011_evidencia import SECRETS, mask

MODO = os.getenv("TA011_MODO", "local")
VIVO = MODO == "vivo"
BASE_URL = os.getenv("TA011_BASE_URL", "").rstrip("/")
SERVER_LOG = os.getenv("TA011_SERVER_LOG", "")
# Encabezado opcional para un preview protegido de Vercel (x-vercel-protection-bypass).
VERCEL_BYPASS = os.getenv("TA011_VERCEL_BYPASS", "")
CASO_SA = os.getenv("TA011_CASO_SA", "EME-001" if VIVO else "MED-900")
CASO_OTRO = os.getenv("TA011_CASO_OTRO", "CIR-005" if VIVO else "MED-900")
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"

SESSION_HEADER = "X-Session-Token"
NOT_FOUND = 404
MENSAJES_SA = (
    ["¿Desde cuándo comenzó el dolor y cómo lo describiría?", "Solicito un hemograma y análisis de sangre"]
    if not VIVO else
    ["¿Desde cuándo comenzaron sus molestias y cómo las describiría?", "Solicito un hemograma completo"]
)
MENSAJE = "¿Tiene alergias a algún medicamento?"
ID_INEXISTENTE = str(uuid.uuid4())


@dataclass
class Identidad:
    nombre: str
    jwt: str | None = None
    user_id: str | None = None

    def headers(self, capacidad: str | None = None) -> dict:
        headers = {}
        if self.jwt:
            headers["Authorization"] = f"Bearer {self.jwt}"
        if capacidad:
            headers[SESSION_HEADER] = capacidad
        return headers


@dataclass
class Mundo:
    client: object
    A: Identidad
    B: Identidad
    anon1: Identidad
    anon2: Identidad
    SA: str = ""
    SB: str = ""
    SN1: str = ""
    SN2: str = ""
    token_SN1: str | None = None
    token_SN2: str | None = None
    marcadores: list[str] = field(default_factory=list)
    creadas: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def call(self, method: str, path: str, headers: dict | None = None, json_body=None, params=None):
        headers = dict(headers or {})
        if VERCEL_BYPASS:
            headers["x-vercel-protection-bypass"] = VERCEL_BYPASS
        response = self.client.request(method, path, headers=headers, json=json_body, params=params)
        if path == "/api/ai/sessions" and method == "POST" and response.status_code == 200:
            data = response.json()
            self.creadas.append(data.get("session_id", ""))
            SECRETS.add(data.get("session_token"))
        return response

    def start(self, quien: Identidad, case_id: str = CASO_SA, capacidad: str | None = None, extra_body=None):
        body = {"case_id": case_id, **(extra_body or {})}
        return self.call("POST", "/api/ai/sessions", quien.headers(capacidad), body)


def ops(session_id: str) -> list[tuple[str, str, dict | None, str]]:
    """Las cuatro operaciones que reciben un session_id (inventario, fase 0)."""
    base = f"/api/ai/sessions/{session_id}"
    return [
        ("GET", base, None, "leer sesión"),
        ("POST", f"{base}/message", {"message": MENSAJE}, "enviar mensaje"),
        ("GET", f"{base}/events", None, "listar eventos"),
        ("POST", f"{base}/finish", {"diagnosis": "intento ajeno", "hypotheses": []}, "cerrar sesión"),
    ]


def fugas(mundo: Mundo, text: str) -> list[str]:
    return [m for m in mundo.marcadores if m and m in text]


# ---------------------------------------------------------------- preparación de los dos modos


def _mundo_local():
    from fastapi.testclient import TestClient

    import server.api.ai as ai_module
    from server.ai.llm.gateway import LLMGateway
    from server.ai.llm.providers import LocalDevelopmentProvider
    from server.auth import SupabaseAuth
    from server.main import app
    from server.persistence import SupabaseAttempts
    from tests.fakes_supabase import FakeSupabase

    url, pub, sec = "https://proyecto-prueba.supabase.co", "sb_publishable_prueba", "sb_secret_prueba"
    fake = FakeSupabase()
    mp = pytest.MonkeyPatch()
    mp.setattr(ai_module, "CASES_DIR", FIXTURES)
    mp.setattr(ai_module, "settings", replace(
        ai_module.settings, rag_embedded_enabled=False, rag_service_url="", rag_backend="local",
        case_store="local", history_enabled=True, supabase_url=url, supabase_publishable_key=pub,
        supabase_secret_key=sec,
    ))
    mp.setattr(ai_module, "build_gateway", lambda: LLMGateway([LocalDevelopmentProvider()]))
    attempts = SupabaseAttempts(url, pub, sec, client=fake.client())
    mp.setattr(ai_module, "get_attempts", lambda: attempts)
    # Verificador de identidad de TA-011; antes del cambio no existe y no se usa.
    mp.setattr(ai_module, "get_session_auth", lambda: SupabaseAuth(url, pub, client=fake.client()), raising=False)
    ai_module.STORE.clear()
    ai_module.get_service.cache_clear()

    def usuario(nombre):
        jwt = "eyJhbGciOiJIUzI1NiJ9." + secrets.token_urlsafe(48) + "." + secrets.token_urlsafe(32)
        user_id = str(uuid.uuid4())
        fake.users[jwt] = user_id
        SECRETS.add(jwt)
        return Identidad(nombre, jwt, user_id)

    mundo = Mundo(
        client=TestClient(app, raise_server_exceptions=False),
        A=usuario("Usuario A (registrado)"), B=usuario("Usuario B (registrado)"),
        anon1=Identidad("Anónimo 1"), anon2=Identidad("Anónimo 2"),
    )
    mundo.extra.update(publishable=pub, supabase_url=url)

    def limpiar():
        ai_module.STORE.clear()
        ai_module.get_service.cache_clear()
        mp.undo()

    return mundo, limpiar


def _admin_headers(secret_key: str) -> dict:
    headers = {"apikey": secret_key, "Content-Type": "application/json"}
    if not secret_key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {secret_key}"
    return headers


def _mundo_vivo():
    from server.config import settings

    url, pub, sec = settings.supabase_url, settings.supabase_publishable_key, settings.supabase_secret_key
    assert BASE_URL and url and pub and sec, "El modo vivo necesita TA011_BASE_URL y Supabase en el .env"
    SECRETS.add(pub, sec)
    admin = httpx.Client(timeout=30, headers=_admin_headers(sec))  # solo preparación y limpieza
    creados: list[dict] = []

    def usuario(nombre, etiqueta):
        email = f"alumno.prueba.ta011.{etiqueta}.{secrets.token_hex(4)}@example.com"
        password = secrets.token_urlsafe(24)
        response = admin.post(f"{url}/auth/v1/admin/users", json={
            "email": email, "password": password, "email_confirm": True,
            "user_metadata": {"nombres": "Alumno", "apellidos": f"TA011 {etiqueta}"},
        })
        response.raise_for_status()
        user_id = response.json()["id"]
        creados.append({"id": user_id, "email": email, "password": password})
        login = httpx.post(f"{url}/auth/v1/token", params={"grant_type": "password"},
                           headers={"apikey": pub, "Content-Type": "application/json"},
                           json={"email": email, "password": password}, timeout=30)
        login.raise_for_status()
        jwt = login.json()["access_token"]
        SECRETS.add(jwt, password, login.json().get("refresh_token"))
        return Identidad(nombre, jwt, user_id)

    mundo = Mundo(
        client=httpx.Client(base_url=BASE_URL, timeout=180),
        A=usuario("Usuario A (registrado)", "a"), B=usuario("Usuario B (registrado)", "b"),
        anon1=Identidad("Anónimo 1"), anon2=Identidad("Anónimo 2"),
    )
    mundo.extra.update(publishable=pub, supabase_url=url, usuarios=creados)

    def limpiar():
        informe = {"sesiones_creadas": len(mundo.creadas), "usuarios_creados": len(creados)}
        ids = [sid for sid in mundo.creadas if sid]
        if ids:
            borradas = admin.delete(f"{url}/rest/v1/sma_sesiones", params={"session_id": f"in.({','.join(ids)})"},
                                    headers={"Prefer": "return=representation"})
            informe["sesiones_borradas_http"] = borradas.status_code
            informe["sesiones_borradas"] = len(borradas.json()) if borradas.is_success else 0
            quedan = admin.get(f"{url}/rest/v1/sma_sesiones",
                               params={"session_id": f"in.({','.join(ids)})", "select": "session_id"})
            informe["sesiones_que_quedan"] = len(quedan.json()) if quedan.is_success else f"HTTP {quedan.status_code}"
            eventos = admin.get(f"{url}/rest/v1/sma_eventos",
                                params={"session_id": f"in.({','.join(ids)})", "select": "id"})
            informe["eventos_que_quedan"] = len(eventos.json()) if eventos.is_success else f"HTTP {eventos.status_code}"
        borrados = 0
        for user in creados:
            if admin.delete(f"{url}/auth/v1/admin/users/{user['id']}").is_success:
                borrados += 1
        informe["usuarios_borrados"] = borrados
        intentos = admin.get(f"{url}/rest/v1/intentos", params={
            "usuario_id": f"in.({','.join(u['id'] for u in creados)})", "select": "id"})
        informe["intentos_que_quedan"] = len(intentos.json()) if intentos.is_success else f"HTTP {intentos.status_code}"
        informe["clave_secreta_usada_en"] = "solo preparación y limpieza (crear/borrar usuarios, borrar sesiones)"
        folder = os.getenv("TA011_EVIDENCIA")
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)
            (Path(folder) / "limpieza.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False), "utf-8")
        admin.close()

    return mundo, limpiar


@pytest.fixture(scope="module")
def mundo():
    mundo, limpiar = (_mundo_vivo if VIVO else _mundo_local)()
    try:
        sa = mundo.start(mundo.A)
        assert sa.status_code == 200, sa.text
        mundo.SA = sa.json()["session_id"]
        mundo.extra["inicio_SA"] = sa
        sb = mundo.start(mundo.B, CASO_OTRO)
        assert sb.status_code == 200, sb.text
        mundo.SB = sb.json()["session_id"]
        for anon, attr in ((mundo.anon1, "SN1"), (mundo.anon2, "SN2")):
            response = mundo.start(anon, CASO_OTRO)
            assert response.status_code == 200, response.text
            setattr(mundo, attr, response.json()["session_id"])
            setattr(mundo, f"token_{attr}", response.json().get("session_token"))
            mundo.extra[f"inicio_{attr}"] = response
        # Datos de SA que no deben aparecer en ninguna respuesta denegada (marcadores de fuga).
        revealed = set(sa.json().get("revealed_evidence_ids", []))
        for text in MENSAJES_SA:
            reply = mundo.call("POST", f"/api/ai/sessions/{mundo.SA}/message", mundo.A.headers(), {"message": text})
            assert reply.status_code == 200, reply.text
            revealed.update(reply.json().get("evidence_ids", []))
            mundo.extra.setdefault("mensajes_SA", []).append(reply)
        mundo.marcadores = [mundo.SA, *MENSAJES_SA, *sorted(revealed), mundo.A.user_id or ""]
        if CASO_SA != CASO_OTRO:
            mundo.marcadores.append(CASO_SA)
        yield mundo
    finally:
        limpiar()


def _snapshot(mundo: Mundo, session_id: str, quien: Identidad, capacidad: str | None = None) -> dict:
    state = mundo.call("GET", f"/api/ai/sessions/{session_id}", quien.headers(capacidad))
    events = mundo.call("GET", f"/api/ai/sessions/{session_id}/events", quien.headers(capacidad))
    return {
        "state": state,
        "events": events,
        "phase": state.json().get("phase") if state.status_code == 200 else None,
        "revealed": state.json().get("revealed_evidence_ids") if state.status_code == 200 else None,
        "n_events": len(events.json()) if events.status_code == 200 else None,
    }


def _denegar_todas(caso, mundo: Mundo, quien: Identidad, session_id: str, capacidad: str | None, esperado,
                   etiqueta: str, revisar_fugas: bool = True) -> list:
    responses = []
    for method, path, body, descripcion in ops(session_id):
        response = mundo.call(method, path, quien.headers(capacidad), body)
        caso.paso(quien.nombre + (" + credencial de capacidad" if capacidad else ""), response, esperado,
                  f"{descripcion} de {etiqueta}", body)
        if revisar_fugas:
            found = fugas(mundo, response.text)
            caso.comprobar(f"sin datos de SA en «{descripcion}»", not found, f"marcadores encontrados: {found}")
        responses.append(response)
    return responses


# ======================================================================= A. Positivos (CA1, CA4)


@pytest.mark.ta011(id="TA011-01", criterio="CA1, CA4", titulo="A crea sesión", nombre="A_crea_sesion",
                   esperado="200 y session_id UUID v4 (no secuencial); sin credencial de capacidad para registrados")
def test_01_a_crea_sesion(mundo, caso):
    response = mundo.extra["inicio_SA"]
    caso.paso(mundo.A.nombre, response, {200}, "crear SA con su token", {"case_id": CASO_SA})
    sid = response.json()["session_id"]
    parsed = uuid.UUID(sid)
    caso.comprobar("session_id es UUID versión 4 (aleatorio)", parsed.version == 4, f"versión {parsed.version}")
    caso.comprobar("el dueño (owner_id) no se devuelve al navegador", "owner_id" not in response.json())
    caso.comprobar("SA es distinto de SB", sid != mundo.SB)
    caso.exigir()


@pytest.mark.ta011(id="TA011-02", criterio="CA1, CA4", titulo="A lee SA", nombre="A_lee_SA",
                   esperado="200 con los datos de SA")
def test_02_a_lee_sa(mundo, caso):
    response = mundo.call("GET", f"/api/ai/sessions/{mundo.SA}", mundo.A.headers())
    caso.paso(mundo.A.nombre, response, {200}, "leer SA")
    if response.status_code == 200:
        caso.comprobar("devuelve SA", response.json()["session_id"] == mundo.SA)
        caso.comprobar("caso correcto", response.json()["case_id"] == CASO_SA)
    caso.exigir()


@pytest.mark.ta011(id="TA011-03", criterio="CA1, CA4", titulo="A envía mensaje a SA", nombre="A_mensaje_SA",
                   esperado="200 con la respuesta del agente")
def test_03_a_envia_mensaje(mundo, caso):
    for i, reply in enumerate(mundo.extra["mensajes_SA"], 1):
        caso.paso(mundo.A.nombre, reply, {200}, f"mensaje {i} de la preparación", {"message": MENSAJES_SA[i - 1]})
    response = mundo.call("POST", f"/api/ai/sessions/{mundo.SA}/message", mundo.A.headers(), {"message": MENSAJE})
    caso.paso(mundo.A.nombre, response, {200}, "mensaje 3", {"message": MENSAJE})
    if response.status_code == 200:
        caso.comprobar("responde un agente", bool(response.json().get("agent")))
    caso.exigir()


@pytest.mark.ta011(id="TA011-04", criterio="CA1, CA4", titulo="A lista eventos de SA", nombre="A_eventos_SA",
                   esperado="200 con sus eventos (inicio y turnos)")
def test_04_a_lista_eventos(mundo, caso):
    response = mundo.call("GET", f"/api/ai/sessions/{mundo.SA}/events", mundo.A.headers())
    caso.paso(mundo.A.nombre, response, {200}, "listar eventos de SA")
    if response.status_code == 200:
        types = [e.get("type") for e in response.json()]
        caso.comprobar("incluye session_started", "session_started" in types, str(types))
        caso.comprobar("al menos 2 turnos", types.count("turn") >= 2, str(types))
    caso.exigir()


@pytest.mark.ta011(id="TA011-05", criterio="CA1, CA4", titulo="Registrar evento (no aplica)",
                   nombre="A_registra_evento_no_aplica",
                   esperado="No existe ruta para registrar eventos: 405/404 y la lista de eventos no cambia")
def test_05_registrar_evento_no_existe(mundo, caso):
    caso.nota("Los eventos solo los genera el servidor al iniciar, en cada mensaje y al cerrar. "
              "No hay ruta que permita a un cliente escribirlos.")
    before = _snapshot(mundo, mundo.SA, mundo.A)
    body = {"type": "turn", "agent": "paciente", "evidence_ids": ["inventado"]}
    response = mundo.call("POST", f"/api/ai/sessions/{mundo.SA}/events", mundo.A.headers(), body)
    caso.paso(mundo.A.nombre, response, {404, 405}, "intentar escribir un evento", body)
    after = _snapshot(mundo, mundo.SA, mundo.A)
    caso.comprobar("la cantidad de eventos no cambia", before["n_events"] == after["n_events"],
                   f"{before['n_events']} -> {after['n_events']}")
    caso.exigir()


@pytest.mark.ta011(id="TA011-07", criterio="CA3", titulo="Anónimo 1 crea sesión y recibe credencial",
                   nombre="anonimo1_crea_sesion",
                   esperado="200 con session_token de al menos 128 bits (base64url >= 22 caracteres), único")
def test_07_anonimo_recibe_credencial(mundo, caso):
    response = mundo.extra["inicio_SN1"]
    caso.paso(mundo.anon1.nombre, response, {200}, "crear SN1 sin iniciar sesión", {"case_id": CASO_OTRO})
    token = mundo.token_SN1 or ""
    bits = len(token) * 6
    caso.comprobar("la respuesta trae session_token", bool(token))
    caso.comprobar("alfabeto base64url", bool(re.fullmatch(r"[A-Za-z0-9_-]+", token)), f"longitud {len(token)}")
    caso.comprobar("al menos 128 bits", bits >= 128, f"{len(token)} caracteres = {bits} bits")
    tokens = {token}
    for _ in range(3):
        extra = mundo.start(mundo.anon1, CASO_OTRO)
        caso.paso(mundo.anon1.nombre, extra, {200}, "crear otra sesión para comparar credenciales",
                  {"case_id": CASO_OTRO})
        tokens.add(extra.json().get("session_token") if extra.status_code == 200 else None)
    caso.comprobar("cuatro sesiones, cuatro credenciales distintas", len(tokens - {None, ""}) == 4,
                   f"distintas: {len(tokens - {None, ''})}")
    caso.comprobar("SN1 y SN2 tienen credenciales distintas", bool(token) and token != mundo.token_SN2)
    caso.exigir()


@pytest.mark.ta011(id="TA011-08", criterio="CA3, CA4", titulo="Anónimo 1 usa su credencial en SN1",
                   nombre="anonimo1_opera_SN1", esperado="200 en leer, mensaje, eventos y cierre de SN1")
def test_08_anonimo_opera_su_sesion(mundo, caso):
    for method, path, body, descripcion in ops(mundo.SN1):
        if path.endswith("/finish"):
            body = {"diagnosis": "Diagnóstico del invitado", "hypotheses": []}
        response = mundo.call(method, path, mundo.anon1.headers(mundo.token_SN1), body)
        caso.paso(mundo.anon1.nombre + " + credencial de capacidad", response, {200}, f"{descripcion} de SN1", body)
    state = mundo.call("GET", f"/api/ai/sessions/{mundo.SN1}", mundo.anon1.headers(mundo.token_SN1))
    caso.paso(mundo.anon1.nombre + " + credencial de capacidad", state, {200}, "SN1 queda finalizada")
    if state.status_code == 200:
        caso.comprobar("fase finalizada", state.json().get("phase") == "finalizada")
    caso.exigir()


@pytest.mark.ta011(id="TA011-09", criterio="CA1", titulo="Inventario completo de rutas con session_id",
                   nombre="inventario_rutas_openapi",
                   esperado="Solo existen las 4 rutas del inventario; no hay rutas extra (hipótesis, reporte, stream)")
def test_09_no_hay_rutas_adicionales(mundo, caso):
    response = mundo.call("GET", "/api/openapi.json")
    caso.paso("sin credencial (documento público de la API)", response, {200}, "leer el esquema OpenAPI")
    paths = response.json().get("paths", {}) if response.status_code == 200 else {}
    with_id = sorted(f"{m.upper()} {p}" for p, d in paths.items() if "{session_id}" in p for m in d)
    expected = sorted([
        "GET /api/ai/sessions/{session_id}", "POST /api/ai/sessions/{session_id}/message",
        "GET /api/ai/sessions/{session_id}/events", "POST /api/ai/sessions/{session_id}/finish",
        # HU-006: el reporte final, con la misma autorización.
        "GET /api/ai/sessions/{session_id}/report",
    ])
    caso.comprobar("rutas con {session_id} = inventario", with_id == expected, f"encontradas: {with_id}")
    caso.nota("Rutas con session_id: " + ", ".join(with_id))
    caso.exigir()


# ================================================ B. Acceso cruzado entre usuarios (CA1, CA2)


@pytest.mark.ta011(id="TA011-10", criterio="CA1, CA2", titulo="B sobre SA en cada operación",
                   nombre="B_sobre_SA", esperado="404 en leer, mensaje, eventos y cierre")
def test_10_b_sobre_sa(mundo, caso):
    mundo.extra["antes_de_B"] = _snapshot(mundo, mundo.SA, mundo.A)
    mundo.extra["respuestas_B"] = _denegar_todas(caso, mundo, mundo.B, mundo.SA, None, {NOT_FOUND}, "SA",
                                                 revisar_fugas=False)
    caso.exigir()


@pytest.mark.ta011(id="TA011-11", criterio="CA2", titulo="Respuestas a B sin datos de SA",
                   nombre="B_sin_fuga_de_SA", esperado="Ningún marcador de SA en los cuerpos devueltos a B")
def test_11_sin_fugas(mundo, caso):
    caso.nota("Marcadores de fuga de SA: session_id, case_id, textos de los mensajes, evidence_id revelados "
              "y user_id de A.")
    for response in mundo.extra.get("respuestas_B", []):
        caso.paso(mundo.B.nombre, response, {NOT_FOUND}, "respuesta recibida en TA011-10")
        found = fugas(mundo, response.text)
        caso.comprobar(f"sin marcadores en {response.request.method} {response.request.url.path}", not found,
                       f"encontrados: {found}")
    caso.exigir()


@pytest.mark.ta011(id="TA011-12", criterio="CA2", titulo="SA no cambia tras los intentos de B",
                   nombre="SA_intacta_tras_B", esperado="Mismos eventos, mismas evidencias y SA sigue abierta")
def test_12_sa_intacta(mundo, caso):
    before = mundo.extra["antes_de_B"]
    after = _snapshot(mundo, mundo.SA, mundo.A)
    caso.paso(mundo.A.nombre, after["state"], {200}, "A lee SA después de los intentos de B")
    caso.paso(mundo.A.nombre, after["events"], {200}, "A lista eventos de SA después de los intentos de B")
    caso.comprobar("misma cantidad de eventos", before["n_events"] == after["n_events"],
                   f"{before['n_events']} -> {after['n_events']}")
    caso.comprobar("mismas evidencias reveladas", before["revealed"] == after["revealed"])
    caso.comprobar("SA sigue abierta", after["phase"] not in (None, "finalizada"), f"fase: {after['phase']}")
    caso.exigir()


@pytest.mark.ta011(id="TA011-13", criterio="CA1, CA2", titulo="B intenta cerrar SA", nombre="B_cierra_SA",
                   esperado="404 y SA sigue abierta")
def test_13_b_no_cierra(mundo, caso):
    body = {"diagnosis": "cerrado por B", "hypotheses": []}
    response = mundo.call("POST", f"/api/ai/sessions/{mundo.SA}/finish", mundo.B.headers(), body)
    caso.paso(mundo.B.nombre, response, {NOT_FOUND}, "cerrar SA", body)
    caso.comprobar("sin datos de SA", not fugas(mundo, response.text))
    after = _snapshot(mundo, mundo.SA, mundo.A)
    caso.paso(mundo.A.nombre, after["state"], {200}, "A comprueba SA")
    caso.comprobar("SA sigue abierta", after["phase"] not in (None, "finalizada"), f"fase: {after['phase']}")
    caso.exigir()


@pytest.mark.ta011(id="TA011-14", criterio="CA2", titulo="SA ajena vs sesión inexistente",
                   nombre="ajena_igual_a_inexistente",
                   esperado="Mismo código y mismo cuerpo para SA (ajena) y para un UUID inexistente")
def test_14_no_enumeracion(mundo, caso):
    for (method, path, body, descripcion), (_, other, _, _) in zip(ops(mundo.SA), ops(ID_INEXISTENTE)):
        ajena = mundo.call(method, path, mundo.B.headers(), body)
        nada = mundo.call(method, other, mundo.B.headers(), body)
        caso.paso(mundo.B.nombre, ajena, {NOT_FOUND}, f"{descripcion} de SA (ajena)", body)
        caso.paso(mundo.B.nombre, nada, {NOT_FOUND}, f"{descripcion} de un UUID inexistente", body)
        caso.comprobar(f"{descripcion}: mismo código", ajena.status_code == nada.status_code,
                       f"{ajena.status_code} vs {nada.status_code}")
        caso.comprobar(f"{descripcion}: mismo cuerpo", ajena.text == nada.text)
    caso.exigir()


# ===================================================== C. Anónimos y credencial de capacidad (CA3)


@pytest.mark.ta011(id="TA011-15", criterio="CA3, CA2", titulo="Anónimo 2 con su credencial sobre SN1",
                   nombre="anonimo2_sobre_SN1", esperado="404 en las 4 operaciones, sin datos de SN1")
def test_15_anonimo2_sobre_sn1(mundo, caso):
    responses = _denegar_todas(caso, mundo, mundo.anon2, mundo.SN1, mundo.token_SN2, {NOT_FOUND}, "SN1",
                               revisar_fugas=False)
    for response in responses:
        caso.comprobar("sin el id de SN1 en la respuesta", mundo.SN1 not in response.text)
    caso.exigir()


@pytest.mark.ta011(id="TA011-16", criterio="CA3, CA2", titulo="Anónimo 1 con su credencial sobre SA",
                   nombre="anonimo1_sobre_SA", esperado="404 en las 4 operaciones, sin datos de SA")
def test_16_anonimo1_sobre_sa(mundo, caso):
    _denegar_todas(caso, mundo, mundo.anon1, mundo.SA, mundo.token_SN1, {NOT_FOUND}, "SA")
    caso.exigir()


@pytest.mark.ta011(id="TA011-17", criterio="CA3, CA2", titulo="A (registrado) sobre SN1 sin la credencial",
                   nombre="A_sobre_SN1", esperado="404 en las 4 operaciones")
def test_17_registrado_sobre_anonima(mundo, caso):
    responses = _denegar_todas(caso, mundo, mundo.A, mundo.SN1, None, {NOT_FOUND}, "SN1", revisar_fugas=False)
    for response in responses:
        caso.comprobar("sin el id de SN1 en la respuesta", mundo.SN1 not in response.text)
    caso.exigir()


def _alterar(token: str) -> str:
    middle = len(token) // 2
    return token[:middle] + ("A" if token[middle] != "A" else "B") + token[middle + 1:]


@pytest.mark.ta011(id="TA011-18", criterio="CA3, CA4", titulo="Credencial de SN1 alterada o malformada",
                   nombre="credencial_alterada",
                   esperado="Alterada en un carácter: 404 (decisión de la política); malformada: 401")
def test_18_credencial_alterada(mundo, caso):
    caso.nota("Decisión: una credencial bien formada pero que no corresponde a la sesión responde 404, igual "
              "que una sesión inexistente, para no ofrecer un oráculo. Las malformadas (largo o alfabeto "
              "incorrectos) responden 401 sin consultar la sesión.")
    token = mundo.token_SN1 or ""
    altered = _alterar(token) if token else "credencial-ausente"
    altered_sn2 = _alterar(mundo.token_SN2 or "x" * 43)
    SECRETS.add(altered, altered_sn2)
    response = mundo.call("GET", f"/api/ai/sessions/{mundo.SN2}", {SESSION_HEADER: altered_sn2})
    caso.paso(mundo.anon2.nombre + " (credencial alterada)", response, {NOT_FOUND}, "leer SN2 con su credencial alterada")
    response = mundo.call("GET", f"/api/ai/sessions/{mundo.SN1}", {SESSION_HEADER: altered})
    caso.paso(mundo.anon1.nombre + " (credencial alterada)", response, {NOT_FOUND}, "leer SN1 con la credencial alterada")
    for etiqueta, value in (("muy corta", "abc"), ("muy larga", "A" * 300), ("con espacios", "abc def ghi jkl mno pqr stu"),
                            ("caracteres no permitidos", "<script>alert(1)</script>" + "a" * 20)):
        response = mundo.call("GET", f"/api/ai/sessions/{mundo.SN2}", {SESSION_HEADER: value})
        caso.paso(f"credencial {etiqueta}", response, {401}, f"leer SN2 con credencial {etiqueta}")
        caso.comprobar(f"credencial {etiqueta}: sin datos de SN2", mundo.SN2 not in response.text)
    caso.exigir()


@pytest.mark.ta011(id="TA011-19", criterio="CA3", titulo="Credencial por query string",
                   nombre="credencial_en_query", esperado="401: la credencial solo se acepta en la cabecera")
def test_19_credencial_en_query(mundo, caso):
    token = mundo.token_SN2 or "sin-credencial"
    for param in ("token", "session_token", "access_token"):
        response = mundo.call("GET", f"/api/ai/sessions/{mundo.SN2}", params={param: token})
        caso.paso(f"{mundo.anon2.nombre} (credencial en ?{param}=)", response, {401}, f"leer SN2 con ?{param}=")
        caso.comprobar(f"?{param}= no da acceso", response.status_code != 200)
    caso.exigir()


@pytest.mark.ta011(id="TA011-20", criterio="CA3", titulo="Credencial de SN1 usada en otra sesión",
                   nombre="credencial_otra_sesion",
                   esperado="404 en SN2; crear sesión con ella da una sesión nueva con credencial propia")
def test_20_credencial_otra_sesion(mundo, caso):
    _denegar_todas(caso, mundo, mundo.anon1, mundo.SN2, mundo.token_SN1, {NOT_FOUND}, "SN2", revisar_fugas=False)
    new = mundo.start(mundo.anon1, CASO_OTRO, capacidad=mundo.token_SN1)
    caso.paso(mundo.anon1.nombre + " + credencial de SN1", new, {200}, "crear sesión presentando la credencial de SN1",
              {"case_id": CASO_OTRO})
    if new.status_code == 200:
        new_id, new_token = new.json()["session_id"], new.json().get("session_token")
        caso.comprobar("la sesión nueva tiene credencial propia", bool(new_token) and new_token != mundo.token_SN1)
        response = mundo.call("GET", f"/api/ai/sessions/{new_id}", {SESSION_HEADER: mundo.token_SN1 or ""})
        caso.paso(mundo.anon1.nombre + " + credencial de SN1", response, {NOT_FOUND},
                  "leer la sesión nueva con la credencial de SN1")
    caso.exigir()


# ===================================================== D. Credenciales inválidas (CA1, CA4)


@pytest.mark.ta011(id="TA011-21", criterio="CA1, CA4", titulo="Sin credencial en todas las rutas",
                   nombre="sin_credencial", esperado="401 en las 4 operaciones (SA, SN2 y UUID inexistente)")
def test_21_sin_credencial(mundo, caso):
    sin = Identidad("Sin credencial")
    for target, etiqueta in ((mundo.SA, "SA"), (mundo.SN2, "SN2"), (ID_INEXISTENTE, "UUID inexistente")):
        _denegar_todas(caso, mundo, sin, target, None, {401}, etiqueta)
    caso.exigir()


@pytest.mark.ta011(id="TA011-22", criterio="CA1, CA4", titulo="Token malformado «Bearer abc»",
                   nombre="bearer_malformado", esperado="401 en las 4 operaciones")
def test_22_token_malformado(mundo, caso):
    _denegar_todas(caso, mundo, Identidad("Bearer abc", jwt="abc"), mundo.SA, None, {401}, "SA")
    caso.exigir()


def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


@pytest.mark.ta011(id="TA011-23", criterio="CA1, CA4", titulo="JWT de A con la firma alterada",
                   nombre="jwt_firma_alterada", esperado="401 en las 4 operaciones")
def test_23_firma_alterada(mundo, caso):
    header, payload, signature = mundo.A.jwt.split(".")
    forged = ".".join([header, payload, _alterar(signature)])
    SECRETS.add(forged)
    if not VIVO:
        caso.nota("Modo local: Supabase Auth está simulado y rechaza cualquier token que no conoce. "
                  "La verificación real de la firma se prueba en el modo vivo.")
    _denegar_todas(caso, mundo, Identidad("A con firma alterada", jwt=forged), mundo.SA, None, {401}, "SA")
    caso.exigir()


@pytest.mark.ta011(id="TA011-24", criterio="CA1, CA4", titulo="JWT vencido o revocado",
                   nombre="jwt_vencido", esperado="401 en las 4 operaciones")
def test_24_jwt_vencido(mundo, caso):
    header, payload, signature = mundo.A.jwt.split(".")
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except ValueError:
        claims = {"sub": mundo.A.user_id, "role": "authenticated"}
    claims["exp"] = int(time.time()) - 3600
    expired = ".".join([header, _b64(claims), signature])
    SECRETS.add(expired)
    caso.nota("Sin la clave de firma del proyecto no se puede emitir un JWT vencido con firma válida: se usa "
              "el JWT de A con exp una hora en el pasado (la firma deja de coincidir).")
    _denegar_todas(caso, mundo, Identidad("A con exp vencido", jwt=expired), mundo.SA, None, {401}, "SA")
    if VIVO:
        # Sesión revocada: A inicia sesión otra vez, la cierra y se usa ese token.
        from server.config import settings

        user = mundo.extra["usuarios"][0]
        login = httpx.post(f"{settings.supabase_url}/auth/v1/token", params={"grant_type": "password"},
                           headers={"apikey": settings.supabase_publishable_key},
                           json={"email": user["email"], "password": user["password"]}, timeout=30)
        revoked = login.json()["access_token"]
        SECRETS.add(revoked, login.json().get("refresh_token"))
        logout = httpx.post(f"{settings.supabase_url}/auth/v1/logout", params={"scope": "local"},
                            headers={"apikey": settings.supabase_publishable_key, "Authorization": f"Bearer {revoked}"},
                            timeout=30)
        caso.comprobar("Supabase cerró la segunda sesión de A", logout.status_code in (200, 204),
                       f"HTTP {logout.status_code}")
        _denegar_todas(caso, mundo, Identidad("A con sesión revocada (logout)", jwt=revoked), mundo.SA, None,
                       {401}, "SA")
    caso.exigir()


@pytest.mark.ta011(id="TA011-25", criterio="CA1, CA4", titulo="Esquema de autorización incorrecto",
                   nombre="esquema_incorrecto", esperado="401 con «Basic», «Token» o sin esquema")
def test_25_esquema_incorrecto(mundo, caso):
    for scheme in ("Basic", "Token", ""):
        value = f"{scheme} {mundo.A.jwt}".strip()
        for method, path, body, descripcion in ops(mundo.SA)[:3]:
            response = mundo.call(method, path, {"Authorization": value}, body)
            caso.paso(f"A con esquema «{scheme or 'ninguno'}»", response, {401}, f"{descripcion} de SA", body)
    caso.exigir()


@pytest.mark.ta011(id="TA011-26", criterio="CA1, CA2", titulo="Solo la clave publicable de Supabase",
                   nombre="solo_anon_key", esperado="401: la clave publicable no identifica a ningún usuario")
def test_26_solo_anon_key(mundo, caso):
    pub = mundo.extra["publishable"]
    for headers, etiqueta in (({"Authorization": f"Bearer {pub}"}, "clave publicable como Bearer"),
                              ({"apikey": pub}, "clave publicable en apikey"),
                              ({"apikey": pub, "Authorization": f"Bearer {pub}"}, "ambas")):
        for method, path, body, descripcion in ops(mundo.SA):
            response = mundo.call(method, path, headers, body)
            caso.paso(etiqueta, response, {401}, f"{descripcion} de SA", body)
            caso.comprobar("sin datos de SA", not fugas(mundo, response.text))
    caso.exigir()


# ================================================ E. Manipulación de identificadores (IDOR)


@pytest.mark.ta011(id="TA011-27", criterio="CA1, CA2", titulo="session_id = SB dentro del cuerpo",
                   nombre="session_id_en_cuerpo", esperado="Se ignora: el mensaje va a SA y SB no recibe nada")
def test_27_session_id_en_cuerpo(mundo, caso):
    before = _snapshot(mundo, mundo.SB, mundo.B)
    caso.paso(mundo.B.nombre, before["events"], {200}, "B cuenta los eventos de SB antes")
    body = {"message": MENSAJE, "session_id": mundo.SB, "owner_id": mundo.B.user_id}
    response = mundo.call("POST", f"/api/ai/sessions/{mundo.SA}/message", mundo.A.headers(), body)
    caso.paso(mundo.A.nombre, response, {200}, "mensaje a SA con session_id = SB en el cuerpo", body)
    after = _snapshot(mundo, mundo.SB, mundo.B)
    caso.paso(mundo.B.nombre, after["events"], {200}, "B cuenta los eventos de SB después")
    caso.comprobar("SB no recibió eventos", before["n_events"] == after["n_events"],
                   f"{before['n_events']} -> {after['n_events']}")
    caso.exigir()


@pytest.mark.ta011(id="TA011-28", criterio="CA1, CA2", titulo="owner_id/user_id = A en el cuerpo de B",
                   nombre="owner_id_en_cuerpo", esperado="Se ignora: la sesión queda a nombre de B (A recibe 404)")
def test_28_owner_en_cuerpo(mundo, caso):
    body = {"case_id": CASO_OTRO, "owner_id": mundo.A.user_id, "user_id": mundo.A.user_id, "session_id": mundo.SA}
    response = mundo.call("POST", "/api/ai/sessions", mundo.B.headers(), body)
    caso.paso(mundo.B.nombre, response, {200}, "crear sesión con owner_id, user_id y session_id de A", body)
    if response.status_code == 200:
        new = response.json()["session_id"]
        caso.comprobar("no reutiliza el id de SA", new != mundo.SA)
        caso.paso(mundo.A.nombre, mundo.call("GET", f"/api/ai/sessions/{new}", mundo.A.headers()), {NOT_FOUND},
                  "A intenta leer la sesión creada por B")
        caso.paso(mundo.B.nombre, mundo.call("GET", f"/api/ai/sessions/{new}", mundo.B.headers()), {200},
                  "B lee su sesión")
    anon = mundo.start(mundo.anon2, CASO_OTRO, extra_body={"owner_id": mundo.A.user_id})
    caso.paso(mundo.anon2.nombre, anon, {200}, "invitado crea sesión con owner_id = A",
              {"case_id": CASO_OTRO, "owner_id": mundo.A.user_id})
    if anon.status_code == 200:
        caso.paso(mundo.A.nombre, mundo.call("GET", f"/api/ai/sessions/{anon.json()['session_id']}", mundo.A.headers()),
                  {NOT_FOUND}, "A intenta leer la sesión del invitado")
    state = mundo.call("GET", f"/api/ai/sessions/{mundo.SA}", mundo.A.headers())
    caso.paso(mundo.A.nombre, state, {200}, "SA sigue intacta para A")
    caso.exigir()


RAROS = [
    ("no es UUID", "no-es-uuid"),
    ("espacio", "%20"),
    ("muy largo (5000)", "a" * 5000),
    ("recorrido de ruta", "..%2F..%2F..%2Fetc%2Fpasswd"),
    ("inyección SQL", "1'%20OR%20'1'%3D'1"),
    ("UUID nulo", "00000000-0000-0000-0000-000000000000"),
    ("byte nulo", "%00"),
]


@pytest.mark.ta011(id="TA011-29", criterio="CA1, CA4", titulo="Identificadores con formatos raros",
                   nombre="ids_raros", esperado="4xx (400/401/404/405/414/422), nunca 500 ni datos")
def test_29_ids_raros(mundo, caso):
    allowed = {400, 401, 404, 405, 414, 422}
    for etiqueta, raw in RAROS:
        for method, suffix, body in (("GET", "", None), ("POST", "/message", {"message": MENSAJE})):
            response = mundo.call(method, f"/api/ai/sessions/{raw}{suffix}", mundo.A.headers(), body)
            caso.paso(mundo.A.nombre, response, allowed, f"{etiqueta}: {method} {suffix or 'leer'}", body)
            caso.comprobar(f"{etiqueta}: sin datos de SA", not fugas(mundo, response.text))
    response = mundo.call("POST", "/api/ai/sessions//message", mundo.A.headers(), {"message": MENSAJE})
    caso.paso(mundo.A.nombre, response, allowed, "id vacío", {"message": MENSAJE})
    caso.exigir()


# ============================================================== F. Estado de cierre


@pytest.mark.ta011(id="TA011-06", criterio="CA1, CA4", titulo="A cierra SA", nombre="A_cierra_SA",
                   esperado="200, fase finalizada y evaluación")
def test_06_a_cierra_sa(mundo, caso):
    body = {"diagnosis": "Diagnóstico de A", "hypotheses": [{"name": "Hipótesis de A", "discarded": False}]}
    response = mundo.call("POST", f"/api/ai/sessions/{mundo.SA}/finish", mundo.A.headers(), body)
    caso.paso(mundo.A.nombre, response, {200}, "cerrar SA", body)
    if response.status_code == 200:
        caso.comprobar("fase finalizada", response.json().get("phase") == "finalizada")
        caso.comprobar("trae evaluación", bool(response.json().get("evaluation")))
        mundo.extra["evaluacion_SA"] = response.json().get("evaluation")
    caso.exigir()


@pytest.mark.ta011(id="TA011-30", criterio="CA1", titulo="Mensaje a SA cerrada", nombre="mensaje_sesion_cerrada",
                   esperado="409 «La sesión ya finalizó.»")
def test_30_mensaje_cerrada(mundo, caso):
    before = _snapshot(mundo, mundo.SA, mundo.A)
    mundo.extra["eventos_cerrada"] = before["n_events"]
    response = mundo.call("POST", f"/api/ai/sessions/{mundo.SA}/message", mundo.A.headers(), {"message": MENSAJE})
    caso.paso(mundo.A.nombre, response, {409}, "mensaje a SA cerrada", {"message": MENSAJE})
    after = _snapshot(mundo, mundo.SA, mundo.A)
    caso.comprobar("no se agregan eventos", before["n_events"] == after["n_events"],
                   f"{before['n_events']} -> {after['n_events']}")
    caso.exigir()


@pytest.mark.ta011(id="TA011-31", criterio="CA1", titulo="Evento a SA cerrada", nombre="evento_sesion_cerrada",
                   esperado="Rechazado (no existe ruta de escritura de eventos) y la lista no cambia")
def test_31_evento_cerrada(mundo, caso):
    body = {"type": "turn", "agent": "paciente"}
    response = mundo.call("POST", f"/api/ai/sessions/{mundo.SA}/events", mundo.A.headers(), body)
    caso.paso(mundo.A.nombre, response, {404, 405}, "escribir evento en SA cerrada", body)
    after = _snapshot(mundo, mundo.SA, mundo.A)
    caso.paso(mundo.A.nombre, after["events"], {200}, "A lista los eventos de SA")
    caso.comprobar("la lista no cambia", after["n_events"] == mundo.extra.get("eventos_cerrada"),
                   f"{mundo.extra.get('eventos_cerrada')} -> {after['n_events']}")
    caso.exigir()


@pytest.mark.ta011(id="TA011-32", criterio="CA1", titulo="Cerrar dos veces", nombre="cerrar_dos_veces",
                   esperado="200 idempotente: misma evaluación, nunca 500")
def test_32_cerrar_dos_veces(mundo, caso):
    response = mundo.call("POST", f"/api/ai/sessions/{mundo.SA}/finish", mundo.A.headers(), {})
    caso.paso(mundo.A.nombre, response, {200}, "cerrar SA otra vez", {})
    if response.status_code == 200:
        caso.comprobar("misma evaluación", response.json().get("evaluation") == mundo.extra.get("evaluacion_SA"))
    caso.exigir()


@pytest.mark.ta011(id="TA011-33", criterio="CA2", titulo="B sobre SA cerrada", nombre="B_sobre_SA_cerrada",
                   esperado="404 en las 4 operaciones, sin datos de SA")
def test_33_b_sobre_cerrada(mundo, caso):
    _denegar_todas(caso, mundo, mundo.B, mundo.SA, None, {NOT_FOUND}, "SA cerrada")
    caso.exigir()


# ====================================================== G. Capa de datos (Supabase RLS)


def _rest(mundo, method, table, headers, params=None, json_body=None):
    url = f"{mundo.extra['supabase_url']}/rest/v1/{table}"
    return httpx.request(method, url, headers=headers, params=params, json=json_body, timeout=30)


def _rows(response) -> int:
    try:
        data = response.json()
    except ValueError:
        return 0
    return len(data) if isinstance(data, list) else 0


@pytest.mark.vivo
@pytest.mark.ta011(id="TA011-34", criterio="CA2", titulo="RLS: B lee las tablas de sesiones por REST",
                   nombre="rls_B_lee_tablas", esperado="0 filas (o permiso denegado) en sma_sesiones, sma_eventos e intentos")
def test_34_rls_lectura(mundo, caso):
    pub = mundo.extra["publishable"]
    headers = {"apikey": pub, "Authorization": f"Bearer {mundo.B.jwt}"}
    for table, params in (("sma_sesiones", {"session_id": f"eq.{mundo.SA}", "select": "*"}),
                          ("sma_eventos", {"session_id": f"eq.{mundo.SA}", "select": "*"}),
                          ("sma_sesiones", {"select": "*"}),
                          ("intentos", {"usuario_id": f"eq.{mundo.A.user_id}", "select": "*"})):
        response = _rest(mundo, "GET", table, headers, params)
        caso.paso(mundo.B.nombre + " (JWT directo a Supabase REST)", response, {200, 401, 403, 404},
                  f"GET {table} {params}")
        caso.comprobar(f"{table}: 0 filas", _rows(response) == 0, f"filas: {_rows(response)}")
    caso.exigir()


@pytest.mark.vivo
@pytest.mark.ta011(id="TA011-35", criterio="CA2", titulo="RLS: B modifica o borra SA por REST",
                   nombre="rls_B_modifica", esperado="0 filas afectadas y SA intacta para A")
def test_35_rls_escritura(mundo, caso):
    pub = mundo.extra["publishable"]
    headers = {"apikey": pub, "Authorization": f"Bearer {mundo.B.jwt}", "Prefer": "return=representation"}
    before = _snapshot(mundo, mundo.SA, mundo.A)
    patch = _rest(mundo, "PATCH", "sma_sesiones", headers, {"session_id": f"eq.{mundo.SA}"}, {"phase": "alterada_por_B"})
    caso.paso(mundo.B.nombre + " (JWT directo a Supabase REST)", patch, {200, 401, 403, 404}, "PATCH sma_sesiones SA",
              {"phase": "alterada_por_B"})
    caso.comprobar("PATCH: 0 filas afectadas", _rows(patch) == 0, f"filas: {_rows(patch)}")
    delete = _rest(mundo, "DELETE", "sma_eventos", headers, {"session_id": f"eq.{mundo.SA}"})
    caso.paso(mundo.B.nombre + " (JWT directo a Supabase REST)", delete, {200, 204, 401, 403, 404}, "DELETE sma_eventos SA")
    caso.comprobar("DELETE eventos: 0 filas afectadas", _rows(delete) == 0, f"filas: {_rows(delete)}")
    delete = _rest(mundo, "DELETE", "sma_sesiones", headers, {"session_id": f"eq.{mundo.SA}"})
    caso.paso(mundo.B.nombre + " (JWT directo a Supabase REST)", delete, {200, 204, 401, 403, 404}, "DELETE sma_sesiones SA")
    caso.comprobar("DELETE sesión: 0 filas afectadas", _rows(delete) == 0, f"filas: {_rows(delete)}")
    after = _snapshot(mundo, mundo.SA, mundo.A)
    caso.paso(mundo.A.nombre, after["state"], {200}, "A comprueba SA por la API")
    caso.comprobar("misma fase", before["phase"] == after["phase"], f"{before['phase']} -> {after['phase']}")
    caso.comprobar("mismos eventos", before["n_events"] == after["n_events"])
    caso.exigir()


@pytest.mark.vivo
@pytest.mark.ta011(id="TA011-36", criterio="CA2", titulo="RLS: solo la clave publicable",
                   nombre="rls_solo_anon_key", esperado="0 filas de cualquier usuario")
def test_36_rls_anon(mundo, caso):
    pub = mundo.extra["publishable"]
    for table in ("sma_sesiones", "sma_eventos", "intentos", "perfiles"):
        response = _rest(mundo, "GET", table, {"apikey": pub}, {"select": "*", "limit": "5"})
        caso.paso("solo clave publicable", response, {200, 401, 403, 404}, f"GET {table}")
        caso.comprobar(f"{table}: 0 filas", _rows(response) == 0, f"filas: {_rows(response)}")
    caso.exigir()


# ============================================= H. Respuestas de error y trazabilidad


PROHIBIDO = ["Traceback", 'File "', "psycopg", "postgres", "SELECT ", "sb_secret", "supabase.co",
             "C:\\", "/var/task", "backend/server", "site-packages"]


@pytest.mark.ta011(id="TA011-37", criterio="CA2, CA4", titulo="Errores sin detalles internos",
                   nombre="errores_sin_detalles",
                   esperado="Ningún error con stack trace, SQL, rutas internas, claves ni ids de otros usuarios")
def test_37_errores_limpios(mundo, caso):
    pruebas = [
        ("Sin credencial", "GET", f"/api/ai/sessions/{mundo.SA}", {}, None, {401}),
        (mundo.B.nombre, "GET", f"/api/ai/sessions/{mundo.SA}", mundo.B.headers(), None, {NOT_FOUND}),
        (mundo.B.nombre, "POST", f"/api/ai/sessions/{mundo.SA}/message", mundo.B.headers(), {"message": MENSAJE}, {NOT_FOUND}),
        (mundo.A.nombre, "POST", f"/api/ai/sessions/{mundo.SA}/message", mundo.A.headers(), {"message": MENSAJE}, {409}),
        (mundo.A.nombre, "POST", f"/api/ai/sessions/{mundo.SA}/message", mundo.A.headers(), {"message": "a"}, {401, 404, 409, 422}),
        (mundo.A.nombre, "GET", "/api/ai/sessions/1'%20OR%20'1'%3D'1", mundo.A.headers(), None, {400, 401, 404}),
        ("Bearer abc", "GET", f"/api/ai/sessions/{mundo.SA}", {"Authorization": "Bearer abc"}, None, {401}),
        ("Credencial malformada", "GET", f"/api/ai/sessions/{mundo.SN2}", {SESSION_HEADER: "abc"}, None, {401}),
        (mundo.A.nombre, "POST", "/api/ai/sessions", mundo.A.headers(), {"case_id": "NO-EXISTE"}, {404}),
    ]
    otros = [mundo.A.user_id, mundo.B.user_id]
    for quien, method, path, headers, body, expected in pruebas:
        response = mundo.call(method, path, headers, body)
        caso.paso(quien, response, expected, f"{method} {path[:80]}", body)
        found = [p for p in PROHIBIDO if p in response.text] + [u for u in otros if u and u in response.text]
        caso.comprobar(f"{method} {path[:60]}: sin detalles internos", not found, f"encontrado: {found}")
    caso.exigir()


@pytest.mark.ta011(id="TA011-38", criterio="CA2", titulo="CORS con origen no permitido",
                   nombre="cors_origen_ajeno",
                   esperado="Sin Access-Control-Allow-Origin: el navegador de otro sitio no puede leer la respuesta")
def test_38_cors(mundo, caso):
    origin = "https://sitio-malicioso.example"
    headers = {**mundo.A.headers(), "Origin": origin}
    response = mundo.call("GET", f"/api/ai/sessions/{mundo.SA}", headers)
    caso.paso(mundo.A.nombre + " desde otro origen", response, {200, 401, 403, 404}, "GET SA con Origin ajeno")
    caso.comprobar("sin Access-Control-Allow-Origin", "access-control-allow-origin" not in response.headers,
                   str(response.headers.get("access-control-allow-origin")))
    preflight = mundo.call("OPTIONS", f"/api/ai/sessions/{mundo.SA}", {
        "Origin": origin, "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization,x-session-token"})
    caso.paso("preflight desde otro origen", preflight, {400, 404, 405}, "OPTIONS (preflight CORS)")
    caso.comprobar("preflight sin Access-Control-Allow-Origin", "access-control-allow-origin" not in preflight.headers)
    caso.nota("La API no tiene CORSMiddleware: ningún origen distinto al del propio sitio puede leer respuestas "
              "desde el navegador. Un cliente fuera del navegador sigue necesitando la credencial.")
    caso.exigir()


def _leer_log_desde(offset: int) -> str:
    with open(SERVER_LOG, "rb") as handle:
        handle.seek(offset)
        return handle.read().decode("utf-8", errors="replace")


@pytest.mark.logs_servidor
@pytest.mark.ta011(id="TA011-39", criterio="CA1, CA2", titulo="Intentos denegados en el log del servidor",
                   nombre="log_de_denegados",
                   esperado="Línea [autorizacion] con quién, ruta y código; tokens solo enmascarados")
def test_39_log_denegados(mundo, caso, capsys):
    capsys.readouterr()
    offset = os.path.getsize(SERVER_LOG) if VIVO else 0
    probes = [
        (mundo.B.nombre, mundo.B.headers(), f"/api/ai/sessions/{mundo.SA}", NOT_FOUND),
        ("Sin credencial", {}, f"/api/ai/sessions/{mundo.SA}/events", 401),
        (mundo.anon2.nombre + " + credencial de capacidad", {SESSION_HEADER: mundo.token_SN2 or ""},
         f"/api/ai/sessions/{mundo.SN1}", NOT_FOUND),
    ]
    for quien, headers, path, code in probes:
        caso.paso(quien, mundo.call("GET", path, headers), {code}, f"intento denegado: GET {path}")
    if VIVO:
        time.sleep(1.5)
        log = _leer_log_desde(offset)
    else:
        log = capsys.readouterr().out
    lines = [line for line in log.splitlines() if "[autorizacion]" in line]
    caso.nota("Líneas del log del servidor:\n" + "\n".join(SECRETS.scrub(line) for line in lines))
    caso.comprobar("hay una línea por intento denegado", len(lines) >= len(probes), f"líneas: {len(lines)}")
    caso.comprobar("registra el código 404", any(" 404 " in f" {line} " for line in lines))
    caso.comprobar("registra el código 401", any(" 401 " in f" {line} " for line in lines))
    caso.comprobar("registra la ruta", any(mundo.SA in line for line in lines))
    caso.comprobar("registra quién (id de B)", any(mundo.B.user_id in line for line in lines))
    leaked = [mask(s) for s in SECRETS.values if any(s in line for line in lines)]
    caso.comprobar("ningún token completo en las líneas [autorizacion]", not leaked,
                   f"tokens completos encontrados: {leaked}")
    if VIVO:
        # Revisión del log completo del servidor (incluye el log de acceso de uvicorn, que guarda la URL).
        whole = _leer_log_desde(0)
        in_access = [mask(s) for s in SECRETS.values if s in whole]
        caso.nota(f"Tokens completos en el log completo del servidor: {len(in_access)} {in_access}. "
                  "Si aparecen, vienen de la URL registrada por el log de acceso (TA011-19 envía la "
                  "credencial en ?token= a propósito); la API no la acepta por query string.")
    caso.exigir()


@pytest.mark.ta011(id="TA011-40", criterio="CA1", titulo="Stream SSE/websocket (no aplica)",
                   nombre="stream_no_existe",
                   esperado="No hay stream de eventos: 404/405 al intentar conectar, con o sin credencial")
def test_40_stream(mundo, caso):
    caso.nota("La API no ofrece SSE ni websocket (ver TA011-09): los eventos solo se leen con GET /events.")
    for quien, headers in ((mundo.B.nombre, mundo.B.headers()), ("Sin credencial", {})):
        for suffix in ("/stream", "/events/stream", "/ws"):
            response = mundo.call("GET", f"/api/ai/sessions/{mundo.SA}{suffix}",
                                  {**headers, "Accept": "text/event-stream"})
            caso.paso(quien, response, {401, 404, 405}, f"conectar a SA{suffix}")
            caso.comprobar(f"{suffix}: sin datos de SA", not fugas(mundo, response.text))
        upgrade = mundo.call("GET", f"/api/ai/sessions/{mundo.SA}/ws",
                             {**headers, "Connection": "Upgrade", "Upgrade": "websocket",
                              "Sec-WebSocket-Version": "13", "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="})
        # Un servidor ASGI real (uvicorn) rechaza el websocket de una ruta inexistente con 403; TestClient no.
        caso.paso(quien, upgrade, {400, 401, 403, 404, 405}, "handshake websocket")
        caso.comprobar("no acepta el websocket (101)", upgrade.status_code != 101)
    caso.exigir()
