"""RAGAS 0.4.3 opcional: identidad local y juez externo separados."""
from __future__ import annotations

import asyncio
import math
import os
from importlib.metadata import PackageNotFoundError, version

from .judge_config import resolve_judge_settings

RAGAS_VERSION = "0.4.3"


class RagasEvaluator:
    def __init__(self, mode="off"):
        self.mode = mode
        self.judge = resolve_judge_settings()
        self._groq_llm = None
        self._local_embeddings = None
        self.usage = {"http_responses": 0, "requests_with_usage": 0, "input_tokens": 0, "output_tokens": 0,
                      "embedding_tokens": 0, "successful_gateway_calls": 0, "gateway_calls_with_usage": 0}
        self.config = {"mode": mode, "required_version": RAGAS_VERSION,
                       "version": None, "status": "disabled" if mode == "off" else "pending",
                       "provider": self.judge.provider, "model": self.judge.model,
                       "credential_count": len(self.judge.api_keys),
                       "embedding_backend": self.judge.embedding_backend,
                       "embedding_model": self.judge.embedding_model,
                       "temperature": 0, "timeout_seconds": self.judge.timeout_seconds,
                       "strictness": 3, "usage": self.usage,
                       "usage_scope": ("successful_gateway_calls_only" if self.judge.provider == "groq"
                                       else "observed_provider_responses_only"), "cost_usd": None,
                       "rates_usd_per_million": {name: os.getenv("RAGAS_" + name + "_USD_PER_MILLION")
                                                 for name in ("INPUT", "OUTPUT", "EMBEDDING")}}
        self.sample_class = None
        self.id_metrics = []
        if mode == "off":
            return
        # Evitar telemetría del framework en el arnés offline.
        os.environ["RAGAS_DO_NOT_TRACK"] = "true"
        try:
            self.config["version"] = version("ragas")
            if self.config["version"] != RAGAS_VERSION:
                self.config["status"] = "incompatible_version"
                return
            from ragas import SingleTurnSample
            from ragas.metrics._context_precision import IDBasedContextPrecision
            from ragas.metrics._context_recall import IDBasedContextRecall
            self.sample_class = SingleTurnSample
            self.id_metrics = [IDBasedContextPrecision(), IDBasedContextRecall()]
            self.config["status"] = "ready"
        except (ImportError, PackageNotFoundError) as exc:
            self.config["status"] = "unavailable"
            self.config["exception_type"] = type(exc).__name__
        except Exception as exc:
            self.config["status"] = "initialization_error:" + type(exc).__name__

    def score_ids(self, expected, retrieved):
        result = {"ragas_context_precision": None, "ragas_context_recall": None,
                  "ragas_ids_status": self.config["status"]}
        if self.config["status"] != "ready":
            return result
        if not expected:
            result["ragas_ids_status"] = "not_applicable_no_reference"
            return result
        # Duplicados no inflan la puntuación de RAGAS. P@k conserva posiciones originales.
        sample = self.sample_class(reference_context_ids=sorted(set(expected)),
                                   retrieved_context_ids=list(dict.fromkeys(retrieved)))

        async def score():
            for key, metric in zip(("ragas_context_precision", "ragas_context_recall"), self.id_metrics):
                value = float(await metric.single_turn_ascore(sample))
                result[key] = value if math.isfinite(value) else None
            result["ragas_ids_status"] = "ok" if retrieved else "precision_undefined_empty_retrieval"
        try:
            asyncio.run(score())
        except Exception as exc:
            result["ragas_ids_status"] = "error:" + type(exc).__name__
        return result

    def score_response(self, query, response, contexts):
        result = {"ragas_faithfulness": None, "ragas_response_relevancy": None,
                  "ragas_response_status": "disabled"}
        if self.mode != "llm":
            return result
        if self.config["status"] != "ready":
            result["ragas_response_status"] = self.config["status"]
            return result
        if not self.judge.api_keys or not self.config["model"]:
            result["ragas_response_status"] = "missing_credentials_or_model"
            return result
        if not response or not contexts:
            result["ragas_response_status"] = "missing_response_or_context"
            return result

        async def usage_hook(http_response):
            await http_response.aread()
            self.usage["http_responses"] += 1
            try:
                payload = http_response.json()
                usage = payload.get("usage") or {}
                if not usage:
                    return
                self.usage["requests_with_usage"] += 1
                if "/embeddings" in http_response.request.url.path:
                    self.usage["embedding_tokens"] += usage.get("total_tokens", 0)
                else:
                    self.usage["input_tokens"] += usage.get("prompt_tokens", 0)
                    self.usage["output_tokens"] += usage.get("completion_tokens", 0)
            except (ValueError, AttributeError):
                pass

        async def score():
            if self.judge.provider == "groq":
                if self._groq_llm is None:
                    from dataclasses import replace
                    from server.ai.llm.factory import build_gateway
                    from server.config import settings
                    from .groq_judge import GroqPoolJudge
                    config = replace(settings, groq_api_keys=self.judge.api_keys,
                                     groq_model=self.judge.model, groq_base_url=self.judge.base_url,
                                     llm_timeout_seconds=self.judge.timeout_seconds)
                    self._groq_llm = GroqPoolJudge(build_gateway(config=config), self.usage)
                await self._score_response_metrics(self._groq_llm, query, response, contexts, result)
                return
            import httpx
            from openai import AsyncOpenAI
            from ragas.llms.base import llm_factory
            async with httpx.AsyncClient(event_hooks={"response": [usage_hook]}) as http:
                async with AsyncOpenAI(api_key=self.judge.api_keys[0],
                                       base_url=self.judge.base_url,
                                       timeout=self.config["timeout_seconds"], max_retries=0,
                                       http_client=http) as client:
                    llm = llm_factory(self.config["model"], client=client, temperature=0, max_retries=1)
                    await self._score_response_metrics(llm, query, response, contexts, result, client=client)
        try:
            asyncio.run(score())
        except Exception as exc:
            result["ragas_response_status"] = "error:" + type(exc).__name__
        rates = [os.getenv("RAGAS_INPUT_USD_PER_MILLION"), os.getenv("RAGAS_OUTPUT_USD_PER_MILLION"),
                 os.getenv("RAGAS_EMBEDDING_USD_PER_MILLION")]
        if (self.judge.provider == "openai" and all(rates) and self.usage["requests_with_usage"]
                and self.usage["requests_with_usage"] == self.usage["http_responses"]):
            self.config["cost_usd"] = sum(self.usage[key] * float(rate) / 1_000_000
                                          for key, rate in zip(("input_tokens", "output_tokens", "embedding_tokens"), rates))
        elif (self.judge.provider == "groq" and all(rates[:2]) and self.usage["gateway_calls_with_usage"]
              and self.usage["gateway_calls_with_usage"] == self.usage["successful_gateway_calls"]):
            self.config["cost_usd"] = sum(self.usage[key] * float(rate) / 1_000_000
                                          for key, rate in zip(("input_tokens", "output_tokens"), rates[:2]))
            self.config["cost_scope"] = "observed_successful_gateway_calls_only"
        return result

    async def _score_response_metrics(self, llm, query, response, contexts, result, *, client=None):
        from ragas.metrics.collections import Faithfulness, AnswerRelevancy
        statuses = []
        try:
            value = await asyncio.wait_for(Faithfulness(llm=llm).ascore(
                user_input=query, response=response, retrieved_contexts=contexts),
                timeout=self.config["timeout_seconds"])
            result["ragas_faithfulness"] = float(value.value) if math.isfinite(value.value) else None
            statuses.append("faithfulness:ok" if result["ragas_faithfulness"] is not None else "faithfulness:undefined")
        except Exception as exc:
            statuses.append("faithfulness:error:" + type(exc).__name__)
        backend = self.judge.embedding_backend
        if backend == "none":
            statuses.append("response_relevancy:disabled_embeddings")
        elif not self.judge.embedding_model:
            statuses.append("response_relevancy:missing_embedding_model")
        elif backend not in {"sentence_transformers", "openai"} or (backend == "openai" and client is None):
            statuses.append("response_relevancy:unsupported_embedding_backend")
        else:
            try:
                if backend == "sentence_transformers":
                    from importlib.util import find_spec
                    if find_spec("sentence_transformers") is None:
                        statuses.append("response_relevancy:missing_semantic_dependency")
                        result["ragas_response_status"] = ";".join(statuses)
                        return
                    from .groq_judge import LocalSemanticEmbeddings
                    if self._local_embeddings is None:
                        self._local_embeddings = LocalSemanticEmbeddings(self.judge.embedding_model)
                    embeddings = self._local_embeddings
                else:
                    from ragas.embeddings.base import embedding_factory
                    embeddings = embedding_factory("openai", model=self.judge.embedding_model, client=client)
                value = await asyncio.wait_for(AnswerRelevancy(llm=llm, embeddings=embeddings,
                                                              strictness=3).ascore(
                    user_input=query, response=response), timeout=self.config["timeout_seconds"])
                result["ragas_response_relevancy"] = float(value.value) if math.isfinite(value.value) else None
                statuses.append("response_relevancy:ok" if result["ragas_response_relevancy"] is not None
                                else "response_relevancy:undefined")
            except Exception as exc:
                statuses.append("response_relevancy:error:" + type(exc).__name__)
        result["ragas_response_status"] = ";".join(statuses)
