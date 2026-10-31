from __future__ import annotations

import hashlib
import re
import time

from server.domain import AgentRole
from server.engine.disclosure.context import ContextAssembler
from server.engine.disclosure.policy import DisclosurePolicy
from server.engine.disclosure.synthetic_scope import outside_clinical_scope
from server.engine.safety.protected_lexicon import ProtectedLexiconService
from server.guardrails import OutputGuard
from server.orchestration.router import DecisionRouter
from server.rag.retrieval_log import RetrievalLogger
from .metrics import retrieval_metrics

SAFE_ID = re.compile(r"^[A-Z]{3,5}-\d{3}(?:\.[a-zA-Z0-9_]+)+$")
SECURITY_ERRORS = {"cross_case_leak", "unauthorized_evidence", "protected_content", "protected_response"}


class HashedRetrievalLogger(RetrievalLogger):
    """La traza auxiliar del adaptador embebido tampoco persiste la consulta cruda."""

    def write(self, payload):
        safe = dict(payload)
        safe["query_sha256"] = text_hash(str(safe.pop("query", "")))
        super().write(safe)


def text_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def safe_id(value):
    return value if SAFE_ID.fullmatch(value) else "redacted:" + text_hash(value)


def inspect_results(results, *, case_id, allowed, canonical, forbidden_terms):
    errors = set()
    traces = []
    guard = OutputGuard()
    for rank, item in enumerate(results, 1):
        if not item.evidence_id.startswith(case_id + "."):
            errors.add("cross_case_leak")
        if item.evidence_id not in allowed:
            errors.add("unauthorized_evidence")
        if item.evidence_id not in canonical:
            errors.add("noncanonical_evidence")
        if not guard.validate(item.text, forbidden_terms)[0]:
            errors.add("protected_content")
        traces.append({"rank": rank, "evidence_id": safe_id(item.evidence_id),
                       "score": item.score, "context_sha256": text_hash(item.text),
                       "provenance": "canonical_case" if item.evidence_id in canonical else "noncanonical"})
    ids = [item.evidence_id for item in results]
    if len(ids) != len(set(ids)):
        errors.add("duplicate_results")
    return errors, traces


