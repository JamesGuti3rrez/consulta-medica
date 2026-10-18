"""Panel docente: límites de acceso, extracción y publicación atómica simulada."""
from __future__ import annotations

import copy
import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from case_preparation.indexing.documents import build_case_documents
from server.auth import SupabaseAuth, get_auth
from server.api import teaching
from server.cases.catalog import load_curated_cases
from server.cases.upload_templates import example_case, excel_template
from server.cases.uploads import MAX_FILE_BYTES, UploadError, prepare_cases, read_upload
from server.domain import AgentRole
from server.main import app
from server.persistence.teaching import TeachingStore, TeachingStoreError

ROOT = Path(__file__).resolve().parents[3]
CASES = load_curated_cases(ROOT / "data/cases/curated")
HEADERS = {"Authorization": "Bearer profesor"}
USER_ID = "1de2cbce-c52a-4c19-a9a0-ddfa89c2391e"


class FakeCases:
    def __init__(self):
        self.rows = {case["case_id"]: copy.deepcopy(case) for case in CASES}
    def list_cases(self):
        return list(self.rows.values())
    def get_case(self, case_id):
        from server.cases import CaseNotFound
        if case_id not in self.rows:
            raise CaseNotFound(case_id)
        return self.rows[case_id]


class FakeStore:
    def __init__(self):
        self.cases = FakeCases()
        self.writes = []
        self.client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])))
    def evidence(self, case_id):
        return []
    def publish(self, cases, evidence, **metadata):
        inserted = sum(case["case_id"] not in self.cases.rows for case in cases)
        self.writes.append({"cases": cases, "evidence": evidence, **metadata})
        self.cases.rows.update({case["case_id"]: case for case in cases})
        return {"casos_insertados": inserted, "casos_existentes": len(cases)-inserted,
                "evidencias_indexadas": len(evidence), "importacion_id": "test-import"}


@pytest.fixture
def setup(monkeypatch):
    def handle(request):
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if token == "expired":
            return httpx.Response(401)
        role = token if token in {"profesor", "administrativo"} else "alumno"
        return httpx.Response(200, json={"id": USER_ID, "email": "docente@example.edu",
                                       "app_metadata": {"rol": role}, "user_metadata": {"rol": "administrativo"}})
    auth = SupabaseAuth("https://test.supabase.co", "public", client=httpx.Client(transport=httpx.MockTransport(handle)))
    store = FakeStore()
    app.dependency_overrides[get_auth] = lambda: auth
    app.dependency_overrides[teaching.get_teaching_store] = lambda: store
    monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "local_hash")
    client = TestClient(app)
    yield client, store
    app.dependency_overrides.clear()
    store.client.close()


@pytest.mark.parametrize("path,method", [
    ("/api/docente/casos", "get"), ("/api/docente/casos/MED-101", "get"),
    ("/api/docente/plantilla?formato=json", "get"),
    ("/api/docente/importaciones/validar?archivo=casos.json", "post"),
    ("/api/docente/importaciones", "post"),
    ("/api/docente/casos/MED-101/probar-rag", "post"),
    ("/api/docente/rag/sincronizar", "post"),
])
def test_student_and_guest_cannot_access_private_teacher_data(setup, path, method):
    client, store = setup
    call = getattr(client, method)
    options = {"json": {}} if method == "post" else {}
    assert call(path, **options).status_code == 401
    assert call(path, headers={"Authorization": "Bearer alumno"}, **options).status_code == 403
    assert store.writes == []


def test_session_reports_verified_role_and_rejects_expired_session(setup):
    client, _ = setup
    assert client.get("/api/docente/sesion", headers=HEADERS).json()["rol"] == "profesor"
    assert client.get("/api/docente/sesion", headers={"Authorization": "Bearer alumno"}).json()["panel_docente"] is False
    assert client.get("/api/docente/sesion", headers={"Authorization": "Bearer expired"}).status_code == 401


@pytest.mark.parametrize("role", ["profesor", "administrativo"])
def test_staff_sees_all_specialties_and_private_diagnosis(setup, role):
    client, _ = setup
    response = client.get("/api/docente/casos", headers={"Authorization": "Bearer " + role})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 43
    assert len(body["por_especialidad"]) == 5
    assert sum(body["por_especialidad"].values()) == 43
    assert all(item["diagnostico"] for item in body["casos"])


