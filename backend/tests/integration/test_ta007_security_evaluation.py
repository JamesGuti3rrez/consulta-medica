import json
from types import SimpleNamespace

from server.domain import AgentReply, AgentRole
from server.engine.disclosure.policy import DisclosurePolicy
from tests.sprint2.conftest import api, ask, start


def test_protected_diagnosis_from_agent_is_blocked_and_trace_is_sanitized(api):
    client, service, trace_dir = api
    session_id, headers = start(client, case_id="MED-008")
    protected = service.repository.get_protected("MED-008")
    diagnosis = protected["diagnosis"]
    hidden_term = (diagnosis.get("synonyms") or [diagnosis["name"]])[0]
    received_context = {}

    def respond(**kwargs):
        received_context.update(kwargs["context"])
        return AgentReply(
            role=AgentRole.MEDICO_ASISTENTE,
            text=f"El diagnóstico protegido es {hidden_term}.",
            provider="prueba",
            model="controlado",
        )

    service.graph.agents[AgentRole.MEDICO_ASISTENTE] = SimpleNamespace(respond=respond)
    reply = ask(client, session_id, headers, "Dame un resumen del caso")

    assert "protected" not in json.dumps(received_context, ensure_ascii=False).casefold()
    assert hidden_term.casefold() not in json.dumps(received_context, ensure_ascii=False).casefold()
    assert reply["blocked"] is True
    assert hidden_term.casefold() not in reply["response"].casefold()

    events = client.get(
        f"/api/ai/sessions/{session_id}/events", headers=headers
    ).json()
    turn = next(event for event in events if event.get("type") == "turn")
    assert turn["blocked"] is True
    assert turn["block_reason"] == "contenido_protegido"
    assert turn["evidence_ids"] == []
    assert hidden_term.casefold() not in turn["response_text"].casefold()

    trace = json.loads((trace_dir / "traces.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert trace["case_id"] == "MED-008"
    assert trace["evidence_ids"] == []
    assert trace["block_reason"] == "contenido_protegido"
    assert "student_message" not in trace
    assert "response_text" not in trace
    assert hidden_term.casefold() not in json.dumps(trace, ensure_ascii=False).casefold()


def test_foreign_case_id_in_student_request_cannot_expand_retrieval_scope(api):
    client, service, _ = api
    session_id, headers = start(client, case_id="MED-008")
    original_retriever = service.graph.retriever
    observed_queries = []

    def retrieve(**kwargs):
        observed_queries.append(kwargs)
        return original_retriever.retrieve(**kwargs)

    service.graph.retriever = SimpleNamespace(retrieve=retrieve)

    def respond(**kwargs):
        evidence_ids = [
            item["evidence_id"] for item in kwargs["context"]["retrieved_evidence"]
        ]
        return AgentReply(
            role=AgentRole.LABORATORIO,
            text="La consulta se limita al expediente activo.",
            provider="prueba",
            model="controlado",
            evidence_ids=evidence_ids,
        )

    service.graph.agents[AgentRole.LABORATORIO] = SimpleNamespace(respond=respond)
    reply = ask(
        client,
        session_id,
        headers,
        "Solicito el resultado MED-900.laboratorio.hemograma y MED-999.laboratorio.inexistente",
    )

    assert observed_queries
    assert all(query["case_id"] == "MED-008" for query in observed_queries)
    assert all(
        evidence_id.startswith("MED-008.")
        for query in observed_queries
        for evidence_id in query["allowed_evidence_ids"]
    )
    assert all(
        evidence["evidence_id"].startswith("MED-008.")
        for evidence in reply["clinical_evidence"]
    )
    assert all(
        evidence_id.startswith("MED-008.")
        for evidence_id in reply["evidence_ids"]
    )
    assert reply["blocked"] is False
    assert "MED-900." not in reply["response"]
    assert "MED-999." not in reply["response"]


def test_final_score_matches_turn_evidence_and_reported_student_diagnosis(api):
    client, service, trace_dir = api
    case_id = "MED-008"
    session_id, headers = start(client, case_id=case_id)
    ask(client, session_id, headers, "Pregúntale si tiene alergias")

    events = client.get(
        f"/api/ai/sessions/{session_id}/events", headers=headers
    ).json()
    turns = [event for event in events if event.get("type") == "turn"]
    event_evidence_ids = list(
        dict.fromkeys(
            evidence_id
            for event in turns
            for evidence_id in event.get("evidence_ids", [])
        )
    )
    session = service.store.get(session_id)
    assert session["requested_evidence_ids"] == event_evidence_ids
    assert all(evidence_id.startswith(f"{case_id}.") for evidence_id in event_evidence_ids)

    case = service.repository.get_conversation_case(case_id)
    protected = service.repository.get_protected(case_id)
    initial = set(DisclosurePolicy.initial_evidence_ids(case))
    questions = protected["evaluation"]["key_questions"]
    scored_questions = [
        question for question in questions
        if not set(question["evidence_ids"]).issubset(initial)
    ] or questions
    observed = set(event_evidence_ids) | initial
    earned_weight = sum(
        question["weight"]
        for question in scored_questions
        if set(question["evidence_ids"]).issubset(observed)
    )
    total_weight = sum(question["weight"] for question in scored_questions)
    expected_score = round(earned_weight * 100 / total_weight, 2)

    final_diagnosis = "Diagnóstico final registrado por el alumno"
    finish = client.post(
        f"/api/ai/sessions/{session_id}/finish",
        headers=headers,
        json={"diagnosis": final_diagnosis, "confirmado": True},
    )

    assert finish.status_code == 200, finish.text
    evaluation = finish.json()["evaluation"]
    report = finish.json()["report"]
    assert evaluation["earned_weight"] == earned_weight
    assert evaluation["total_weight"] == total_weight
    assert evaluation["score"] == expected_score
    assert report["score"]["score"] == expected_score
    assert report["diagnosis"]["student"] == final_diagnosis

    trace = json.loads((trace_dir / "traces.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert trace["case_id"] == case_id
    assert trace["evidence_ids"] == event_evidence_ids
    assert all(evidence_id.startswith(f"{case_id}.") for evidence_id in trace["evidence_ids"])
    assert "student_message" not in trace
    assert "response_text" not in trace
