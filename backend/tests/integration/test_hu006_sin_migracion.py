"""HU-006 mientras falta la migración 0007: la consulta se cierra igual y el registro por intentos queda pendiente.

Si Supabase responde que diagnosticos_finales no existe (404, PGRST205), el diagnóstico queda en la consulta y en
el reporte final, sin número de intento. Cualquier otro fallo del registro sigue dejando la consulta abierta (503).
Cuando la tabla existe, el registro por intentos funciona sin cambiar nada.
"""
import pytest

from server.api import ai
from server.persistence import diagnoses
from server.persistence.diagnoses import DiagnosisStoreError, SupabaseDiagnoses
from tests.fakes_supabase import FakeSupabase
from tests.sprint2.conftest import api, start  # noqa: F401

CUERPO = {"diagnosis": "Hemofilia A", "confirmado": True}


@pytest.fixture
def supabase(api, monkeypatch):
    client, service, _ = api
    fake = FakeSupabase()
    store = SupabaseDiagnoses("https://fake.supabase.co", "sb_secret_fake", client=fake.client())
    def get_diagnoses():
        return store
    get_diagnoses.cache_clear = lambda: None  # el fixture de sprint2 lo limpia al terminar
    monkeypatch.setattr(ai, "get_diagnoses", get_diagnoses)
    return client, service, fake


def cerrar(client, sid, headers, cuerpo=CUERPO):
    return client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, json=cuerpo)


def test_tabla_inexistente_se_distingue_de_otros_fallos():
    fake = FakeSupabase()
    store = SupabaseDiagnoses("https://fake.supabase.co", "sb_secret_fake", client=fake.client())
    fake.fail_tables["diagnosticos_finales"] = "sin_tabla"
    missing = getattr(diagnoses, "DiagnosisTableMissing", None)
    assert missing is not None, "falta DiagnosisTableMissing"
    with pytest.raises(missing):
        store.by_session("6f1c2d3e-1111-4222-8333-444455556666")
    fake.fail_tables["diagnosticos_finales"] = 404
    with pytest.raises(DiagnosisStoreError) as error:
        store.by_session("6f1c2d3e-1111-4222-8333-444455556666")
    assert not isinstance(error.value, missing)


def test_sin_la_tabla_el_alumno_cierra_y_su_diagnostico_queda_en_el_reporte(supabase):
    client, service, fake = supabase
    fake.fail_tables["diagnosticos_finales"] = "sin_tabla"
    sid, headers = start(client, case_id="CIR-005", token="alumno-a")
    respuesta = cerrar(client, sid, headers)
    assert respuesta.status_code == 200, respuesta.text
    body = respuesta.json()
    assert body["registro"] == {"guardado": False, "motivo": "registro_pendiente"}
    assert body["phase"] == "finalizada" and body["report"]["diagnosis"]["student"] == "Hemofilia A"
    # Un segundo envío no cambia lo que quedó en la consulta.
    otra = cerrar(client, sid, headers, {"diagnosis": "Otra cosa distinta", "confirmado": True})
    assert otra.status_code == 200 and otra.json()["report"]["diagnosis"]["student"] == "Hemofilia A"
    assert not fake.diagnoses


@pytest.mark.parametrize("fallo", [500, 503, "sin_red"])
def test_otros_fallos_del_registro_siguen_dejando_la_consulta_abierta(supabase, fallo):
    client, service, fake = supabase
    fake.fail_tables["diagnosticos_finales"] = fallo
    sid, headers = start(client, case_id="CIR-005", token="alumno-a")
    respuesta = cerrar(client, sid, headers)
    assert respuesta.status_code == 503
    assert service.store.get(sid)["phase"] != "finalizada"


def test_con_la_tabla_el_registro_por_intentos_funciona(supabase):
    client, service, fake = supabase
    sid, headers = start(client, case_id="CIR-005", token="alumno-a")
    body = cerrar(client, sid, headers).json()
    assert body["registro"]["guardado"] and body["registro"]["numero_intento"] == 1
    assert len(fake.diagnoses) == 1


def test_el_invitado_no_cambia(supabase):
    client, service, fake = supabase
    fake.fail_tables["diagnosticos_finales"] = "sin_tabla"
    sid, headers = start(client, case_id="CIR-005")
    body = cerrar(client, sid, headers).json()
    assert body["registro"] == {"guardado": False, "motivo": "invitado"}
