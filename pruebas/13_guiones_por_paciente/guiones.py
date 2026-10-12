"""Guion de prueba de cada paciente: qué preguntar (en orden) y qué no preguntar.

Fuente única para la batería (bateria_guiones.py) y para el documento «Guiones por paciente».

- PREGUNTAR: (pedido, agente que debe responder, datos que debe revelar). Los datos son el final del
  evidence_id («antecedente.alergias»); una lista vacía significa que no revela nada nuevo.
- NO_PREGUNTAR: (pedido, motivo). Cosas que el caso no tiene o que el estudiante no debe hacer: el
  simulador debe responder con naturalidad, sin revelar datos ni el diagnóstico.
- NOTA: algo que conviene saber del caso al probarlo.
"""

DOLOR_TORACICO = [
    ("¿Cómo es el dolor? Descríbalo, por favor", "paciente", ["anamnesis.caracteristicas_dolor"]),
    ("Pregúntele cuándo empezó y cómo ha evolucionado", "paciente", ["anamnesis.inicio_evolucion"]),
    ("¿Tiene algún otro síntoma?", "paciente", ["sintoma.sintomas_acompanantes"]),
    ("Pregúntele por sus antecedentes de enfermedades", "paciente", ["antecedente.antecedentes"]),
    ("¿Toma algún medicamento?", "paciente", ["medicacion.tratamiento_habitual"]),
    ("¿Tiene alergias?", "paciente", ["antecedente.alergias"]),
    ("¿Fuma? ¿Ha hecho algún viaje reciente?", "paciente", ["antecedente.habitos"]),
    ("¿Alguien en su familia ha tenido problemas del corazón?", "paciente", ["antecedente.antecedentes_familiares"]),
    ("Voy a realizar la exploración física completa", "medico_asistente", ["examen.exploracion_fisica"]),
    ("Pido un electrocardiograma de 12 derivaciones", "laboratorio", ["estudio.electrocardiograma"]),
    ("Solicito troponina", "laboratorio", ["lab.troponina"]),
    ("Solicito dímero D", "laboratorio", ["lab.dimero_d"]),
    ("Pido una radiografía de tórax", "radiologia", ["imagen.radiografia_torax"]),
    ("Solicito una angiotomografía de tórax", "radiologia", ["imagen.angiotomografia_torax"]),
]
NO_DOLOR_TORACICO = [
    ("¿Qué tiene el paciente? Dígame el diagnóstico", "El diagnóstico lo debe deducir el estudiante."),
    ("¿Le duele la cabeza?", "El caso no tiene ese síntoma: debe responder que no."),
    ("Pido una ecografía abdominal", "El caso no tiene ese estudio."),
    ("Solicito un hemograma", "El caso no tiene ese examen."),
]

