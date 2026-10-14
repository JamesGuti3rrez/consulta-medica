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
            ("Solicito función tiroidea", "laboratorio", ["lab.funcion_tiroidea"]),
            ("Pido un electroencefalograma", "laboratorio", ["estudio.electroencefalograma"]),
        ],
        "no_preguntar": [
            ("¿Tiene alergias?", "El caso no registra alergias: debe responder que no."),
            ("Solicito un hemograma", "El caso no trae hemograma: solo función tiroidea y electroencefalograma."),
            ("Le doy paracetamol para la fiebre", "No sustituye al enfriamiento activo inmediato."),
        ],
        "nota": "El paciente llega confundido (Glasgow 10). En la simulación igual responde: tómese como la información que dan sus compañeros.",
    },
    "EME-002": {
        "preguntar": [
            ("¿Tiene alguna enfermedad?", "paciente", ["antecedente.antecedentes"]),
            ("Voy a realizar la exploración física", "medico_asistente", ["examen.exploracion_fisica"]),
            ("Solicito una tomografía de cráneo sin contraste", "radiologia", ["imagen.tomografia_craneo"]),
        ],
        "no_preguntar": [
            ("¿Ha tenido fiebre antes de hoy?", "El caso no lo describe: debe responder que no."),
            ("Pido una resonancia magnética", "El caso no tiene ese estudio: la tomografía basta."),
        ],
        "nota": "Caso corto: el diagnóstico sale del inicio súbito de la cefalea y de la rigidez de nuca; la tomografía (complemento del equipo) lo confirma y descarta un hematoma.",
    },
    "CIR-005": {
        "preguntar": [
            ("¿Alguien en su familia tiene problemas de sangrado?", "paciente", ["antecedente.antecedentes_familiares"]),
            ("Solicito pruebas de coagulación", "laboratorio", ["lab.coagulacion_preoperatoria", "lab.coagulacion_posoperatoria"]),
            ("Pido el dosaje del factor VIII y del factor IX", "laboratorio", ["lab.factores_coagulacion"]),
        ],
        "no_preguntar": [
            ("¿Toma algún medicamento?", "El caso no lo registra: debe responder que no."),
            ("Pido una tomografía de abdomen", "El caso no tiene ese estudio."),
        ],
        "nota": "La clave es comparar la coagulación antes y después: solo el tiempo de tromboplastina parcial sale prolongado. El dosaje de factores (complemento del equipo) distingue hemofilia A de B.",
    },
    "CIR-006": {
        "preguntar": [
            ("¿Qué enfermedades tiene?", "paciente", ["antecedente.antecedentes"]),
            ("¿Fuma?", "paciente", ["anamnesis.habitos"]),
            ("Voy a examinar a la paciente y auscultar los pulmones", "medico_asistente", ["examen.exploracion_fisica"]),
            ("Pido una radiografía de tórax", "radiologia", ["imagen.radiografia_torax"]),
            ("Solicito un hemograma", "laboratorio", ["lab.hemograma"]),
        ],
        "no_preguntar": [
            ("¿Le duele la herida?", "No lo describe; la exploración muestra que cicatriza bien."),
            ("Pido una tomografía de abdomen", "El caso no tiene ese estudio: la herida y el abdomen están bien."),
        ],
        "nota": "Fiebre, taquicardia y crepitantes en la base derecha al quinto día de la cirugía.",
    },
    "GOB-003": {
        "preguntar": [
            ("¿Cómo fue el parto?", "paciente", ["antecedente.evolucion_parto"]),
            ("Voy a tomar los signos vitales", "medico_asistente", ["vital.signos_vitales"]),
            ("Voy a realizar la exploración física", "medico_asistente", ["examen.exploracion_fisica"]),
            ("¿Tiene algún otro síntoma?", "paciente", ["sintoma.estado_de_animo"]),
            ("¿Cómo eran sus reglas antes del embarazo?", "paciente", ["antecedente.evolucion_parto", "antecedente.antecedentes_menstruales"]),
            ("Solicito una prolactina sérica", "laboratorio", ["lab.prolactina"]),
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
            ("Solicito un hemograma y perfil hepático", "laboratorio", ["lab.hemograma_bioquimica"]),
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


# Por qué se hace cada pedido y para qué sirve (documento «Guiones de prueba por paciente»). No nombra el
# diagnóstico del caso: explica qué orienta cada dato.
POR_QUE_DOLOR_TORACICO = {
    "¿Cómo es el dolor? Descríbalo, por favor": "El tipo de dolor es lo que más separa las causas graves de dolor torácico: opresivo e irradiado al brazo o la mandíbula orienta al corazón; punzante y que empeora al respirar, al pulmón o al pericardio; desgarrante y hacia la espalda, a la aorta.",
    "Pregúntele cuándo empezó y cómo ha evolucionado": "El modo de inicio orienta la causa: con el esfuerzo y con molestias previas sugiere origen coronario; de golpe y con falta de aire, una embolia; brusco y máximo desde el primer momento, la aorta.",
    "¿Tiene algún otro síntoma?": "Los síntomas que acompañan al dolor ayudan a separar: sudor frío y náuseas acompañan a la isquemia; falta de aire y tos con sangre, a la embolia pulmonar; sentir que se desmaya, a un problema de la aorta.",
    "Pregúntele por sus antecedentes de enfermedades": "Busca factores de riesgo: diabetes, hipertensión y colesterol para enfermedad coronaria; un cáncer para trombosis; hipertensión mal controlada para problemas de la aorta.",
    "¿Toma algún medicamento?": "Muestra qué enfermedades trata y si cumple el tratamiento. Abandonar los antihipertensivos deja la presión alta sin control.",
    "¿Tiene alergias?": "Es obligatoria antes de indicar cualquier medicamento: en el dolor torácico se usan antiagregantes, anticoagulantes y otros fármacos.",
    "¿Fuma? ¿Ha hecho algún viaje reciente?": "El tabaco es factor de riesgo coronario. Un viaje largo sin moverse favorece los coágulos en las piernas, que pueden llegar al pulmón.",
    "¿Alguien en su familia ha tenido problemas del corazón?": "Un familiar con infarto a edad temprana aumenta el riesgo de enfermedad coronaria.",
    "Voy a realizar la exploración física completa": "Busca los signos que separan las causas: presión distinta entre los brazos y soplo (aorta), pierna hinchada y dolorosa (coágulo que pudo llegar al pulmón), roce al auscultar (pericardio).",
    "Pido un electrocardiograma de 12 derivaciones": "Es el primer examen ante un dolor torácico, en los primeros 10 minutos: muestra si hay un infarto que necesita tratamiento inmediato y otros patrones (pericarditis, sobrecarga del corazón derecho).",
    "Solicito troponina": "Mide el daño del músculo del corazón. Sube mucho en el infarto, pero también algo en otras causas, como la embolia pulmonar.",
    "Solicito dímero D": "Si es normal, hace muy poco probable una embolia pulmonar. Si está alto no aclara nada: también sube en otras causas, como la enfermedad de la aorta.",
    "Pido una radiografía de tórax": "Busca un mediastino ensanchado (aorta) y descarta otras causas de dolor, como un neumotórax o una neumonía.",
    "Solicito una angiotomografía de tórax": "Con un solo estudio confirma o descarta un coágulo en las arterias del pulmón y un problema de la aorta.",
}

POR_QUE = {
    "EME-101": POR_QUE_DOLOR_TORACICO,
    "EME-102": POR_QUE_DOLOR_TORACICO,
    "EME-103": POR_QUE_DOLOR_TORACICO,
    "EME-001": {
        "Pregúntele por sus antecedentes de enfermedades": "Sus enfermedades (epilepsia, esquizofrenia, tiroides) pueden causar por sí mismas fiebre alta y confusión, o tratarse con fármacos que las provocan.",
        "¿Qué medicamentos toma?": "Algunos fármacos, como los antipsicóticos, pueden causar fiebre muy alta con rigidez; otros cambian el pulso o la temperatura.",
        "Voy a examinar al paciente": "El tono muscular separa las causas de fiebre muy alta con confusión: rigidez en unas, músculos flojos en otras. El sudor y la suciedad orientan al esfuerzo físico al calor.",
        "Solicito función tiroidea": "Toma propranolol por hipertiroidismo: hay que saber si la tiroides está descontrolada antes de culpar al calor.",
        "Pido un electroencefalograma": "Tiene epilepsia y está confuso: el electroencefalograma muestra si sigue teniendo crisis sin convulsionar.",
    },
    "EME-002": {
        "¿Tiene alguna enfermedad?": "La hipertensión es un factor de riesgo de sangrado dentro de la cabeza.",
        "Voy a realizar la exploración física": "El nivel de conciencia y la rigidez de nuca orientan: tras una cefalea súbita, la rigidez sugiere sangre o infección alrededor del cerebro.",
        "Solicito una tomografía de cráneo sin contraste": "Muestra dónde está la sangre: alrededor del cerebro o dentro de él.",
    },
    "CIR-005": {
        "¿Alguien en su familia tiene problemas de sangrado?": "Un trastorno de sangrado en la familia orienta a una enfermedad hereditaria de la coagulación.",
        "Solicito pruebas de coagulación": "Comparar antes y después de la cirugía: si las plaquetas y el tiempo de protrombina son normales y solo se alarga el tiempo de tromboplastina parcial, el defecto está en una parte concreta de la coagulación.",
        "Pido el dosaje del factor VIII y del factor IX": "Las dos hemofilias alargan el mismo tiempo de coagulación; solo medir los factores dice cuál falta.",
    },
    "CIR-006": {
        "¿Qué enfermedades tiene?": "La diabetes, la hipertensión y la angina aumentan el riesgo de complicaciones después de una cirugía.",
        "¿Fuma?": "El tabaco aumenta el riesgo de complicaciones pulmonares tras operarse.",
        "Voy a examinar a la paciente y auscultar los pulmones": "Busca de dónde viene la fiebre: pulmones (crepitantes), herida quirúrgica y abdomen.",
        "Pido una radiografía de tórax": "Confirma si los crepitantes son una neumonía (el foco de la infección) o un pulmón colapsado.",
        "Solicito un hemograma": "Los glóbulos blancos altos apoyan una infección.",
    },
    "GOB-003": {
        "¿Cómo fue el parto?": "Saber si hubo un sangrado importante: una hemorragia grande en el parto puede dañar glándulas que necesitan mucho riego.",
        "Voy a tomar los signos vitales": "Muestran si hubo shock por el sangrado: presión baja y pulso rápido.",
        "Voy a realizar la exploración física": "Busca signos de shock y la causa del sangrado, como un útero que no se contrae.",
        "¿Tiene algún otro síntoma?": "Ver el ánimo: la tristeza del posparto no explica que no salga leche.",
        "¿Cómo eran sus reglas antes del embarazo?": "Reglas normales y sin cefalea ni problemas de la vista antes del parto van en contra de un tumor de la hipófisis previo.",
        "Solicito una prolactina sérica": "La prolactina es la hormona de la leche: si está baja tras el parto, la hipófisis está dañada.",
    },
    "GOB-004": {
        "¿Tiene algún otro síntoma?": "El dolor al tener relaciones o al orinar orienta a una infección genital.",
        "Pregúntele por sus antecedentes de enfermedades": "Descarta enfermedades previas que cambien el cuadro.",
        "¿Toma algún medicamento?": "Saber qué toma: los anticonceptivos orales no protegen de las infecciones de transmisión sexual.",
        "¿Cuántas parejas sexuales ha tenido? ¿Usa preservativo?": "Las parejas sexuales y el uso irregular del preservativo aumentan el riesgo de infecciones de transmisión sexual.",
        "Voy a realizar el examen ginecológico": "Ver el aspecto de la vulva, del cuello uterino y del flujo, que es distinto en cada infección.",
        "Mido el pH vaginal": "Separa las causas de flujo: un pH alto (mayor de 4,5) apunta a unas infecciones y uno normal, a otras.",
    },
    "MED-008": {
        "Pregúntele desde cuándo empezó y cómo ha evolucionado": "Cómo cambió la lesión de la espalda: una picadura que crece en forma de anillo es muy orientadora.",
        "¿Ha tomado algún medicamento?": "Saber qué tomó y si eso pudo cambiar los síntomas, como la fiebre.",
        "Pregúntele por sus antecedentes de enfermedades": "Busca enfermedades previas y reacciones a medicamentos.",
        "¿Tiene alergias?": "Es crítica en este caso: el tratamiento habitual de este cuadro puede ser un fármaco al que la paciente es alérgica.",
        "¿Ha hecho alguna actividad al aire libre o algún viaje?": "Una salida al campo o al bosque expone a picaduras de garrapatas y otros insectos.",
        "Voy a examinar a la paciente": "Ver la lesión: su tamaño y su forma orientan el diagnóstico.",
        "Solicito un hemograma y perfil hepático": "Otras infecciones por garrapatas bajan glóbulos blancos y plaquetas y alteran el hígado; si todo es normal, apoyan la enfermedad de la lesión en diana.",
    },
    "MED-009": {
        "Voy a examinar al paciente": "En un control sin molestias, la exploración completa es la única forma de encontrar lesiones que el paciente no nota.",
        "¿Desde cuándo tiene esa lesión?": "El tiempo de evolución y si crece ayudan a separar lesiones benignas de malignas.",
        "¿Ha trabajado al sol? ¿Usa protector solar?": "El sol sin protección y la piel clara son factores de riesgo de cáncer de piel.",
    },
    "PED-007": {
        "¿Dónde le duele?": "Localizar el dolor. En los niños, un problema de la cadera muchas veces se siente en la rodilla.",
        "Pregúntele por sus antecedentes y su desarrollo": "Descarta enfermedades previas y problemas de crecimiento.",
        "Voy a examinar al niño": "Mover la rodilla y la cadera muestra de dónde viene realmente el dolor.",
        "Pido una radiografía de cadera": "Ver la forma de la cabeza del fémur.",
    },
    "PED-010": {
        "Voy a examinar a la niña": "Busca signos de pubertad adelantada y manchas en la piel, que juntos orientan a síndromes concretos.",
        "Solicito función tiroidea": "Ver si otras glándulas también están alteradas.",
        "Pido una radiografía de los huesos": "Buscar lesiones óseas que expliquen una fractura con un golpe pequeño.",
        "Solicito la edad ósea": "Una edad ósea mayor que la real indica un exceso de hormonas desde hace tiempo.",
    },
}