def test_detail_reports_missing_index_instead_of_claiming_complete(setup):
    client, _ = setup
    response = client.get("/api/docente/casos/MED-101", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["caso"]["protected"]["diagnosis"]
    assert body["rag"]["indexadas"] == 0
    assert body["rag"]["faltantes"]
    assert len(body["rag"]["faltantes"]) == len(build_case_documents([body["caso"]]))


@pytest.mark.parametrize("format", ["json", "xlsx"])
def test_template_round_trip_validates_without_writes(setup, format):
    client, store = setup
    response = client.get("/api/docente/plantilla?formato=" + format, headers=HEADERS)
    assert response.status_code == 200
    preview = client.post("/api/docente/importaciones/validar?archivo=plantilla." + format,
                          headers=HEADERS, content=response.content)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["valido"] is True, body
    assert body["casos"][0]["case_id"] == "MED-107"
    assert body["casos"][0]["provenance"]["curated_by"] == "docente:" + USER_ID
    assert store.writes == []


def test_publish_saves_case_and_only_conversational_index_in_one_call(setup):
    client, store = setup
    case = example_case(CASES)
    response = client.post("/api/docente/importaciones", headers=HEADERS,
                           json={"casos": [case], "archivo": "caso.json"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["casos_insertados"] == 1
    assert len(store.writes) == 1
    written = store.writes[0]
    assert written["user_id"] == USER_ID
    assert written["evidence"] and all(row["owner"] != "protected" for row in written["evidence"])
    assert all(row["case_id"] == "MED-107" and row["embedding_model"] and row["source_hash"] for row in written["evidence"])
    assert not any(case["protected"]["diagnosis"]["name"] in row["content"] for row in written["evidence"])
    repeat = client.post("/api/docente/importaciones", headers=HEADERS, json={"casos": [case], "archivo": "caso.json"})
    assert repeat.status_code == 200
    assert repeat.json()["casos_insertados"] == 0


def test_publish_conflicting_case_is_rejected_before_any_write(setup):
    client, store = setup
    case = copy.deepcopy(next(item for item in CASES if item["case_id"] == "MED-101"))
    case["public"]["patient"]["alias"] = "Otra persona"
    response = client.post("/api/docente/importaciones", headers=HEADERS, json={"casos": [case], "archivo": "conflicto.json"})
    assert response.status_code == 422
    assert store.writes == []


def test_invalid_batch_is_fully_rejected_and_duplicate_ids_are_reported(setup):
    client, store = setup
    valid = example_case(CASES)
    invalid = copy.deepcopy(valid); invalid["case_id"] = "../../otra"
    response = client.post("/api/docente/importaciones", headers=HEADERS,
                           json={"casos": [valid, invalid], "archivo": "lote.json"})
    assert response.status_code == 422
    assert store.writes == []
    _, errors, _ = prepare_cases([valid, valid], CASES, USER_ID)
    assert any("R10" in error["message"] for error in errors)


@pytest.mark.parametrize(("name", "content"), [("malo.json", b"{"),
    ("malo.pdf", b"pdf"), ("vacio.json", b"[]"), ("malo.xlsx", b"not a workbook")])
def test_bad_documents_do_not_write(setup, name, content):
    client, store = setup
    assert client.post("/api/docente/importaciones/validar?archivo=" + name,
                       headers=HEADERS, content=content).status_code == 422
    assert store.writes == []


def test_oversized_upload_is_rejected(setup):
    client, store = setup
    response = client.post("/api/docente/importaciones/validar?archivo=grande.json",
                           headers=HEADERS, content=b"x" * (MAX_FILE_BYTES + 1))
    assert response.status_code == 413
    assert store.writes == []


def test_excel_rejects_formulas_and_orphan_evidence():
    content = excel_template(example_case(CASES))
    book = load_workbook(BytesIO(content))
    book["Casos"]["B2"] = "=1+1"
    stream = BytesIO(); book.save(stream)
    with pytest.raises(UploadError, match="fórmulas"):
        read_upload("formula.xlsx", stream.getvalue())
    book["Casos"]["B2"] = "Consulta de ejemplo"
    book["Evidencias"]["A2"] = "MED-999"
    stream = BytesIO(); book.save(stream)
    with pytest.raises(UploadError, match="no aparecen"):
        read_upload("huerfano.xlsx", stream.getvalue())


def test_probe_uses_disclosure_before_pgvector_search(setup, monkeypatch):
    client, _ = setup
    requests = []
    class Retriever:
        def __init__(self, *args, **kwargs): pass
        def retrieve(self, **kwargs):
            requests.append(kwargs)
            return []
    monkeypatch.setattr(teaching, "SupabasePgvectorRetriever", Retriever)
    response = client.post("/api/docente/casos/MED-101/probar-rag", headers=HEADERS,
                           json={"pregunta": "Solicito función tiroidea"})
    assert response.status_code == 200
    assert requests[0]["agent_role"] == AgentRole.LABORATORIO
    assert requests[0]["allowed_evidence_ids"] == ["MED-101.lab.funcion_tiroidea"]
    assert response.json()["backend_prueba"] == "supabase_pgvector"


def test_missing_rpc_has_actionable_safe_error(setup):
    client, store = setup
    def fail(*args, **kwargs):
        raise TeachingStoreError("Aplica la migración 0004_panel_docente.sql en Supabase para publicar casos.")
    store.publish = fail
    response = client.post("/api/docente/importaciones", headers=HEADERS,
                           json={"casos": [example_case(CASES)], "archivo": "ejemplo.json"})
    assert response.status_code == 503
    assert "0004_panel_docente" in response.json()["detail"]


def test_store_sends_one_atomic_rpc_without_exposing_secret():
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"casos_insertados": 1, "evidencias_indexadas": 1})
    store = TeachingStore("https://test.supabase.co", "sb_secret_test",
                          client=httpx.Client(transport=httpx.MockTransport(handle)))
    store.publish([{"case_id": "MED-107"}], [{"case_id": "MED-107"}],
                  user_id=USER_ID, filename="casos.xlsx")
    assert len(calls) == 1 and calls[0].url.path == "/rest/v1/rpc/importar_casos_docente"
    body = json.loads(calls[0].content)
    assert body["p_docente_id"] == USER_ID
    assert "sb_secret_test" not in str(body)


def test_bulk_sync_rebuilds_all_specialties_without_modifying_cases(setup):
    client, store = setup
    before = copy.deepcopy(store.cases.rows)
    response = client.post('/api/docente/rag/sincronizar', headers=HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['casos_sincronizados'] == len(CASES)
    assert body['evidencias_indexadas'] == len(build_case_documents(CASES))
    assert body['lotes'] == 1
    assert store.cases.rows == before
    assert {row['case_id'] for row in store.writes[0]['evidence']} == set(before)
    assert all(row['owner'] != 'protected' for row in store.writes[0]['evidence'])


def test_bulk_sync_empty_catalog_does_not_write(setup):
    client, store = setup
    store.cases.rows = {}
    body = client.post('/api/docente/rag/sincronizar', headers=HEADERS).json()
    assert body['casos_sincronizados'] == body['evidencias_indexadas'] == 0
    assert store.writes == []


def test_bulk_sync_validates_entire_catalog_before_writing(setup):
    client, store = setup
    case = store.cases.rows['MED-101']
    case['on_request'][0]['text'] += ' ' + case['protected']['diagnosis']['name']
    response = client.post('/api/docente/rag/sincronizar', headers=HEADERS)
    assert response.status_code == 422
    assert store.writes == []


def test_bulk_sync_supports_catalogs_larger_than_rpc_batch_limit(setup):
    from server.rag.catalog_sync import synchronize_catalog
    _, store = setup
    example = example_case(CASES)
    cases = [json.loads(json.dumps(example).replace(example['case_id'], f'MED-{number:03d}'))
             for number in range(200, 305)]
    # La sincronización trabaja con documentos ya curados del repositorio.
    for case in cases:
        case['status'] = 'curado'
    store.cases.rows = {case['case_id']: case for case in cases}
    result = synchronize_catalog(store, user_id=USER_ID)
    assert result['casos_sincronizados'] == 105
    assert result['lotes'] == 2
    assert [len(write['cases']) for write in store.writes] == [100, 5]


@pytest.mark.parametrize('verified', [False, True])
def test_activation_changes_env_only_after_verification(monkeypatch, verified):
    import scripts.sync_rag as activation
    writes = []
    monkeypatch.setattr('sys.argv', ['sync_rag.py', '--email', 'docente@example.edu', '--activate'])
    monkeypatch.setattr(activation, 'TeachingStore', lambda *args: type('Store', (), {'headers': {}})())
    monkeypatch.setattr(activation, 'find_staff_id', lambda *args: USER_ID)
    monkeypatch.setattr(activation, 'synchronize_catalog', lambda *args, **kwargs: {'lotes': 1})
    def verify(store):
        if not verified:
            raise ValueError('Índice incompleto')
        return 43, 500
    monkeypatch.setattr(activation, 'verify_index', verify)
    monkeypatch.setattr(activation, 'set_key', lambda *args: writes.append(args))
    assert activation.main() == (0 if verified else 1)
    assert len(writes) == int(verified)
    if verified:
        assert writes[0][1:] == ('RAG_BACKEND', 'supabase_pgvector')

