import json

import httpx
import pytest

from server.cases.supabase import CaseStoreError
from server.persistence.synthetic_facts import SupabaseSyntheticFacts


def test_store_isolates_cases_paginates_and_uses_server_key():
    offsets = []
    def handler(request):
        assert request.headers["apikey"] == "sb_secret_test"
        assert "Authorization" not in request.headers
        assert request.url.params["case_id"] == "eq.MED-008"
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(200, json=[{"case_id": "MED-008", "clave": "tabaco"}] if offset == 0 else [])
    store = SupabaseSyntheticFacts("https://example.supabase.co", "sb_secret_test",
                                  client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert len(store.list_for_case("MED-008")) == 1
    assert offsets == [0, 1]


def test_insert_uses_unique_key_and_never_updates_existing_facts():
    def handler(request):
        assert request.method == "POST"
        assert request.url.params["on_conflict"] == "case_id,clave"
        assert request.headers["Prefer"] == "resolution=ignore-duplicates,return=minimal"
        assert request.headers["Authorization"] == "Bearer old.jwt.key"
        assert json.loads(request.content)[0]["case_id"] == "MED-008"
        return httpx.Response(201)
    store = SupabaseSyntheticFacts("https://example.supabase.co", "old.jwt.key",
                                  client=httpx.Client(transport=httpx.MockTransport(handler)))
    store.insert_missing([{"case_id": "MED-008", "clave": "tabaco"}])


@pytest.mark.parametrize("body", [[{"case_id": "MED-007"}], {}, "not rows"])
def test_store_rejects_another_cases_data_or_malformed_payload(body):
    store = SupabaseSyntheticFacts("https://example.supabase.co", "sb_secret_test",
                                  client=httpx.Client(transport=httpx.MockTransport(
                                      lambda r: httpx.Response(200, json=body))))
    with pytest.raises(CaseStoreError):
        store.list_for_case("MED-008")


def test_store_failure_does_not_leak_credentials_or_raw_payload():
    store = SupabaseSyntheticFacts("https://example.supabase.co", "sb_secret_test",
                                  client=httpx.Client(transport=httpx.MockTransport(
                                      lambda r: httpx.Response(403, text="private-content"))))
    with pytest.raises(CaseStoreError) as exc:
        store.list_for_case("MED-008")
    assert "private-content" not in str(exc.value)
    assert "sb_secret" not in str(exc.value)
