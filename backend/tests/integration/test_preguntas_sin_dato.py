"""Preguntas sin dato en el caso: ni el doctor pide al estudiante que invente hallazgos ni el paciente finge no entender.

- Exploración física de un caso sin hallazgos registrados (CIR-005): el doctor lo dice, sin pedir al estudiante que
  describa lo que encontró.
- Si el modelo del doctor, sin datos, pide al estudiante que describa hallazgos, se sustituye por «no disponible».
- Si el generador de datos sintéticos rechaza la pregunta del paciente, responde el agente paciente normal (que dice
  con naturalidad que no lo recuerda) en lugar de «No entendí bien, doctor»; el motivo queda en la auditoría.
- La respuesta del agente que reemplaza al generador pasa los mismos controles que cualquier respuesta del agente.
"""
from types import SimpleNamespace

from server.ai.agents.medico_asistente import MedicoAsistenteAgent
from server.ai.llm.base import LLMResult
from server.domain import AgentReply, AgentRole
from server.orchestration.patient_completion import Completion
from tests.sprint2.conftest import api, start, ask  # noqa: F401
from tests.unit.test_patient_completion import KEYS, clinical, make_service, run  # noqa: F401

SIN_HALLAZGOS = "No hay hallazgos de exploración física registrados para este paciente."
NO_ENTENDI = "No entendí bien"


def test_exploracion_sin_hallazgos_registrados_no_pide_al_estudiante_que_los_describa(api):
    client, service, _ = api
    sid, headers = start(client, case_id="CIR-005")
    reply = ask(client, sid, headers, "Realizo exploración física")
    assert reply["agent"] == "medico_asistente"
    assert reply["response"] == SIN_HALLAZGOS
    assert reply["evidence_ids"] == [] and not reply["blocked"]
    event = client.get(f"/api/ai/sessions/{sid}/events", headers=headers).json()[-1]
    assert event["provider"] == "reglas"


def test_exploracion_con_hallazgos_registrados_los_entrega(api):
    client, service, _ = api
    sid, headers = start(client, case_id="MED-008")
    reply = ask(client, sid, headers, "Realizo exploración física")
    assert reply["agent"] == "medico_asistente" and reply["response"] != SIN_HALLAZGOS
    assert reply["clinical_evidence"]


class _Gateway:
    def __init__(self, text):
        self.text, self.calls = text, 0

    def generate(self, messages, *, temperature):
        self.calls += 1
        return LLMResult(text=self.text, provider="fake", model="test", input_tokens=4, output_tokens=3)


def test_doctor_sin_datos_que_pide_describir_hallazgos_se_sustituye():
    gateway = _Gateway("Anotado. Por favor, describe los hallazgos que encuentres en la exploración física.")
    reply = MedicoAsistenteAgent(gateway).respond(student_message="¿Cómo está la piel?", context={"retrieved_evidence": []})
    assert reply.text == MedicoAsistenteAgent.missing_data_reply
    assert "describ" not in reply.text.lower() and reply.grounding_fallback_used
    assert gateway.calls == 1


def test_doctor_sin_datos_que_responde_bien_no_se_toca():
    texto = "Lo anoto; se revisará al cerrar la consulta. Siga reuniendo datos."
    reply = MedicoAsistenteAgent(_Gateway(texto)).respond(student_message="Creo que es apendicitis",
                                                          context={"retrieved_evidence": []})
    assert reply.text == texto and not reply.grounding_fallback_used


def test_rechazo_del_generador_deja_responder_al_agente_paciente(clinical):
    # Una selección mal formada hace que el generador rechace sin escribir nada.
    service, _ = make_service([{"alcance": "caso", "claves": "sintoma_inventado"}])
    result = run(service, clinical, question="¿Desde cuándo tiene el dolor?")
    assert result.validation_rejected and result.rejection_reason.startswith("seleccionar:ValueError:")
    assert result.reply is None and result.selector_usage == (10, 5)
    assert not service.store.rows


def _rechazo(**_):
    return Completion(validation_rejected=True, rejection_reason="generar:ValueError:prueba", selector_usage=(7, 2))


def test_paciente_responde_con_naturalidad_cuando_el_generador_rechaza(api):
    client, service, _ = api
    service.graph.patient_completion = SimpleNamespace(complete=_rechazo)
    service.graph.agents[AgentRole.PACIENTE] = SimpleNamespace(respond=lambda **_: AgentReply(
        role=AgentRole.PACIENTE, text="No recuerdo con precisión cuándo empezó el dolor.", provider="prueba",
        model="controlado", input_tokens=5, output_tokens=6))
    sid, headers = start(client, case_id="CIR-005")
    reply = ask(client, sid, headers, "¿Desde cuándo tiene el dolor?")
    assert reply["agent"] == "paciente"
    assert reply["response"] == "No recuerdo con precisión cuándo empezó el dolor."
    assert NO_ENTENDI not in reply["response"] and not reply["blocked"]
    event = client.get(f"/api/ai/sessions/{sid}/events", headers=headers).json()[-1]
    assert event["synthetic_rejection_reason"] == "generar:ValueError:prueba"
    assert (event["input_tokens"], event["output_tokens"]) == (12, 8)


def test_la_respuesta_del_agente_tras_el_rechazo_pasa_los_controles(api):
    client, service, _ = api
    service.graph.patient_completion = SimpleNamespace(complete=_rechazo)
    service.graph.agents[AgentRole.PACIENTE] = SimpleNamespace(respond=lambda **_: AgentReply(
        role=AgentRole.PACIENTE, text="Me duele desde hace 37 días.", provider="prueba", model="controlado"))
    sid, headers = start(client, case_id="CIR-005")
    reply = ask(client, sid, headers, "¿Desde cuándo tiene el dolor?")
    # 37 no está en el caso: una cifra inventada por el agente se bloquea igual que sin generador.
    assert "37" not in reply["response"] and reply["blocked"]


# «¿Desde cuándo…?» sobre la molestia actual no pide el año de un antecedente (antes respondía el de la hipertensión).
import pytest  # noqa: E402

from server.engine.disclosure.synthetic_scope import candidate_topics  # noqa: E402


@pytest.mark.parametrize("pregunta", ["¿Desde cuándo tiene la molestia?", "¿Desde cuándo tiene el dolor?",
                                      "¿Hace cuánto le duele?", "¿Desde cuándo tiene esa lesión en el párpado?",
                                      "¿Hace cuánto tiene fiebre?"])
def test_inicio_de_la_molestia_actual_no_es_inicio_de_un_antecedente(pregunta):
    assert "inicio_antecedentes" not in candidate_topics(pregunta)


@pytest.mark.parametrize("pregunta", ["¿Desde cuándo tiene hipertensión?", "¿En qué año le diagnosticaron la diabetes?",
                                      "¿Hace cuánto le dio la presión alta?", "¿Qué edad tenía cuando le dio?"])
def test_inicio_de_un_antecedente_se_sigue_reconociendo(pregunta):
    assert "inicio_antecedentes" in candidate_topics(pregunta)