GUIONES = {
    "EME-101": {
        "preguntar": DOLOR_TORACICO,
        "no_preguntar": [*NO_DOLOR_TORACICO,
                         ("Le doy morfina y lo mando a casa", "Tratamiento inadecuado: debe ir a reperfusión urgente.")],
        "nota": "Familia de dolor torácico. Lo decisivo: el dolor opresivo y el electrocardiograma con elevación del ST en cara inferior.",
    },
    "EME-102": {
        "preguntar": DOLOR_TORACICO,
        "no_preguntar": [*NO_DOLOR_TORACICO,
                         ("Le indico amoxicilina", "Es alérgico a la penicilina; además, el cuadro no es una infección.")],
        "nota": "Familia de dolor torácico. Lo decisivo: dolor que empeora al respirar, viaje largo, pantorrilla hinchada y angiotomografía.",
    },
    "EME-103": {
        "preguntar": DOLOR_TORACICO,
        "no_preguntar": [*NO_DOLOR_TORACICO,
                         ("Le indico aspirina y heparina", "Contraindicado: en la disección aumenta el riesgo de sangrado y de rotura de la aorta.")],
        "nota": "Familia de dolor torácico. Lo decisivo: medir la presión en ambos brazos (exploración física) y la angiotomografía. El dímero D alto no lo distingue de la tromboembolia.",
    },
    "EME-001": {
        "preguntar": [
            ("Pregúntele por sus antecedentes de enfermedades", "paciente", ["antecedente.antecedentes"]),
            ("¿Qué medicamentos toma?", "paciente", ["medicacion.tratamiento_habitual"]),
            ("Voy a examinar al paciente", "medico_asistente", ["examen.exploracion_fisica"]),
        ],
        "no_preguntar": [
            ("¿Tiene alergias?", "El caso no registra alergias: debe responder que no."),
            ("Solicito un hemograma", "El caso no tiene exámenes de laboratorio."),
            ("Le doy paracetamol para la fiebre", "No sustituye al enfriamiento activo inmediato."),
        ],
        "nota": "El paciente llega confundido (Glasgow 10). En la simulación igual responde: tómese como la información que dan sus compañeros.",
    },
    "EME-002": {
        "preguntar": [
            ("¿Tiene alguna enfermedad?", "paciente", ["antecedente.antecedentes"]),
            ("Voy a realizar la exploración física", "medico_asistente", ["examen.exploracion_fisica"]),
        ],
        "no_preguntar": [
            ("¿Ha tenido fiebre antes de hoy?", "El caso no lo describe: debe responder que no."),
            ("Pido una tomografía de cráneo", "Sería lo indicado, pero el caso de origen no trae el resultado."),
        ],
        "nota": "Caso corto: el diagnóstico sale del inicio súbito de la cefalea y de la rigidez de nuca en la exploración.",
    },
    "CIR-005": {
        "preguntar": [
            ("¿Alguien en su familia tiene problemas de sangrado?", "paciente", ["antecedente.antecedentes_familiares"]),
            ("Solicito pruebas de coagulación", "laboratorio", ["lab.coagulacion_preoperatoria", "lab.coagulacion_posoperatoria"]),
        ],
        "no_preguntar": [
            ("¿Toma algún medicamento?", "El caso no lo registra: debe responder que no."),
            ("Pido una tomografía de abdomen", "El caso no tiene ese estudio."),
        ],
        "nota": "La clave es comparar la coagulación antes y después: solo el tiempo de tromboplastina parcial sale prolongado.",
    },
    "CIR-006": {
        "preguntar": [
            ("¿Qué enfermedades tiene?", "paciente", ["antecedente.antecedentes"]),
            ("¿Fuma?", "paciente", ["anamnesis.habitos"]),
            ("Voy a examinar a la paciente y auscultar los pulmones", "medico_asistente", ["examen.exploracion_fisica"]),
        ],
        "no_preguntar": [
            ("¿Le duele la herida?", "No lo describe; la exploración muestra que cicatriza bien."),
            ("Pido una radiografía de tórax", "Sería útil, pero el caso de origen no trae el resultado."),
        ],
        "nota": "Fiebre, taquicardia y crepitantes en la base derecha al quinto día de la cirugía.",
    },
    "GOB-003": {
        "preguntar": [
            ("¿Cómo fue el parto?", "paciente", ["antecedente.evolucion_parto"]),
            ("Voy a tomar los signos vitales", "medico_asistente", ["vital.signos_vitales"]),
            ("Voy a realizar la exploración física", "medico_asistente", ["examen.exploracion_fisica"]),
        ],
        "no_preguntar": [
            ("¿Tiene fiebre?", "El caso no lo describe: debe responder que no."),
            ("Solicito hormonas tiroideas", "El caso no tiene ese examen."),
        ],
        "nota": "La clave es la hemorragia del parto con presión de 80/60 y transfusión: explica que no pueda lactar.",
    },
    "GOB-004": {
        "preguntar": [
            ("¿Tiene algún otro síntoma?", "paciente", ["sintoma.sintomas_asociados"]),
            ("Pregúntele por sus antecedentes de enfermedades", "paciente", ["antecedente.antecedentes"]),
            ("¿Toma algún medicamento?", "paciente", ["medicacion.tratamiento_habitual"]),
            ("¿Cuántas parejas sexuales ha tenido? ¿Usa preservativo?", "paciente", ["anamnesis.vida_sexual"]),
            ("Voy a realizar el examen ginecológico", "medico_asistente", ["examen.exploracion_fisica"]),
            ("Mido el pH vaginal", "laboratorio", ["lab.ph_vaginal"]),
        ],
        "no_preguntar": [
            ("¿Ha tenido tos?", "El caso no lo describe: debe responder que no."),
            ("Pido una ecografía pélvica", "El caso no tiene ese estudio."),
        ],
        "nota": "Lo decisivo: cuello uterino en fresa y pH vaginal de 5,8.",
    },
    "MED-008": {
        "preguntar": [
            ("Pregúntele desde cuándo empezó y cómo ha evolucionado", "paciente", ["sintoma.evolucion"]),
            ("¿Ha tomado algún medicamento?", "paciente", ["medicacion.tratamiento_previo"]),
            ("Pregúntele por sus antecedentes de enfermedades", "paciente", ["antecedente.antecedentes"]),
            ("¿Tiene alergias?", "paciente", ["antecedente.alergias"]),
            ("¿Ha hecho alguna actividad al aire libre o algún viaje?", "paciente", ["anamnesis.exposicion"]),
            ("Voy a examinar a la paciente", "medico_asistente", ["examen.exploracion_fisica"]),
        ],
        "no_preguntar": [
            ("¿Tiene tos?", "El caso no tiene ese síntoma: debe responder que no."),
            ("Le indico doxiciclina", "Contraindicado: es alérgica a las tetraciclinas (anafilaxia)."),
        ],
        "nota": "La pregunta de alergias es crítica: el tratamiento habitual de este cuadro es justo el fármaco al que es alérgica.",
    },
    "MED-009": {
        "preguntar": [
            ("Voy a examinar al paciente", "medico_asistente", ["examen.exploracion_fisica"]),
            ("¿Desde cuándo tiene esa lesión?", "paciente", ["sintoma.evolucion"]),
            ("¿Ha trabajado al sol? ¿Usa protector solar?", "paciente", ["anamnesis.exposicion_solar"]),
        ],
        "no_preguntar": [
            ("¿Le duele algo?", "Viene a un control y no tiene molestias."),
            ("Pido una tomografía", "El caso no tiene ese estudio."),
        ],
        "nota": "Sin la exploración no hay pista: la lesión del párpado solo aparece al examinar.",
    },
    "PED-007": {
        "preguntar": [
            ("¿Dónde le duele?", "paciente", ["sintoma.dolor"]),
            ("Pregúntele por sus antecedentes y su desarrollo", "paciente", ["antecedente.antecedentes"]),
            ("Voy a examinar al niño", "medico_asistente", ["examen.exploracion_fisica"]),
            ("Pido una radiografía de cadera", "radiologia", ["imagen.radiografia"]),
        ],
        "no_preguntar": [
            ("¿Ha tenido fiebre?", "Está afebril: debe responder que no."),
            ("Solicito un hemograma", "El caso no tiene ese examen."),
        ],
        "nota": "Trampa: el niño dice que le duele la rodilla, pero la exploración muestra que el dolor viene de la cadera.",
    },
    "PED-010": {
        "preguntar": [
            ("Voy a examinar a la niña", "medico_asistente", ["examen.desarrollo_mamario", "examen.manchas_piel"]),
            ("Solicito función tiroidea", "laboratorio", ["lab.funcion_tiroidea"]),
            ("Pido una radiografía de los huesos", "radiologia", ["imagen.imagen_osea"]),
            ("Solicito la edad ósea", "radiologia", ["imagen.edad_osea"]),
        ],
        "no_preguntar": [
            ("¿Tiene dolor de cabeza?", "El caso no lo describe: debe responder que no."),
            ("Pido una resonancia de cerebro", "El caso no tiene ese estudio."),
        ],
        "nota": "El resultado tiroideo es ambiguo porque la fuente (banco de Taiwán) menciona hipotiroidismo e hipertiroidismo a la vez.",
    },
}
