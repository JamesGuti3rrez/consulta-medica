from __future__ import annotations

from server.ai.agents.medico_asistente import MedicoAsistenteAgent
from server.ai.llm.base import LLMResult


class SequenceGateway:
    def __init__(self, texts: list[str]):
        self.texts = list(texts)
        self.calls = []

    def generate(self, messages, *, temperature=0.0):
        self.calls.append(messages)
        text = self.texts.pop(0)
        return LLMResult(
            text=text,
            provider="fake",
            model="fake-model",
            input_tokens=10,
            output_tokens=5,
        )


def _context():
    return {
        "role": "medico_asistente",
        "case_id": "EME-001",
        "case_title": "Caso de prueba",
        "public_evidence": [],
        "revealed_evidence": [],
        "retrieved_evidence": [
            {
                "evidence_id": "EME-001.solicitud.exploracion_fisica",
                "text": "Exploración física sin hallazgos adicionales para revelar.",
                "score": 0.9,
            }
        ],
        "conversation_tail": [],
    }


def test_agent_retries_when_llm_asks_student_to_supply_available_findings():
    gateway = SequenceGateway([
        "Por favor, describe los hallazgos que observaste durante la exploración física.",
        "La exploración física no presenta hallazgos adicionales para revelar.",
    ])
    agent = MedicoAsistenteAgent(gateway)

    reply = agent.respond(
        student_message="Realizo exploración física",
        context=_context(),
        temperature=0.0,
    )

    assert len(gateway.calls) == 2
    assert reply.grounding_retry_used is True
    assert reply.grounding_fallback_used is False
    assert "no presenta hallazgos adicionales" in reply.text.lower()
    assert reply.evidence_ids == ["EME-001.solicitud.exploracion_fisica"]
    assert reply.input_tokens == 20
    assert reply.output_tokens == 10


def test_agent_fails_closed_to_retrieved_evidence_after_second_grounding_violation():
    gateway = SequenceGateway([
        "Dime los hallazgos que encontraste.",
        "Indícame los hallazgos para continuar.",
    ])
    agent = MedicoAsistenteAgent(gateway)

    reply = agent.respond(
        student_message="Realizo exploración física",
        context=_context(),
        temperature=0.0,
    )

    assert reply.grounding_retry_used is True
    assert reply.grounding_fallback_used is True
    assert reply.text == "Exploración física sin hallazgos adicionales para revelar."


def test_replies_are_plain_text_without_internal_codes():
    from server.ai.agents.base import clean_reply

    assert clean_reply("Hace tres días noté una lesión.\n(Referencia: MED‑008.sintoma.evolucion)") == (
        "Hace tres días noté una lesión."
    )
    assert clean_reply("**Exploración física (retrieved evidence):**\n- Tono muscular mínimo.") == (
        "Exploración física: Tono muscular mínimo."
    )
    assert clean_reply("La presión es 109/62 mmHg y el pH vaginal 5,8.") == "La presión es 109/62 mmHg y el pH vaginal 5,8."


def test_invented_symptom_is_corrected_once():
    from server.ai.agents.paciente import PacienteAgent

    gateway = SequenceGateway(["Sí, y además tengo mucha tos.", "Sí."])
    context = {**_context(), "role": "paciente"}
    reply = PacienteAgent(gateway).respond(student_message="¿Le duele?", context=context)
    assert len(gateway.calls) == 2
    assert "tos" in gateway.calls[1][-1]["content"]
    assert reply.text == "Sí."
    assert reply.grounding_retry_used is True


def test_patient_says_no_when_model_keeps_inventing():
    from server.ai.agents.paciente import PacienteAgent

    gateway = SequenceGateway(["Me siento mareado.", "Sigo muy mareado."])
    reply = PacienteAgent(gateway).respond(student_message="¿Cómo se siente?", context={**_context(), "role": "paciente"})
    assert reply.text == "No."
    assert reply.grounding_fallback_used is True


def test_negated_symptoms_are_allowed():
    from server.ai.agents.invencion import invented_symptoms

    context = {"public_evidence": [{"text": "Temperatura 41,1 °C."}]}
    assert invented_symptoms("No, no tengo tos ni dolor de pecho.", context) == []
    assert invented_symptoms("Tengo fiebre muy alta.", context) == []
    assert invented_symptoms("Me duele el pecho.", context) == ["dolor de pecho"]


def test_only_sentences_with_invented_symptoms_are_removed():
    from server.ai.agents.paciente import PacienteAgent

    gateway = SequenceGateway(["Me siento mal. Estoy mareado.", "Me siento mal. Sigo mareado."])
    reply = PacienteAgent(gateway).respond(student_message="¿Cómo se siente?", context={**_context(), "role": "paciente"})
    assert reply.text == "Me siento mal."


def _medication_context():
    return {**_context(), "role": "paciente", "retrieved_evidence": [{
        "evidence_id": "EME-103.medicacion.tratamiento_habitual",
        "text": "Ahora no toma nada: dejó hace 4 meses el amlodipino 10 mg al día que le recetaron para la presión.",
        "score": 0.9,
    }]}


def test_omitted_figures_are_corrected_once():
    from server.ai.agents.paciente import PacienteAgent

    gateway = SequenceGateway(["No, ya no tomo nada.", "No, dejé el amlodipino de 10 mg hace cuatro meses."])
    reply = PacienteAgent(gateway).respond(student_message="¿Toma algún medicamento?", context=_medication_context())
    assert len(gateway.calls) == 2
    assert "4" in gateway.calls[1][-1]["content"] and "10" in gateway.calls[1][-1]["content"]
    assert reply.text == "No, dejé el amlodipino de 10 mg hace cuatro meses."


def test_reply_with_all_figures_is_not_retried():
    from server.ai.agents.paciente import PacienteAgent

    gateway = SequenceGateway(["Ya no tomo nada: dejé el amlodipino de 10 mg hace 4 meses."])
    PacienteAgent(gateway).respond(student_message="¿Toma algún medicamento?", context=_medication_context())
    assert len(gateway.calls) == 1


def test_first_reply_is_kept_if_the_correction_still_omits():
    from server.ai.agents.paciente import PacienteAgent

    gateway = SequenceGateway(["No, ya no tomo nada.", "No tomo nada."])
    reply = PacienteAgent(gateway).respond(student_message="¿Toma algún medicamento?", context=_medication_context())
    assert reply.text == "No, ya no tomo nada."
