import pytest

from server.persistence import AttemptStoreError, SupabaseAttempts, build_attempt
from tests.fakes_supabase import FakeSupabase

USER = "0b8f3c1e-5d4a-4f6b-9a1e-2c3d4e5f6a7b"


def _session(**extra):
    return {
        "session_id": "5af956e6-7820-461c-9d96-31bda9373aa6",
        "case_id": "MED-900",
        "started_at": "2026-10-14T10:00:00+00:00",
        "finished_at": "2026-10-14T10:12:30+00:00",
        "evaluation": {
            "score": 62.5,
            "completed_questions": 1,
            "total_questions": 2,
            "errors": {"negligencia": 0, "anamnesis_incompleta": 1, "razonamiento_clinico": 0},
        },
        "avatar_state": {"alerts": [{"code": "case_contraindication", "message": "Revisar."}]},
        **extra,
    }


@pytest.fixture
def fake():
    fake = FakeSupabase()
    fake.users["token-valido"] = USER
    return fake


def _attempts(fake):
    return SupabaseAttempts("https://proyecto.supabase.co/", "sb_publishable_prueba", "sb_secret_prueba",
                            client=fake.client())


def test_valid_access_token_returns_the_user_and_invalid_returns_none(fake):
    attempts = _attempts(fake)
    assert attempts.user_id("token-valido") == USER
    assert attempts.user_id("token-falso") is None
    # El token del alumno se comprueba con la clave publicable, nunca con la secreta.
    assert fake.requests[0].headers["apikey"] == "sb_publishable_prueba"


def test_attempt_row_uses_the_engine_score_and_no_protected_topics():
    row = build_attempt(
        user_id=USER,
        session=_session(),
        specialty="medicina_interna",
        diagnosis="Lupus",
        hypotheses=[{"name": "Lupus", "discarded": False, "reason": ""}],
    )
    assert row["usuario_id"] == USER
    assert row["caso_id"] == "MED-900"
    assert row["especialidad"] == "medicina_interna"
    assert row["puntaje"] == 62
    assert row["duracion_segundos"] == 750
    assert row["diagnostico"] == "Lupus"
    assert row["hipotesis"] == [{"name": "Lupus", "discarded": False, "reason": ""}]
    assert row["reporte"]["session_id"] == "5af956e6-7820-461c-9d96-31bda9373aa6"
    assert row["reporte"]["errors"]["anamnesis_incompleta"] == 1
    assert row["reporte"]["safety_alerts"] == ["case_contraindication"]
    assert "topic" not in str(row)


def test_save_inserts_with_the_secret_key_and_returns_the_id(fake):
    attempt_id = _attempts(fake).save({"usuario_id": USER, "caso_id": "MED-900", "puntaje": 62})
    assert attempt_id == "intento-1"
    assert fake.attempts[0]["usuario_id"] == USER
    assert fake.requests[-1].headers["apikey"] == "sb_secret_prueba"


def test_supabase_errors_are_reported(fake):
    fake.fail_with = 500
    with pytest.raises(AttemptStoreError):
        _attempts(fake).save({"usuario_id": USER})
    with pytest.raises(AttemptStoreError):
        _attempts(fake).user_id("token-valido")
