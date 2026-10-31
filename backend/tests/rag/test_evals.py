from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from evals.dataset import load_dataset
from evals.metrics import retrieval_metrics
from evals.ragas_bridge import RagasEvaluator
from evals.reporting import aggregate, export
from evals.runner import evaluate
from server.cases.catalog import CURATED_CASES_DIR
from server.cases.repository import CanonicalCaseRepository
from server.config import settings
from server.rag.factory import build_retriever
from server.rag.port import RetrievedEvidence


@pytest.fixture(autouse=True)
def isolated_judge_environment(monkeypatch):
    # Este archivo prueba el adaptador OpenAI con datos controlados. El pool Groq
    # del .env personal nunca debe habilitar llamadas externas desde estas pruebas.
    monkeypatch.setenv('RAGAS_PROVIDER', 'openai')
    monkeypatch.setenv('RAGAS_EMBEDDING_BACKEND', 'openai')
    for name in ('RAGAS_API_KEY', 'RAGAS_MODEL', 'RAGAS_EMBEDDING_MODEL', 'RAGAS_BASE_URL'):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("expected,found,k,p,r,h", [
    (["a", "b", "c"], ["a", "b", "c"], 3, 1, 1, 1),
    (["a", "b"], ["a", "x", "y"], 3, 1/3, .5, 1),
    (["a"], ["x", "y", "z"], 3, 0, 0, 0),
    (["a"], [], 3, 0, 0, 0),
    (["a"], ["a", "a", "a"], 3, 1/3, 1, 1),
    (["a", "b"], ["x", "x", "a", "b"], 3, 1/3, .5, 1),
    (["a", "a"], ["a"], 5, .2, 1, 1),
])
def test_metrics(expected, found, k, p, r, h):
    result = retrieval_metrics(expected, found, k)
    assert result["precision"] == pytest.approx(p)
    assert result["recall"] == pytest.approx(r)
    assert result["hit"] == h


def test_negative_references_and_k():
    assert retrieval_metrics([], [], 3) == dict(precision=0, recall=None, hit=None, abstention=1)
    assert retrieval_metrics([], ["x"], 3)["abstention"] == 0
    for invalid in [0, -1, True, 1.5]:
        with pytest.raises(ValueError):
            retrieval_metrics([], [], invalid)


DATASET = Path(__file__).resolve().parents[2] / "evals/datasets/clinical_v1.json"


def test_real_dataset_balanced_verifiable_and_unchanged():
    repo = CanonicalCaseRepository(CURATED_CASES_DIR)
    before = {path: path.read_bytes() for path in CURATED_CASES_DIR.glob("*.json")}
    records = load_dataset(DATASET, repo)
    assert len(records) == 100
    assert len({r['case_id'] for r in records}) == 10
    from collections import Counter
    assert set(Counter(r['specialty'] for r in records).values()) == {20}
    for row in records:
        if row['scenario'] == 'cross_case':
            assert row['forbidden_evidence_ids']
            assert all(not i.startswith(row['case_id'] + '.') for i in row['forbidden_evidence_ids'])
    assert before == {path: path.read_bytes() for path in before}


def test_dataset_rejects_drift_and_foreign_references(tmp_path):
    repo = CanonicalCaseRepository(CURATED_CASES_DIR)
    original = json.loads(DATASET.read_text(encoding="utf-8"))[:1]
    for field, value in [("case_sha256", "modified"), ("expected_evidence_ids", ["OTHER-999.secret"]),
                         ("specialty", "inventada")]:
        rows = copy.deepcopy(original)
        rows[0][field] = value
        path = tmp_path / "dataset.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        with pytest.raises(ValueError):
            load_dataset(path, repo)


@pytest.fixture
def mini():
    case = {"case_id": "MED-900", "title": "Caso", "specialty": "medicina_interna",
            "public": {"patient": {}, "chief_complaint": {
                "evidence_id": "MED-900.motivo.publico", "label": "Motivo", "category": "motivo", "text": "Malestar"}},
            "on_request": [{"evidence_id": "MED-900.antecedente.historia", "text": "Antecedentes registrados.",
                            "reveal_policy": {"owner": "paciente", "mode": "al_preguntar",
                                              "requires": ["antecedentes_personales"]}}]}
    class Repo:
        def get_conversation_case(self, case_id):
            assert case_id == "MED-900"
            return copy.deepcopy(case)

        def get_protected(self, case_id):
            return {"diagnosis": {"name": "Secreto clínico reservado"}}
    record = {"test_id": "one", "case_id": "MED-900", "specialty": "medicina_interna",
              "query": "¿Qué antecedentes personales tiene?", "scenario": "patient",
              "expected_evidence_ids": ["MED-900.antecedente.historia"]}
    return Repo(), record


