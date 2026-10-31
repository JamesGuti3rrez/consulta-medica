"""HU-006: registro del diagnóstico final por alumno, caso, sesión e intento, en memoria y en Supabase."""

import threading
import uuid

import httpx
import pytest

from server.persistence.diagnoses import (
    DIAGNOSES_TABLE, DiagnosisStoreError, InMemoryDiagnoses, SupabaseDiagnoses,
)
from tests.fakes_supabase import FakeSupabase

URL, SECRET = "https://proyecto-prueba.supabase.co", "sb_secret_prueba"
ALUMNO_A, ALUMNO_B = str(uuid.uuid4()), str(uuid.uuid4())
HYP = [{"name": "Colecistitis", "discarded": True, "reason": "Murphy negativo"}]
COLUMNS = {"id", "session_id", "usuario_id", "case_id", "numero_intento", "diagnostico", "hipotesis", "creado_en"}


def _sid() -> str:
    return str(uuid.uuid4())


@pytest.fixture(params=["memoria", "supabase"])
def store(request):
    if request.param == "memoria":
        return InMemoryDiagnoses()
    fake = FakeSupabase()
    store = SupabaseDiagnoses(URL, SECRET, client=fake.client())
    store.fake = fake
    return store


def _register(store, session_id=None, user=ALUMNO_A, case="EME-001", diagnosis="Apendicitis aguda", hypotheses=None):
    return store.register(session_id=session_id or _sid(), user_id=user, case_id=case,
                          diagnosis=diagnosis, hypotheses=HYP if hypotheses is None else hypotheses)


def test_first_diagnosis_is_attempt_one_with_every_key(store):
    session_id = _sid()
    record, created = _register(store, session_id)
    assert created is True
    assert record.numero_intento == 1
    assert (record.session_id, record.usuario_id, record.case_id) == (session_id, ALUMNO_A, "EME-001")
    assert record.diagnostico == "Apendicitis aguda"
    assert record.hipotesis == HYP
    assert record.id
    assert set(record.as_dict()) == COLUMNS


def test_attempts_are_counted_per_student_and_case(store):
    assert _register(store)[0].numero_intento == 1
    assert _register(store)[0].numero_intento == 2
    assert _register(store)[0].numero_intento == 3
    assert _register(store, case="CIR-005")[0].numero_intento == 1
    assert _register(store, user=ALUMNO_B)[0].numero_intento == 1
    assert _register(store)[0].numero_intento == 4


def test_the_same_session_is_registered_only_once(store):
    session_id = _sid()
    first, created = _register(store, session_id, diagnosis="Apendicitis aguda")
    again, created_again = _register(store, session_id, diagnosis="Otro diagnóstico distinto")
    assert created is True and created_again is False
    assert again == first
    assert again.diagnostico == "Apendicitis aguda"
    assert store.by_session(session_id) == first
    # El segundo envío no consumió un número de intento.
    assert _register(store)[0].numero_intento == 2


def test_unknown_session_has_no_record(store):
    assert store.by_session(_sid()) is None


def test_in_memory_concurrent_submissions_of_one_session_create_one_record():
    store = InMemoryDiagnoses()
    session_id = _sid()
    results = []
    barrier = threading.Barrier(20)

    def submit(i):
        barrier.wait()
        results.append(_register(store, session_id, diagnosis=f"Diagnóstico {i}"))

    threads = [threading.Thread(target=submit, args=(i,)) for i in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(created for _, created in results) == 1
    assert len({record.id for record, _ in results}) == 1


def test_in_memory_concurrent_sessions_get_distinct_attempt_numbers():
    store = InMemoryDiagnoses()
    barrier = threading.Barrier(10)
    numbers = []

    def submit():
        barrier.wait()
        numbers.append(_register(store)[0].numero_intento)

    threads = [threading.Thread(target=submit) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(numbers) == list(range(1, 11))


# ---------------------------------------------------------------- Supabase


def _supabase():
    fake = FakeSupabase()
    return fake, SupabaseDiagnoses(URL, SECRET, client=fake.client())


def test_supabase_inserts_only_the_registry_columns_with_the_secret_key():
    fake, store = _supabase()
    _register(store)
    insert = [r for r in fake.requests if r.method == "POST"][0]
    assert insert.url.path == f"/rest/v1/{DIAGNOSES_TABLE}"
    assert insert.headers["apikey"] == SECRET
    import json
    body = json.loads(insert.content)
    assert set(body) == {"session_id", "usuario_id", "case_id", "numero_intento", "diagnostico", "hipotesis"}


def test_supabase_lost_race_on_the_session_returns_the_winner():
    fake, store = _supabase()
    session_id = _sid()

    def other_request_wins(body):
        fake.before_diagnosis_insert = None
        fake.diagnoses.append({**body, "id": "diag-ganador", "diagnostico": "Diagnóstico del primer envío",
                               "creado_en": "2026-10-31T12:00:00+00:00"})

    fake.before_diagnosis_insert = other_request_wins
    record, created = _register(store, session_id, diagnosis="Diagnóstico del segundo envío")
    assert created is False
    assert record.id == "diag-ganador"
    assert record.diagnostico == "Diagnóstico del primer envío"


def test_supabase_lost_race_on_the_attempt_number_retries_with_the_next():
    fake, store = _supabase()

    def another_session_takes_the_number(body):
        fake.before_diagnosis_insert = None
        fake.diagnoses.append({**body, "session_id": _sid(), "id": "diag-otra", "creado_en": "2026-10-31T12:00:00+00:00"})

    fake.before_diagnosis_insert = another_session_takes_the_number
    record, created = _register(store)
    assert created is True
    assert record.numero_intento == 2


@pytest.mark.parametrize("status", [400, 401, 404, 500, 503])
def test_supabase_errors_raise_store_error(status):
    fake, store = _supabase()
    fake.fail_with = status
    with pytest.raises(DiagnosisStoreError):
        _register(store)


def test_supabase_network_failure_raises_store_error():
    def broken(request):
        raise httpx.ConnectError("sin red", request=request)

    store = SupabaseDiagnoses(URL, SECRET, client=httpx.Client(transport=httpx.MockTransport(broken)))
    with pytest.raises(DiagnosisStoreError):
        _register(store)
    with pytest.raises(DiagnosisStoreError):
        store.by_session(_sid())


def test_supabase_requires_url_and_secret():
    with pytest.raises(ValueError):
        SupabaseDiagnoses("", SECRET)
    with pytest.raises(ValueError):
        SupabaseDiagnoses(URL, "")


def test_supabase_rejects_a_session_id_that_is_not_a_uuid_without_calling_supabase():
    fake, store = _supabase()
    assert store.by_session("no-es-un-uuid") is None
    assert fake.requests == []
