from server.domain import AgentRole, Intent
from server.orchestration.router import DecisionRouter


def test_requests_for_multiple_agents_are_routed_for_clarification():
    decision = DecisionRouter().route("Solicito un hemograma y una radiografía")

    assert decision.target == AgentRole.MEDICO_ASISTENTE
    assert decision.intent == Intent.ASK_ASSISTANT
    assert DecisionRouter.requests_multiple_specific_agents("Solicito un hemograma y una radiografía")


def test_specific_exam_route_wins_over_general_assistant_or_exam_terms():
    router = DecisionRouter()

    assert router.route("Dame un resumen de los resultados de laboratorio").target == AgentRole.LABORATORIO
    assert router.route("Tomo la presión y pido un electrocardiograma").target == AgentRole.LABORATORIO


def test_only_concrete_exam_names_count_as_a_multiple_request():
    router = DecisionRouter()
    clarified = [
        "Solicito un hemograma y una radiografía",
        "Solicito análisis de sangre y una radiografía de tórax",
        "Solicito tomografía de cráneo y punción para líquido cefalorraquídeo",
        "Pido un examen de orina y una ecografía renal",
    ]
    for message in clarified:
        assert router.route(message).target == AgentRole.MEDICO_ASISTENTE, message
        assert DecisionRouter.requests_multiple_specific_agents(message), message

    # «sangre», «orina», «imagen» o «cirugía» sueltas no son un segundo pedido.
    single = {
        "Solicito hemograma antes de la cirugía": AgentRole.LABORATORIO,
        "Pido una ecografía para ver si hay sangre libre en abdomen": AgentRole.RADIOLOGIA,
        "Solicito una radiografía para tener una imagen del tórax": AgentRole.RADIOLOGIA,
        "Quiero interconsulta con cirugía por sangre en las heces": AgentRole.ESPECIALISTA,
    }
    for message, target in single.items():
        assert not DecisionRouter.requests_multiple_specific_agents(message), message
        assert router.route(message).target == target, message


def test_a_negated_exam_is_not_part_of_the_request():
    router = DecisionRouter()

    for message in ("No necesito radiografía, solo un hemograma", "Solicito hemograma, no una radiografía",
                    "Sin tomografía por ahora; pido un hemograma"):
        assert not DecisionRouter.requests_multiple_specific_agents(message), message
        assert router.route(message).target == AgentRole.LABORATORIO, message


def test_loose_words_alone_keep_the_priority_of_main():
    # Sin pedido concreto se mantiene el orden de main: laboratorio, imagen y especialista.
    assert DecisionRouter().route("¿Ha tenido sangre en la orina?").target == AgentRole.LABORATORIO
    assert DecisionRouter().route("¿Le operaron (cirugía) y vio sangre?").target == AgentRole.LABORATORIO


def test_unknown_clinical_request_uses_the_deterministic_patient_fallback():
    decision = DecisionRouter().route("¿Cómo se siente ahora?")

    assert decision.target == AgentRole.PACIENTE
    assert decision.intent == Intent.ASK_PATIENT


def test_explicit_diagnosis_and_finish_keep_priority_over_ambiguous_keywords():
    router = DecisionRouter()

    diagnosis = router.route("Mi diagnóstico final es migraña y solicito un hemograma")
    finish = router.route("Finalizar consulta y solicitar una radiografía")

    assert diagnosis.intent == Intent.PROPOSE_DIAGNOSIS
    assert finish.intent == Intent.FINISH


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


def test_taking_vital_signs_is_an_examination():
    router = DecisionRouter()
    assert router.route("Voy a tomar los signos vitales").intent == Intent.EXAMINE
    assert router.route("¿Tiene la presión alta?").target == AgentRole.PACIENTE


def test_exams_added_by_the_team_reach_their_agent():
    # Decisión 0002: exámenes que deciden entre diagnósticos parecidos.
    router = DecisionRouter()
    assert router.route("Pido el dosaje del factor VIII y del factor IX").target == AgentRole.LABORATORIO
    assert router.route("Solicito una prolactina sérica").target == AgentRole.LABORATORIO
    assert router.route("Pido un electroencefalograma").target == AgentRole.LABORATORIO


def test_plural_physical_exams_reach_assistant_instead_of_patient():
    router = DecisionRouter()
    for message in (
        "bueno pasemos con los exámenes físicos que tiene que tomar el paciente para empezar a ver cómo está actualmente",
        "Pasemos a los exámenes físicos", "Hagamos una evaluación física", "Voy a revisar al paciente",
    ):
        decision = router.route(message)
        assert decision.target == AgentRole.MEDICO_ASISTENTE
        assert decision.intent == Intent.EXAMINE


def test_unspecified_medical_exams_are_clarified_by_the_assistant():
    router = DecisionRouter()
    for message in ("pasamos por los exámenes médicos", "Quiero solicitar exámenes", "Hagamos unas pruebas",
                    "Solicito un examen médico"):
        decision = router.route(message)
        assert decision.target == AgentRole.MEDICO_ASISTENTE
        assert decision.intent == Intent.ASK_ASSISTANT


def test_specific_exam_agents_take_precedence_over_generic_exam_words():
    router = DecisionRouter()
    for message, target in (
        ("Hagamos exámenes de laboratorio", AgentRole.LABORATORIO),
        ("Solicito un examen de imagen", AgentRole.RADIOLOGIA),
        ("Pido pruebas de coagulación", AgentRole.LABORATORIO),
    ):
        decision = router.route(message)
        assert decision.target == target