@pytest.mark.parametrize("evidence_id,text,error", [
    ("MED-901.antecedente.historia", "Texto", "cross_case_leak"),
    ("MED-900.lab.no_autorizado", "Texto", "unauthorized_evidence"),
    ("MED-900.antecedente.historia", "Secreto clínico reservado", "protected_content"),
    ("MED-900.synthetic.resultado", "Inventado", "noncanonical_evidence"),
])
def test_security_and_redacted_exports(mini, tmp_path, evidence_id, text, error):
    repo, record = mini
    class Retriever:
        def retrieve(self, **kwargs):
            assert kwargs['session_id'] is None
            return [RetrievedEvidence(evidence_id, text)]
    rows, traces = evaluate([record], repo, Retriever(), [3, 5], RagasEvaluator())
    assert error in rows[0]['errors']
    assert rows[0]['security_failure']
    export(tmp_path, rows, traces, dict(ks=[3, 5], started_at="test", profile="test",
                                       retriever={"class": "test"}))
    for path in tmp_path.iterdir():
        assert "Secreto clínico reservado" not in path.read_text(encoding="utf-8-sig")
        assert "Inventado" not in path.read_text(encoding="utf-8-sig")


def test_provider_failure_is_not_a_successful_abstention(mini):
    repo, record = mini
    class Broken:
        def retrieve(self, **kwargs):
            raise RuntimeError("SECRET API KEY and protected text")
    rows, traces = evaluate([record], repo, Broken(), [3], RagasEvaluator())
    assert rows[0]['precision'] is None
    assert rows[0]['abstention'] is None
    assert rows[0]['retrieval_status'] == 'error'
    assert 'SECRET' not in json.dumps([rows, traces])
    summary = aggregate(rows)[0]
    assert summary['retrieval_errors'] == 1
    assert summary['precision_n'] == 0


def test_empty_result_and_missing_ragas_continue(mini, monkeypatch):
    import evals.ragas_bridge as bridge
    from importlib.metadata import PackageNotFoundError
    def unavailable(name):
        raise PackageNotFoundError(name)
    monkeypatch.setattr(bridge, 'version', unavailable)
    evaluator = RagasEvaluator('ids')
    class Empty:
        def retrieve(self, **kwargs):
            return []
    rows, _ = evaluate([mini[1]], mini[0], Empty(), [3], evaluator)
    assert rows[0]['precision'] == 0
    assert rows[0]['recall'] == 0
    assert rows[0]['ragas_context_precision'] is None
    assert rows[0]['ragas_ids_status'] == 'unavailable'
    assert {'empty_retrieval', 'missing_expected'} <= set(rows[0]['errors'])


def test_real_ragas_ids_and_failure_without_credentials(monkeypatch):
    pytest.importorskip('ragas')
    evaluator = RagasEvaluator('llm')
    assert evaluator.config['status'] == 'ready'
    scores = evaluator.score_ids(['a', 'b'], ['a', 'x', 'x'])
    assert scores['ragas_context_precision'] == .5
    assert scores['ragas_context_recall'] == .5
    # La API 0.4.3 devuelve NaN en precisión sin resultados; se exporta N/A.
    assert evaluator.score_ids(['a'], [])['ragas_context_precision'] is None
    assert evaluator.score_ids([], [])['ragas_context_recall'] is None
    monkeypatch.delenv('RAGAS_API_KEY', raising=False)
    assert evaluator.score_response('q', 'r', ['c'])['ragas_response_status'] == 'missing_credentials_or_model'


def test_ragas_judge_failure_does_not_erase_id_scores(monkeypatch):
    pytest.importorskip('ragas')
    import ragas.llms.base
    monkeypatch.setenv('RAGAS_API_KEY', 'test-key')
    monkeypatch.setenv('RAGAS_MODEL', 'test-model')
    def broken(*args, **kwargs):
        raise RuntimeError('SECRET')
    monkeypatch.setattr(ragas.llms.base, 'llm_factory', broken)
    evaluator = RagasEvaluator('llm')
    result = evaluator.score_response('q', 'r', ['c'])
    assert result['ragas_faithfulness'] is None
    assert result['ragas_response_status'] == 'error:RuntimeError'
    assert evaluator.score_ids(['a'], ['a'])['ragas_context_recall'] == 1