def evaluate(records, repository, retriever, ks, ragas, *, generate_responses=False, on_complete=None):
    router, policy = DecisionRouter(), DisclosurePolicy()
    lexicon = ProtectedLexiconService(repository)
    agents, reformulator = None, None
    if generate_responses:
        from server.ai.agents.base import PROMPTS_DIR
        from server.ai.agents.registry import build_agents
        from server.ai.agents.reformulador import QuestionReformulator
        from server.ai.llm.factory import build_gateway
        gateway = build_gateway()
        agents = build_agents(gateway)
        reformulator = QuestionReformulator(gateway, PROMPTS_DIR)
    rows, traces = [], []
    for index, record in enumerate(records, 1):
        started = time.perf_counter()
        case_id, query = record["case_id"], record["query"]
        case = repository.get_conversation_case(case_id)
        route = router.route(query)
        allowed = policy.authorize(case=case, role=route.target, intent=route.intent,
                                   student_message=query).allowed_evidence_ids
        if outside_clinical_scope(query):
            allowed = []
        terms = lexicon.for_case(case_id)
        public = DisclosurePolicy.initial_evidence_ids(case)
        public_available = set(record.get("public_context_ids", [])) <= set(public)
        canonical = {item["evidence_id"] for item in case["on_request"]}
        retrieval_query = query
        response_status, response, provider, model = "not_requested", "", None, None
        generation_input_tokens = generation_output_tokens = None
        reformulation = None
        if reformulator and route.target == AgentRole.PACIENTE:
            try:
                reformulation = reformulator.reformulate(query, temperature=0)
                retrieval_query = reformulation.text
            except Exception:
                response_status = "reformulation_error"
        results, retrieval_status, retrieval_exception = [], "ok", None
        try:
            results = retriever.retrieve(query=retrieval_query, case_id=case_id, agent_role=route.target,
                                         allowed_evidence_ids=allowed, top_k=max(ks), session_id=None)
        except Exception as exc:
            retrieval_status, retrieval_exception = "error", type(exc).__name__
        errors, ranked = inspect_results(results, case_id=case_id, allowed=allowed,
                                         canonical=canonical, forbidden_terms=terms)
        if not public_available:
            errors.add("missing_public_context")
        if len(results) > max(ks):
            errors.add("top_k_contract_exceeded")
        response_scores = {"ragas_faithfulness": None, "ragas_response_relevancy": None,
                           "ragas_response_status": "missing_response" if ragas.mode == "llm" else "disabled"}
        context = None
        if agents and retrieval_status == "ok" and not errors & SECURITY_ERRORS:
            try:
                context = ContextAssembler().build(case=case, role=route.target,
                                                   revealed_evidence_ids=public, retrieved=results)
                reply = agents[route.target].respond(student_message=retrieval_query, context=context, temperature=0)
                response, provider, model = reply.text, reply.provider, reply.model
                generation_input_tokens, generation_output_tokens = reply.input_tokens, reply.output_tokens
                response_status = "ok"
                if not OutputGuard().validate(response, terms)[0]:
                    errors.add("protected_response")
                    response_status = "blocked"
                else:
                    # Usar TODO el contexto visible del agente, incluido el público; nunca protected.
                    contexts = [str(item.get("text") or item.get("value") or item.get("label", ""))
                                for key in ("public_evidence", "revealed_evidence", "retrieved_evidence")
                                for item in context[key]]
                    response_scores = ragas.score_response(retrieval_query, response, contexts)
                    score = response_scores["ragas_faithfulness"]
                    if score is not None and score < 1:
                        errors.add("unsupported_response_claims")
            except Exception as exc:
                response_status = "error:" + type(exc).__name__
        elif agents:
            response_status = "skipped_unsafe_or_retrieval_error"
        raw_ids = [item.evidence_id for item in results]
        safe_query = query if OutputGuard().validate(query, terms)[0] else "[consulta protegida omitida]"
        traces.append({"test_id": record["test_id"], "case_id": case_id,
                       "role": route.target.value, "intent": route.intent.value,
                       "allowed_evidence_ids": allowed, "ranked_results": ranked,
                       "initial_public_context_ids": public,
                       "retrieval_query_sha256": text_hash(retrieval_query),
                       "response_sha256": text_hash(response) if response else None,
                       "response_context_ids": [safe_id(value) for value in public + raw_ids] if context else [],
                       "response_status": response_status,
                       "response_context_k": max(ks), "provider": provider, "model": model,
                       "input_tokens": generation_input_tokens, "output_tokens": generation_output_tokens,
                       "reformulation_provider": reformulation.provider if reformulation else None,
                       "reformulation_input_tokens": reformulation.input_tokens if reformulation else None,
                       "reformulation_output_tokens": reformulation.output_tokens if reformulation else None,
                       "retrieval_status": retrieval_status, "exception_type": retrieval_exception,
                       "errors": sorted(errors), "latency_ms": round((time.perf_counter() - started) * 1000, 3)})
        for k in ks:
            expected = record["expected_evidence_ids"]
            found = raw_ids[:k]
            row_errors = set(errors)
            if retrieval_status == "ok":
                missing = sorted(set(expected) - set(found))
                irrelevant = sorted(set(found) - set(expected))
                if missing:
                    row_errors.add("missing_expected")
                    if set(missing) - set(allowed):
                        row_errors.add("expected_not_authorized")
                if irrelevant:
                    row_errors.add("irrelevant_results")
                if expected and not found:
                    row_errors.add("empty_retrieval")
                metrics = retrieval_metrics(expected, raw_ids, k)
                ragas_ids = ragas.score_ids(expected, found)
            else:
                missing, irrelevant = [], []
                row_errors.add("retrieval_error")
                metrics = dict.fromkeys(("precision", "recall", "hit", "abstention"))
                ragas_ids = {"ragas_context_precision": None, "ragas_context_recall": None,
                             "ragas_ids_status": "retrieval_error"}
            rows.append({"test_id": record["test_id"], "case_id": case_id,
                         "specialty": record["specialty"], "scenario": record["scenario"],
                         "query": safe_query, "expected_evidence_ids": expected,
                         "retrieved_evidence_ids": [safe_id(value) for value in found],
                         "k": k, **metrics, "missing_evidence_ids": missing,
                         "irrelevant_evidence_ids": [safe_id(value) for value in irrelevant],
                         "empty_retrieval": retrieval_status == "ok" and not found,
                         "retrieval_status": retrieval_status, "response_status": response_status,
                         "response_context_k": max(ks) if context else None,
                         "security_failure": bool(row_errors & SECURITY_ERRORS),
                         "errors": sorted(row_errors), **ragas_ids, **response_scores})
        if on_complete:
            on_complete(index, len(records), record["test_id"], rows, traces)
    return rows, traces
