import copy
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from scripts.import_cases import import_cases, main as import_main
from server.cases import CanonicalCaseRepository, CaseNotFound
from server.cases.supabase import CaseStoreError, SupabaseCaseRepository
from server.cases import source


@pytest.fixture
def case():
    return CanonicalCaseRepository(
        Path(__file__).resolve().parents[1] / "fixtures" / "cases"
    ).get_case("MED-900")


def repository(handler, key="sb_secret_test"):
    return SupabaseCaseRepository(
        "https://example.supabase.co", key,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_cloud_case_keeps_protected_out_of_conversation(case):
    repo = repository(lambda r: httpx.Response(200, json=[{"case_id": case["case_id"], "documento": case}]))
    assert repo.get_case("MED-900") == case
    assert "protected" not in repo.get_conversation_case("MED-900")
    assert repo.get_protected("MED-900") == case["protected"]


@pytest.mark.parametrize("key,expected", [("sb_secret_test", None), ("old.jwt.key", "Bearer old.jwt.key")])
def test_server_key_headers(case, key, expected):
    def handler(request):
        assert request.headers["apikey"] == key
        assert request.headers.get("Authorization") == expected
        assert request.url.params["case_id"] == "eq.MED-900"
        return httpx.Response(200, json=[{"case_id": "MED-900", "documento": case}])
    repository(handler, key).get_case("MED-900")


def test_invalid_id_never_contacts_supabase():
    def handler(request):
        pytest.fail("No debe consultar IDs inválidos")
    with pytest.raises(CaseNotFound):
        repository(handler).get_case("../MED-900")


def test_missing_remote_case_does_not_read_local_files():
    with pytest.raises(CaseNotFound):
        repository(lambda r: httpx.Response(200, json=[])).get_case("EME-001")


@pytest.mark.parametrize("change", ["invalid", "wrong_id", "draft"])
def test_remote_documents_are_validated(case, change):
    row = {"case_id": case["case_id"], "documento": copy.deepcopy(case)}
    if change == "invalid":
        row["documento"].pop("protected")
    elif change == "wrong_id":
        row["case_id"] = "MED-001"
    else:
        row["documento"]["status"] = "borrador"
    with pytest.raises(CaseStoreError):
        repository(lambda r: httpx.Response(200, json=[row])).get_case("MED-900")


def test_pagination_handles_server_page_limit(case):
    offsets = []
    def handler(request):
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(200, json=[{"case_id": case["case_id"], "documento": case}] if offset == 0 else [])
    assert repository(handler).list_curated() == ["MED-900"]
    assert offsets == [0, 1]


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_remote_failure_is_sanitized(status):
    repo = repository(lambda r: httpx.Response(status, text="secret and protected data"))
    with pytest.raises(CaseStoreError) as error:
        repo.list_cases()
    assert "secret" not in str(error.value)
    assert "protected" not in str(error.value)


def test_timeout_is_store_error():
    def handler(request):
        raise httpx.ConnectTimeout("connection failed", request=request)
    with pytest.raises(CaseStoreError):
        repository(handler).get_case("MED-900")


def test_repeat_import_preserves_existing_cases(case):
    rows = {}
    def handler(request):
        if request.method == "POST":
            import json
            assert request.headers["Prefer"] == "resolution=ignore-duplicates,return=minimal"
            assert request.url.params["on_conflict"] == "case_id"
            for row in json.loads(request.content):
                rows.setdefault(row["case_id"], row)
            return httpx.Response(201)
        return httpx.Response(200, json=list(rows.values()) if int(request.url.params["offset"]) == 0 else [])
    repo = repository(handler)
    assert import_cases(repo, [case]) == 1
    assert import_cases(repo, [case]) == 1
    assert len(rows) == 1
    changed = copy.deepcopy(case)
    changed["title"] = "Otro titulo del mismo caso"
    with pytest.raises(CaseStoreError):
        import_cases(repo, [changed])
    assert rows["MED-900"]["documento"] == case


def test_invalid_batch_writes_nothing(case):
    def handler(request):
        pytest.fail("Un lote inválido no debe enviarse")
    invalid = copy.deepcopy(case)
    invalid.pop("protected")
    with pytest.raises(CaseStoreError):
        repository(handler).insert_missing([case, invalid])


def test_dry_run_does_not_create_remote_repository(monkeypatch):
    import scripts.import_cases as importer
    def unexpected(*args, **kwargs):
        pytest.fail("dry-run no debe conectar ni modificar .env")
    monkeypatch.setattr(importer, "SupabaseCaseRepository", unexpected)
    monkeypatch.setattr(importer, "set_key", unexpected)
    assert import_main(["--dry-run", "--activate"]) == 0


def test_failed_import_does_not_activate_store(case, monkeypatch):
    import scripts.import_cases as importer
    monkeypatch.setattr(importer, "load_curated_cases", lambda directory: [case])
    def unavailable(*args, **kwargs):
        raise CaseStoreError("No se pudo conectar al almacén de casos.")
    def unexpected(*args, **kwargs):
        pytest.fail("No debe cambiar .env tras una carga fallida")
    monkeypatch.setattr(importer, "SupabaseCaseRepository", unavailable)
    monkeypatch.setattr(importer, "set_key", unexpected)
    assert import_main(["--activate"]) == 1


def test_activation_follows_verified_import(case, monkeypatch):
    import scripts.import_cases as importer
    calls = []
    monkeypatch.setattr(importer, "load_curated_cases", lambda directory: [case])
    def handler(request):
        if request.method == "POST":
            calls.append("insert")
            return httpx.Response(201)
        calls.append("read")
        return httpx.Response(200, json=[{"case_id": case["case_id"], "documento": case}]
                              if int(request.url.params["offset"]) == 0 else [])
    monkeypatch.setattr(importer, "SupabaseCaseRepository", lambda *args: repository(handler))
    def activate(path, key, value):
        assert key == "CASE_STORE" and value == "supabase"
        calls.append("activate")
    monkeypatch.setattr(importer, "set_key", activate)
    assert import_main(["--activate"]) == 0
    assert calls == ["insert", "read", "read", "activate"]


def test_remote_catalog_api_and_session_use_same_repository(case, monkeypatch):
    import server.api.ai as ai
    import server.api.routes as routes
    from server.ai.llm.gateway import LLMGateway
    from server.ai.llm.providers import LocalDevelopmentProvider
    from server.main import app
    def handler(request):
        rows = [{"case_id": case["case_id"], "documento": case}]
        if "offset" in request.url.params and int(request.url.params["offset"]) > 0:
            rows = []
        return httpx.Response(200, json=rows)
    repo = repository(handler)
    remote_settings = replace(source.settings, case_store="supabase", rag_service_url="http://unused:8001")
    monkeypatch.setattr(source, "settings", remote_settings)
    monkeypatch.setattr(routes, "settings", remote_settings)
    monkeypatch.setattr(ai, "settings", remote_settings)
    monkeypatch.setattr(source, "SupabaseCaseRepository", lambda *a: repo)
    monkeypatch.setattr(ai, "build_gateway", lambda: LLMGateway([LocalDevelopmentProvider()]))
    ai.get_service.cache_clear()
    try:
        client = TestClient(app)
        status = client.get("/api/status").json()
        assert status["availableCases"] == 1
        assert status["caseStore"] == "supabase"
        public = client.get("/api/caso").json()
        assert public["case_id"] == "MED-900"
        assert "protected" not in public and "on_request" not in public
        response = client.post("/api/ai/sessions", json={"case_id": "MED-900"})
        assert response.status_code == 200
        sid = response.json()["session_id"]
        response = client.post(f"/api/ai/sessions/{sid}/message", json={"message": "Desde cuando comenzo el dolor?"},
                               headers={"X-Session-Token": response.json()["session_token"]})
        assert response.status_code == 200
        assert ai.get_service().repository is repo
    finally:
        ai.get_service.cache_clear()


def test_api_returns_503_on_remote_failure(monkeypatch):
    from server.main import app
    import server.api.routes as routes
    def unavailable():
        raise CaseStoreError("secret")
    monkeypatch.setattr(routes, "load_curated_cases", unavailable)
    response = TestClient(app).get("/api/status")
    assert response.status_code == 503
    assert "secret" not in response.text
