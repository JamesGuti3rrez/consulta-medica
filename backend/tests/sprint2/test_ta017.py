"""TA-017: propietario, capacidad, integridad y cierre por todas las rutas HTTP."""
from copy import deepcopy
import pytest

from .conftest import start, ask

TASK = "TA-017"
OPS = [("get", "", None), ("post", "/message", {"message": "¿Tiene alergias?"}),
       ("get", "/events", None), ("post", "/finish", {}), ("get", "/report", None)]


@pytest.mark.parametrize("method,suffix,body", OPS)
@pytest.mark.parametrize("identity,expected", [(None, 401), ("alumno-b", 404), ("rechazado", 401)])
def test_other_user_or_missing_credential_never_reads_or_mutates(api, method, suffix, body, identity, expected):
    client, service, _ = api
    sid, owner = start(client, token="alumno-a")
    before = deepcopy(service.store.get(sid))
    response = client.request(method, f"/api/ai/sessions/{sid}{suffix}", json=body,
        headers={"Authorization": "Bearer " + identity} if identity else {})
    assert response.status_code == expected
    assert service.store.get(sid) == before
    assert "Alberto" not in response.text and "carcinoma" not in response.text.lower()


@pytest.mark.parametrize("method,suffix,body", OPS)
def test_guest_token_of_another_session_is_rejected(api, method, suffix, body):
    client, service, _ = api
    sid, correct = start(client)
    _, other = start(client)
    before = deepcopy(service.store.get(sid))
    response = client.request(method, f"/api/ai/sessions/{sid}{suffix}", json=body, headers=other)
    assert response.status_code == 404
    assert service.store.get(sid) == before


@pytest.mark.parametrize("token", [None, "alumno-a"])
def test_owner_positive_path_and_guest_hash_only(api, token):
    client, service, _ = api
    sid, headers = start(client, token=token)
    assert client.get(f"/api/ai/sessions/{sid}", headers=headers).status_code == 200
    ask(client, sid, headers, "¿Qué alergias tiene?")
    assert len(client.get(f"/api/ai/sessions/{sid}/events", headers=headers).json()) == 2
    assert client.get(f"/api/ai/sessions/{sid}/report", headers=headers).status_code == 409
    finish = client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, json={})
    assert finish.status_code == 200
    assert client.get(f"/api/ai/sessions/{sid}/report", headers=headers).status_code == 200
    if not token:
        assert headers["X-Session-Token"] not in str(service.store.get(sid))
        assert service.store.get(sid)["access_token_hash"]
    assert "owner_id" not in finish.json()


def test_body_cannot_claim_owner_or_redirect_session(api):
    client, service, _ = api
    sid, owner = start(client, token="alumno-a")
    response = client.post(f"/api/ai/sessions/{sid}/message", headers={"Authorization": "Bearer alumno-b"},
        json={"message": "¿Alergias?", "owner_id": "alumno-a", "session_id": "falso"})
    assert response.status_code == 404
    assert service.store.get(sid)["history"] == []
