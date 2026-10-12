import pytest

from server.orchestration import SessionNotFound, SessionStoreError, SupabaseSessionStore
from tests.fakes_supabase import FakeSupabase

SID = "5af956e6-7820-461c-9d96-31bda9373aa6"


def _state(**extra):
    return {"session_id": SID, "case_id": "MED-900", "phase": "presentacion", "history": [], **extra}


@pytest.fixture
def fake():
    return FakeSupabase()


def _store(fake, key="sb_secret_prueba"):
    return SupabaseSessionStore("https://proyecto.supabase.co/", key, client=fake.client())


def test_create_get_save_round_trip(fake):
    store = _store(fake)
    store.create(_state())
    state = store.get(SID)
    state["phase"] = "anamnesis"
    state["history"].append({"role": "student", "text": "¿Tiene alergias?"})
    store.save(state)

    saved = store.get(SID)
    assert saved["phase"] == "anamnesis"
    assert saved["history"] == [{"role": "student", "text": "¿Tiene alergias?"}]
    assert fake.sessions[SID]["phase"] == "anamnesis"
    assert fake.sessions[SID]["case_id"] == "MED-900"


def test_a_second_instance_sees_the_session(fake):
    """Lo que falló en Vercel: la sesión creada por una instancia debe existir para otra."""
    _store(fake).create(_state())
    assert _store(fake).get(SID)["case_id"] == "MED-900"


def test_events_keep_their_order(fake):
    store = _store(fake)
    store.create(_state())
    store.event(SID, {"type": "session_started"})
    store.event(SID, {"type": "turn", "agent": "paciente"})
    assert [e["type"] for e in store.events(SID)] == ["session_started", "turn"]


def test_unknown_or_invalid_session_is_not_found(fake):
    store = _store(fake)
    with pytest.raises(SessionNotFound):
        store.get(SID)
    with pytest.raises(SessionNotFound):
        store.get("no-es-un-uuid")
    with pytest.raises(SessionNotFound):
        store.save(_state())
    with pytest.raises(SessionNotFound):
        store.event(SID, {"type": "turn"})
    with pytest.raises(SessionNotFound):
        store.events(SID)
    assert not fake.requests or all("no-es-un-uuid" not in str(r.url) for r in fake.requests)


def test_supabase_errors_are_store_errors(fake):
    store = _store(fake)
    fake.fail_with = 500
    with pytest.raises(SessionStoreError):
        store.create(_state())


def test_secret_key_headers(fake):
    _store(fake).create(_state())
    request = fake.requests[-1]
    assert request.headers["apikey"] == "sb_secret_prueba"
    assert "authorization" not in request.headers
    assert str(request.url) == "https://proyecto.supabase.co/rest/v1/sma_sesiones"

    _store(fake, key="eyJ.jwt.antiguo").get(SID)
    assert fake.requests[-1].headers["authorization"] == "Bearer eyJ.jwt.antiguo"


def test_requires_url_and_key():
    with pytest.raises(ValueError):
        SupabaseSessionStore("", "sb_secret_prueba")
    with pytest.raises(ValueError):
        SupabaseSessionStore("https://proyecto.supabase.co", "")
