"""TA-017: diálogo directo; el doctor presenta, entrega hallazgos y aclara solicitudes."""
from types import SimpleNamespace

from server.domain import AgentReply, AgentRole
from tests.sprint2.conftest import api, start, ask


def test_direct_dialogue_ten_turns_have_only_student_and_responding_agent(api):
    client, service, _ = api
    sid, headers = start(client)
    turns = [
        ('¿Desde cuándo tiene la molestia?', 'paciente'),
        ('¿Tiene alergias?', 'paciente'),
        ('¿Qué medicamentos toma?', 'paciente'),
        ('Realizo exploración física', 'medico_asistente'),
        ('¿Le dificulta esa lesión realizar sus actividades diarias?', 'paciente'),
        ('Solicito exámenes', 'medico_asistente'),
        ('Solicito hemograma', 'laboratorio'),
        ('Solicito radiografía', 'radiologia'),
        ('Solicito interconsulta con cardiología', 'especialista'),
        ('¿Cómo se siente?', 'paciente'),
    ]
    for question, role in turns:
        reply = ask(client, sid, headers, question)
        assert reply['agent'] == role
        assert reply['doctor_question'] is None
        assert reply['response']
        if 'exploración' in question:
            assert 'párpado' in reply['response'] and reply['clinical_evidence']
        if question == 'Solicito exámenes':
            assert 'cuál' in reply['response'].lower() or 'tipo' in reply['response'].lower()
    events = client.get(f'/api/ai/sessions/{sid}/events', headers=headers).json()[1:]
    assert len(events) == 10
    assert [(e['student_message'], e['agent']) for e in events] == turns
    assert all(e['doctor_question'] is None for e in events)
    history = service.store.get(sid)['history']
    assert len(history) == 20
    assert [h['role'] for h in history[::2]] == ['student'] * 10
    assert [h['role'] for h in history[1::2]] == [role for _, role in turns]


def test_direct_dialogue_uses_original_question_for_retrieval_and_patient(api):
    client, service, _ = api
    sid, headers = start(client)
    calls = []
    retriever = service.graph.retriever
    def retrieve(**kwargs):
        calls.append(('retrieve', kwargs['query']))
        return retriever.retrieve(**kwargs)
    def respond(**kwargs):
        calls.append(('patient', kwargs['student_message']))
        return AgentReply(role=AgentRole.PACIENTE, text='No tengo alergias conocidas.', provider='prueba', model='controlado', input_tokens=6, output_tokens=8)
    service.graph.retriever = SimpleNamespace(retrieve=retrieve)
    service.graph.agents[AgentRole.PACIENTE] = SimpleNamespace(respond=respond)
    question = 'Pregúntale si tiene alergias'
    reply = ask(client, sid, headers, question)
    assert calls == [('retrieve', question), ('patient', question)]
    assert reply['response'] == 'No tengo alergias conocidas.'
    event = client.get(f'/api/ai/sessions/{sid}/events', headers=headers).json()[-1]
    assert (event['input_tokens'], event['output_tokens']) == (6, 8)


def test_direct_dialogue_ignores_legacy_doctor_echo_in_context_preserving_records(api):
    client, service, _ = api
    sid, headers = start(client)
    old_echo = {'role': 'medico_tratante', 'text': 'PREGUNTA ANTIGUA INTERMEDIADA'}
    state = service.store.get(sid)
    state['history'] = [{'role': 'student', 'text': 'Pregunta anterior'}, old_echo,
                        {'role': 'paciente', 'text': 'Respuesta anterior'}]
    service.store.save(state)
    received = []
    def respond(**kwargs):
        received.extend(kwargs['context']['conversation_tail'])
        return AgentReply(role=AgentRole.PACIENTE, text='No tengo alergias conocidas.', provider='prueba', model='controlado')
    service.graph.agents[AgentRole.PACIENTE] = SimpleNamespace(respond=respond)
    reply = ask(client, sid, headers, '¿Tiene alergias?')
    assert reply['doctor_question'] is None
    assert len(received) == 2 and old_echo not in received
    assert old_echo in service.store.get(sid)['history']  # No se borra la evidencia histórica.