def test_factory_uses_json_when_no_index_and_respects_remote_priority(tmp_path):
    config = replace(settings, rag_backend='local', case_store='local', rag_service_url='',
                     rag_embedded_enabled=True, rag_index_dir=tmp_path)
    assert type(build_retriever(object(), config=config)).__name__ == 'CaseEvidenceRetriever'
    config = replace(config, case_store='supabase', rag_service_url='https://unused')
    assert type(build_retriever(object(), config=config)).__name__ == 'CaseEvidenceRetriever'
    config = replace(config, case_store='local', rag_service_url='https://unused')
    assert type(build_retriever(object(), config=config)).__name__ == 'HttpRetriever'


def test_auxiliary_log_contains_hash_instead_of_query(tmp_path):
    from evals.runner import HashedRetrievalLogger, text_hash
    path = tmp_path / 'retrieval.jsonl'
    HashedRetrievalLogger(path).write({'query': 'Secreto clínico reservado', 'results': []})
    row = json.loads(path.read_text(encoding='utf-8'))
    assert 'query' not in row
    assert row['query_sha256'] == text_hash('Secreto clínico reservado')


def test_actual_ragas_judge_api_with_controlled_http(monkeypatch):
    """Contrato real de RAGAS/OpenAI; todos los mensajes del juez son controlados."""
    pytest.importorskip('ragas')
    import httpx
    import openai
    monkeypatch.setenv('RAGAS_API_KEY', 'test-only')
    monkeypatch.setenv('RAGAS_MODEL', 'test-model')
    monkeypatch.delenv('RAGAS_EMBEDDING_MODEL', raising=False)
    for name in ('INPUT', 'OUTPUT', 'EMBEDDING'):
        monkeypatch.setenv('RAGAS_' + name + '_USD_PER_MILLION', '1')
    original = openai.AsyncOpenAI
    calls = []
    def handle(request):
        data = json.loads(request.content)
        # RAGAS 0.4.3 usa Instructor en modo JSON, con esquema en el mensaje.
        assert data['response_format'] == {'type': 'json_object'}
        tool = 'NLIStatementOutput' if 'NLIStatementOutput' in json.dumps(data) else 'StatementGeneratorOutput'
        calls.append(tool)
        statements = (['Tiene fiebre.', 'Tiene tos.'] if tool == 'StatementGeneratorOutput' else
                      [{'statement': 'Tiene fiebre.', 'reason': 'Documentado', 'verdict': 1},
                       {'statement': 'Tiene tos.', 'reason': 'No documentado', 'verdict': 0}])
        return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion', 'created': 0,
            'model': 'test-model', 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': json.dumps({'statements': statements})}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}})
    class ControlledClient(original):
        def __init__(self, **kwargs):
            hooks = kwargs['http_client'].event_hooks
            kwargs['http_client'] = httpx.AsyncClient(transport=httpx.MockTransport(handle), event_hooks=hooks)
            super().__init__(**kwargs)
    monkeypatch.setattr(openai, 'AsyncOpenAI', ControlledClient)
    evaluator = RagasEvaluator('llm')
    result = evaluator.score_response('¿Tiene fiebre?', 'Tiene fiebre y tos.', ['Tiene fiebre.'])
    assert result['ragas_faithfulness'] == .5, result
    assert calls == ['StatementGeneratorOutput', 'NLIStatementOutput']
    assert evaluator.usage['input_tokens'] == 20
    assert evaluator.usage['output_tokens'] == 10
    assert evaluator.config['cost_usd'] == pytest.approx(.00003)


