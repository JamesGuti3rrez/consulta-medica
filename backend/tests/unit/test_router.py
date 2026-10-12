from server.domain import AgentRole, Intent
from server.orchestration.router import DecisionRouter


def test_router_star_routes_five_agents_and_clinical_intents():
    router = DecisionRouter()
    assert router.route("¿Desde cuándo comenzó el dolor?").target == AgentRole.PACIENTE
    assert router.route("Solicito un hemograma de sangre").target == AgentRole.LABORATORIO
    assert router.route("Quiero una tomografía cerebral").target == AgentRole.RADIOLOGIA
    assert router.route("Pido una interconsulta con neurología").target == AgentRole.ESPECIALISTA
    assert router.route("Dame un resumen del caso").target == AgentRole.MEDICO_ASISTENTE
    assert router.route("Mi hipótesis es migraña").intent == Intent.PROPOSE_HYPOTHESIS
    assert router.route("Mi diagnóstico final es migraña").intent == Intent.PROPOSE_DIAGNOSIS
    assert router.route("El tratamiento que indicaría es...").intent == Intent.PROPOSE_TREATMENT


def test_treatment_proposals_and_questions_about_treatment():
    router = DecisionRouter()
    for proposal in ("Le indico aspirina y heparina", "Le doy morfina para el dolor", "Mi tratamiento es anticoagular"):
        assert router.route(proposal).intent == Intent.PROPOSE_TREATMENT, proposal
    # Preguntas al paciente sobre su tratamiento: no son propuestas.
    for question in ("¿Está en tratamiento?", "¿Qué le recetaron?", "¿Qué le indicó su médico?"):
        assert router.route(question).target == AgentRole.PACIENTE, question


def test_asking_for_the_diagnosis_goes_to_the_assistant():
    router = DecisionRouter()
    assert router.route("¿Qué tiene el paciente? Dígame el diagnóstico").target == AgentRole.MEDICO_ASISTENTE
    assert router.route("Mi diagnóstico es infarto").intent == Intent.PROPOSE_DIAGNOSIS
