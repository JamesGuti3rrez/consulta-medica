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