def test_unsupported_response_is_classified_without_exporting_content(mini, monkeypatch):
    from server.ai.llm.gateway import LLMGateway
    from server.ai.llm.providers import LocalDevelopmentProvider
    monkeypatch.setattr('server.ai.llm.factory.build_gateway',
                        lambda: LLMGateway([LocalDevelopmentProvider()]))
    repo, record = mini
    class Retriever:
        def retrieve(self, **kwargs):
            return [RetrievedEvidence('MED-900.antecedente.historia', 'Antecedentes registrados.')]
    class Judge(RagasEvaluator):
        def score_response(self, *args):
            return {'ragas_faithfulness': .5, 'ragas_response_relevancy': None,
                    'ragas_response_status': 'controlled_test'}
    rows, traces = evaluate([record], repo, Retriever(), [3], Judge(), generate_responses=True)
    assert rows[0]['response_status'] == 'ok'
    assert 'unsupported_response_claims' in rows[0]['errors']
    assert 'Antecedentes registrados.' not in json.dumps([rows, traces])


def test_limit_validates_only_selected_references(tmp_path):
    original = json.loads(DATASET.read_text(encoding='utf-8'))
    original[1]['case_sha256'] = 'invalid'
    path = tmp_path / 'sample.json'
    path.write_text(json.dumps(original), encoding='utf-8')
    repo = CanonicalCaseRepository(CURATED_CASES_DIR)
    assert len(load_dataset(path, repo, limit=1)) == 1
    with pytest.raises(ValueError):
        load_dataset(path, repo)
    with pytest.raises(ValueError):
        load_dataset(path, repo, limit=0)


def test_progress_runs_once_per_complete_query(mini):
    repo, record = mini
    calls = []
    class Empty:
        def retrieve(self, **kwargs):
            return []
    rows, traces = evaluate([record], repo, Empty(), [3, 5], RagasEvaluator(),
        on_complete=lambda index, total, test_id, rows, traces:
            calls.append((index, total, test_id, len(rows), len(traces))))
    assert calls == [(1, 1, 'one', 2, 1)]
    assert len(rows) == 2 and len(traces) == 1


def test_local_tracing_overrides_inherited_context_and_threads(monkeypatch):
    import asyncio
    from langsmith import tracing_context
    from langsmith.utils import tracing_is_enabled
    from evals.telemetry import local_tracing_only
    monkeypatch.setenv('LANGSMITH_TRACING', 'true')
    async def in_thread():
        return await asyncio.to_thread(tracing_is_enabled)
    with tracing_context(enabled=True):
        with local_tracing_only():
            assert tracing_is_enabled() is False
            assert asyncio.run(in_thread()) is False
        assert tracing_is_enabled() is True


def test_evaluation_tracing_can_enable_requested_project_without_sending_runs():
    from langsmith.run_helpers import get_tracing_context
    from langsmith.utils import tracing_is_enabled
    from evals.telemetry import evaluation_tracing
    # Solo consulta el contexto; no crea runs ni clientes remotos.
    with evaluation_tracing(enabled=True, project_name='controlled-project'):
        assert tracing_is_enabled() is True
        assert get_tracing_context()['project_name'] == 'controlled-project'


def test_cli_keeps_completed_results_on_ctrl_c(mini, monkeypatch, tmp_path):
    from evals import __main__ as cli
    repo, original = mini
    record = {**original, 'case_sha256': 'controlled'}
    source = tmp_path / 'input.json'
    source.write_text('[]', encoding='utf-8')
    output = tmp_path / 'output'
    monkeypatch.setattr('sys.argv', ['evals', '--dataset', str(source), '--output', str(output)])
    monkeypatch.setattr(cli, 'build_case_repository', lambda *a, **kw: repo)
    monkeypatch.setattr(cli, 'load_dataset', lambda *a, **kw: [record])
    monkeypatch.setattr(cli.subprocess, 'check_output', lambda *a, **kw: 'controlled')
    class Empty:
        def retrieve(self, **kwargs):
            return []
    monkeypatch.setattr(cli, 'build_retriever', lambda *a, **kw: Empty())
    def interrupted(records, repository, retriever, ks, ragas, *, generate_responses, on_complete):
        rows, traces = evaluate(records, repository, retriever, ks, ragas)
        on_complete(1, 2, record['test_id'], rows, traces)
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, 'evaluate', interrupted)
    def save(output, rows, traces, metadata):
        assert len(rows) == 2 and len(traces) == 1
        (output / 'run.json').write_text(json.dumps(metadata), encoding='utf-8')
    monkeypatch.setattr(cli, 'export', save)
    assert cli.main() == 130
    metadata = json.loads((output / 'run.json').read_text(encoding='utf-8'))
    assert metadata['status'] == 'interrupted'
    assert metadata['completed_queries'] == 1
    assert metadata['external_tracing'].startswith('disabled')
