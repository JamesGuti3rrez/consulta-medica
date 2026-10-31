"""Contratos controlados de Groq/RAGAS; no se usan claves ni servicios reales."""
import asyncio
import json
from dataclasses import replace

import pytest
from pydantic import BaseModel

from evals.judge_config import resolve_judge_settings


def test_groq_defaults_inherit_pool_and_model():
    config = resolve_judge_settings({'GROQ_API_KEYS': 'fake-one;fake-two', 'GROQ_MODEL': 'groq-model'})
    assert config.provider == 'groq'
    assert config.api_keys == ('fake-one', 'fake-two')
    assert config.model == 'groq-model'
    assert config.base_url == 'https://api.groq.com/openai/v1'
    assert config.embedding_backend == 'sentence_transformers'


def test_groq_ignores_legacy_openai_credentials_and_endpoint():
    config = resolve_judge_settings({'GROQ_API_KEYS': 'fake-groq', 'RAGAS_API_KEY': 'fake-openai',
                                    'RAGAS_BASE_URL': 'https://api.openai.com/v1'})
    assert config.api_keys == ('fake-groq',)
    assert config.base_url == 'https://api.groq.com/openai/v1'


def test_groq_model_override_and_explicit_openai_do_not_mix_credentials():
    config = resolve_judge_settings({'GROQ_API_KEYS': 'fake-groq', 'GROQ_MODEL': 'generator',
                                    'RAGAS_MODEL': 'judge'})
    assert config.model == 'judge'
    other = resolve_judge_settings({'RAGAS_PROVIDER': 'openai', 'GROQ_API_KEYS': 'fake-groq'})
    assert other.api_keys == ()


def test_groq_judge_reuses_pool_json_contract_and_reports_usage(monkeypatch):
    pytest.importorskip('ragas')
    import httpx
    from evals.groq_judge import GroqPoolJudge
    from server.ai.llm.factory import build_gateway
    from server.config import settings
    requests = []
    def post(url, *, headers, json, timeout):
        assert url == 'https://api.groq.com/openai/v1/chat/completions'
        assert json['response_format'] == {'type': 'json_object'}
        assert json['model'] == 'judge-model'
        requests.append(headers['Authorization'])
        if headers['Authorization'] == 'Bearer fake-invalid':
            return httpx.Response(401, json={'error': 'invalid credential'})
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"statements":["Controlado"]}'}}],
                                         'usage': {'prompt_tokens': 10, 'completion_tokens': 5}})
    monkeypatch.setattr('server.ai.llm.providers.httpx.post', post)
    config = replace(settings, groq_api_keys=('fake-invalid', 'fake-valid'), groq_model='judge-model',
                     groq_base_url='https://api.groq.com/openai/v1')
    usage = dict(successful_gateway_calls=0, gateway_calls_with_usage=0, input_tokens=0, output_tokens=0)
    judge = GroqPoolJudge(build_gateway(config=config), usage)
    class Statements(BaseModel):
        statements: list[str]
    result = asyncio.run(judge.agenerate('Pregunta controlada', Statements))
    assert result.statements == ['Controlado']
    assert requests == ['Bearer fake-invalid', 'Bearer fake-valid']
    assert usage['input_tokens'] == 10
    assert usage['output_tokens'] == 5


def test_groq_missing_credentials_does_not_use_openai_key(monkeypatch):
    pytest.importorskip('ragas')
    from evals.ragas_bridge import RagasEvaluator
    monkeypatch.setenv('RAGAS_PROVIDER', 'groq')
    monkeypatch.setenv('GROQ_API_KEYS', '')
    monkeypatch.setenv('GROQ_API_KEY', '')
    monkeypatch.setenv('RAGAS_API_KEY', 'fake-openai')
    evaluator = RagasEvaluator('llm')
    result = evaluator.score_response('Pregunta', 'Respuesta', ['Contexto'])
    assert result['ragas_response_status'] == 'missing_credentials_or_model'
    assert 'fake-openai' not in json.dumps(evaluator.config)


def test_local_embeddings_use_existing_semantic_provider(monkeypatch):
    pytest.importorskip('ragas')
    import numpy as np
    from evals.groq_judge import LocalSemanticEmbeddings
    seen = []
    class Provider:
        def embed_sync(self, texts):
            return np.array([[1., 0.] for _ in texts])
    def provider(backend, *, model):
        seen.append((backend, model))
        return Provider()
    monkeypatch.setattr('evals.groq_judge.get_embedding_provider', provider)
    embeddings = LocalSemanticEmbeddings('local-test-model')
    assert asyncio.run(embeddings.aembed_texts(['uno', 'dos'])) == [[1., 0.], [1., 0.]]
    assert seen == [('sentence_transformers', 'local-test-model')]
