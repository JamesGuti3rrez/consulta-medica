from server.ai.agents.base import PROMPTS_DIR
from server.ai.agents.reformulador import QuestionReformulator, reformulate_without_llm
from server.ai.llm.base import LLMResult


def test_rule_turns_student_order_into_question_for_the_patient():
    assert reformulate_without_llm("pregúntale si tiene alergias") == "¿Tiene alergias?"
    assert reformulate_without_llm("Pregúntele al paciente desde cuándo le duele") == "¿Desde cuándo le duele?"
    assert reformulate_without_llm("dígale que me cuente qué medicamentos toma") == "¿Me cuente qué medicamentos toma?"
    assert reformulate_without_llm("¿Tiene fiebre?") == "¿Tiene fiebre?"


class FixedGateway:
    def __init__(self, text, provider="groq-1"):
        self.text, self.provider, self.messages = text, provider, None

    def generate(self, messages, *, temperature=0.0):
        self.messages = messages
        return LLMResult(text=self.text, provider=self.provider, model="m", input_tokens=7, output_tokens=3)


def test_llm_reformulation_receives_only_the_student_message():
    gateway = FixedGateway("¿Tiene usted alguna alergia?")
    result = QuestionReformulator(gateway, PROMPTS_DIR).reformulate("pregúntale si tiene alergias")
    assert result.text == "¿Tiene usted alguna alergia?"
    assert result.used_llm
    assert [m["role"] for m in gateway.messages] == ["system", "user"]
    assert gateway.messages[1]["content"] == "pregúntale si tiene alergias"


def test_local_provider_falls_back_to_rule():
    gateway = FixedGateway("No hay evidencia adicional autorizada para esta solicitud.", provider="local-development")
    result = QuestionReformulator(gateway, PROMPTS_DIR).reformulate("pregúntale si tiene alergias")
    assert result.text == "¿Tiene alergias?"
    assert not result.used_llm
