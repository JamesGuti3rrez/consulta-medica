"""TA-012 contra Supabase real: cuenta y filas temporales, verificadas y eliminadas al terminar."""
from __future__ import annotations

import json
import secrets
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import httpx
from fastapi.testclient import TestClient

import server.api.ai as ai
from server.config import settings
from server.main import app
from server.orchestration.supabase_store import SupabaseSessionStore


def main():
    if not settings.supabase_url or not settings.supabase_secret_key or not settings.supabase_publishable_key:
        raise SystemExit("Faltan las credenciales de Supabase en .env.")
    output = ROOT / "pruebas/TA-012/supabase_real.json"
    report = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "supabase_real": True,
              "historial_habilitado_solo_en_prueba": True, "casos": [], "limpieza": {},
              "credenciales_incluidas": False, "resultado": "PENDIENTE"}
    base = settings.supabase_url.rstrip("/")
    headers = {"apikey": settings.supabase_secret_key}
    if not settings.supabase_secret_key.startswith("sb_"):
        headers["Authorization"] = "Bearer " + settings.supabase_secret_key
    http = httpx.Client(timeout=25)
    user_id, session_ids = None, []
    history_available = False
    original_settings, original_store = ai.settings, ai.STORE

    def request(method, path, *, label, **kwargs):
        response = http.request(method, base + path, headers=kwargs.pop("headers", headers), **kwargs)
        if response.is_error:
            raise RuntimeError(f"{label}: HTTP {response.status_code}")
        return response

    def check(condition, message):
        if not condition:
            raise RuntimeError(message)

    try:
        print("TA-012 | Validación contra Supabase REAL", flush=True)
        print("Se usan filas y cuenta temporales. No se modifican casos curados ni .env.", flush=True)
        for table, column in [("casos_curados", "case_id"), ("sma_sesiones", "session_id"),
                              ("sma_eventos", "id")]:
            request("GET", "/rest/v1/" + table, label="Comprobar tabla " + table,
                    params={"select": column, "limit": 0})
            print("[PASA] Tabla disponible: " + table, flush=True)
        history_check = http.get(base + '/rest/v1/intentos', headers=headers,
                                params={'select': 'id', 'limit': 0})
        history_available = history_check.is_success
        check(history_available or history_check.status_code == 404, 'No se pudo comprobar la tabla de historial.')
        report['historial_real_disponible'] = history_available
        report['historial_habilitado_solo_en_prueba'] = history_available
        if history_available:
            print('[PASA] Tabla disponible: intentos; historial habilitado solo para esta prueba.', flush=True)
        else:
            print('[INFO] Tabla intentos no instalada; historial desactivado. Se verifican sesiones y eventos reales.', flush=True)

        email = "ta012-" + uuid4().hex + "@example.com"
        password = secrets.token_urlsafe(32)
        user = request("POST", "/auth/v1/admin/users", label="Crear cuenta temporal",
                       json={"email": email, "password": password, "email_confirm": True,
                             "user_metadata": {"nombres": "Validación", "apellidos": "TA-012"}}).json()
        user_id = user["id"]
        check(user.get("email") == email, "La cuenta creada no coincide con la solicitud.")
        token = request("POST", "/auth/v1/token", label="Autenticar cuenta temporal",
                        params={"grant_type": "password"},
                        headers={"apikey": settings.supabase_publishable_key},
                        json={"email": email, "password": password}).json()["access_token"]
        print("[PASA] Cuenta temporal autenticada; no se enviaron correos.", flush=True)

        ai.settings = replace(settings, case_store="supabase", session_store="supabase",
                              history_enabled=history_available)
        ai.STORE = SupabaseSessionStore(settings.supabase_url, settings.supabase_secret_key)
        ai.get_service.cache_clear()
        ai.get_attempts.cache_clear()
        ai.get_session_auth.cache_clear()
        client = TestClient(app)
        auth = {"Authorization": "Bearer " + token}
        case = ai.get_service().repository.get_case("CIR-101")
        diagnosis = case["protected"]["diagnosis"]
        reference = diagnosis["name"]
        synonym = next(term for term in diagnosis["synonyms"] if term.casefold() != reference.casefold())
        matrix = [("correcto", reference, "correct", 100),
                  ("incorrecto", "Respuesta de control no admitida", "incorrect", 0),
                  ("sinonimo", synonym.upper(), "correct", 100),
                  ("vacio", "", "empty", 0),
                  ("ambiguo", reference + " o una alternativa no concluyente", "ambiguous", 0)]
        for name, value, expected_status, expected_score in matrix:
            start = client.post("/api/ai/sessions", headers=auth, json={"case_id": case["case_id"]})
            check(start.status_code == 200, f"{name}: inicio HTTP {start.status_code}")
            sid = start.json()["session_id"]
            session_ids.append(sid)
            opened = client.get(f"/api/ai/sessions/{sid}", headers=auth)
            check("diagnosis_evaluation" not in opened.json(), f"{name}: fuga de nota antes del cierre")
            before = client.get(f"/api/ai/sessions/{sid}/report", headers=auth)
            check(before.status_code == 409, f"{name}: el reporte previo no fue bloqueado")
            check(reference not in before.text, f"{name}: fuga de referencia antes del cierre")
            check(client.get(f"/api/ai/sessions/{sid}/report").status_code == 401,
                  f"{name}: reporte sin credencial no bloqueado")
            finished = client.post(f"/api/ai/sessions/{sid}/finish", headers=auth,
                                   json={"diagnosis": value, "hypotheses": []})
            check(finished.status_code == 200, f"{name}: cierre HTTP {finished.status_code}")
            body = finished.json()
            grade = body["diagnosis_evaluation"]
            check((grade["status"], grade["score"]) == (expected_status, expected_score),
                  f"{name}: calificación inesperada")
            if history_available:
                check(body["attempt"].get("saved") is True, f"{name}: intento no persistido")
            else:
                check(body['attempt'].get('reason') == 'desactivado', f'{name}: historial inesperadamente activo')
            saved = request("GET", "/rest/v1/sma_sesiones", label="Leer sesión persistida",
                            params={"session_id": "eq." + sid, "select": "state"}).json()
            check(saved[0]["state"]["diagnosis_evaluation"] == grade, f"{name}: sesión no coincide")
            if history_available:
                attempts = request("GET", "/rest/v1/intentos", label="Leer intento persistido",
                                   params={"id": "eq." + body["attempt"]["id"], "select": "reporte,diagnostico"}).json()
                check(attempts[0]["reporte"]["diagnosis_evaluation"] == grade, f"{name}: intento no coincide")
            events = request("GET", "/rest/v1/sma_eventos", label="Leer evento persistido",
                             params={"session_id": "eq." + sid, "select": "payload"}).json()
            check(any(row["payload"].get("diagnosis_evaluation") == grade for row in events),
                  f"{name}: falta la calificación en el evento de cierre")
            # Una instancia nueva debe reconstruir el reporte desde la sesión remota.
            ai.get_service.cache_clear()
            reread = client.get(f"/api/ai/sessions/{sid}/report", headers=auth)
            check(reread.status_code == 200 and reread.json()["diagnosis"]["grading"] == grade,
                  f"{name}: la lectura desde otra instancia no coincide")
            repeated = client.post(f"/api/ai/sessions/{sid}/finish", headers=auth,
                                   json={"diagnosis": "Texto cambiado en reintento"})
            check(repeated.json()["diagnosis_evaluation"] == grade, f"{name}: nota modificada al reintentar")
            if history_available:
                check(repeated.json()["attempt"]["id"] == body["attempt"]["id"], f"{name}: intento duplicado")
            report["casos"].append({"caso": name, "entrada": value, "estado": grade["status"],
                "puntuacion": grade["score"], "motivo": grade["reason"], "session_id": sid,
                "attempt_id": body["attempt"].get("id"), "sesion_real": True, "intento_real": history_available,
                "evento_real": True, "sin_fuga_previa": True, "lectura_nueva_instancia": True,
                "reintento_inmutable": True})
            print(f"[PASA] {name:10} HTTP 200 | {grade['status']:9} | {grade['score']:3}/100 "
                  "| persistencia real verificada", flush=True)
        report["resultado"] = "PASA"
        print("[PASA] 5/5 escenarios en Supabase real; bloqueo previo 409 y acceso anónimo 401.", flush=True)
    except Exception as exc:
        report["resultado"] = "FALLA"
        # Nunca imprimir cuerpos de Auth, contraseñas, claves ni tokens.
        report["error"] = str(exc)[:180] if isinstance(exc, RuntimeError) else type(exc).__name__
        print("[FALLA] " + report["error"], flush=True)
    finally:
        if user_id:
            try:
                # Los filtros se limitan al UUID recién creado y a las sesiones de esta ejecución.
                if history_available:
                    request("DELETE", "/rest/v1/intentos", label="Eliminar intentos temporales",
                            params={"usuario_id": "eq." + user_id})
                for sid in session_ids:
                    request("DELETE", "/rest/v1/sma_sesiones", label="Eliminar sesión temporal",
                            params={"session_id": "eq." + sid})
                    remaining = request("GET", "/rest/v1/sma_sesiones", label="Verificar limpieza de sesión",
                                        params={"session_id": "eq." + sid, "select": "session_id"}).json()
                    check(not remaining, "Quedó una sesión temporal.")
                    remaining_events = request("GET", "/rest/v1/sma_eventos", label="Verificar limpieza de eventos",
                                               params={"session_id": "eq." + sid, "select": "id"}).json()
                    check(not remaining_events, "Quedaron eventos temporales.")
                if history_available:
                    remaining_attempts = request("GET", "/rest/v1/intentos", label="Verificar limpieza de intentos",
                                                params={"usuario_id": "eq." + user_id, "select": "id"}).json()
                    check(not remaining_attempts, "Quedaron intentos temporales.")
                request("DELETE", "/auth/v1/admin/users/" + user_id, label="Eliminar cuenta temporal")
                deleted = http.get(base + "/auth/v1/admin/users/" + user_id, headers=headers)
                check(deleted.status_code == 404, "No se confirmó la eliminación de la cuenta temporal.")
                report["limpieza"] = {"cuenta_eliminada": True, "sesiones_eliminadas": len(session_ids),
                                      "eventos_eliminados": True, "intentos_eliminados": history_available}
                print(f"[PASA] Limpieza: cuenta temporal, {len(session_ids)} sesiones y sus eventos eliminados.", flush=True)
                if history_available:
                    print('[PASA] Intentos temporales eliminados.', flush=True)
            except Exception as exc:
                report["limpieza"]["error"] = str(exc)[:180] if isinstance(exc, RuntimeError) else type(exc).__name__
                report["resultado"] = "FALLA"
                print("[FALLA] No se confirmó toda la limpieza; revisar el registro JSON.", flush=True)
        ai.settings, ai.STORE = original_settings, original_store
        ai.get_service.cache_clear(); ai.get_attempts.cache_clear(); ai.get_session_auth.cache_clear()
        http.close()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Resultado final: " + report["resultado"] + ". Evidencia: pruebas/TA-012/supabase_real.json", flush=True)
    return 0 if report["resultado"] == "PASA" else 1


if __name__ == "__main__":
    raise SystemExit(main())

