"""Por qué cada dato descarta cada diagnóstico diferencial, caso por caso (guía de preguntas por paciente).

La relación dato → diferencial está en los casos (protected.differentials[].discard_evidence_ids); aquí va la
explicación clínica en palabras sencillas que lee quien prueba el simulador. Cada clave es el nombre exacto
del diferencial en el caso.
"""

DESCARTES: dict[str, dict[str, str]] = {
    "EME-001": {
        "Síndrome neuroléptico maligno": "Tiene el tono muscular mínimo; el síndrome neuroléptico maligno cursa con rigidez muscular intensa.",
        "Tormenta tiroidea": "Aunque toma propranolol por hipertiroidismo, la TSH y la tiroxina libre están normales: la tiroides no está descontrolada.",
        "Estado epiléptico": "Tiene epilepsia y está obnubilado, pero el electroencefalograma no muestra actividad epileptiforme: no está convulsionando sin que se vea.",
        "Hipertermia maligna perioperatoria": "La hipertermia maligna aparece durante o justo después de una anestesia; la suya fue hace varios meses.",
    },
    "EME-002": {
        "Meningitis o meningoencefalitis": "La cefalea empezó de golpe, en segundos, y casi no tiene fiebre (37,9 °C); la meningitis se instala en horas y con fiebre alta.",
        "Hemorragia intracerebral": "La tomografía muestra la sangre en el espacio subaracnoideo, sin un hematoma dentro del cerebro.",
        "Trombosis venosa cerebral": "La trombosis venosa produce una cefalea que empeora en días; la suya fue súbita, la peor de su vida, en segundos.",
        "Crisis epiléptica": "No hubo convulsiones, y la cefalea súbita con rigidez de nuca no se explica por una crisis.",
    },
    "GOB-003": {
        "Retención de restos placentarios": "Los restos placentarios frenan la lactancia sin dañar la hipófisis, con la prolactina normal; aquí la prolactina está baja.",
        "Tristeza puerperal": "Conserva el ánimo, quiere amamantar y niega tristeza o llanto; además, la tristeza puerperal no impide que salga la leche.",
        "Tumor hipofisario": "Antes del embarazo tenía reglas normales, sin cefalea ni problemas de la vista, y la prolactina está baja (un tumor que la produce la elevaría).",
        "Hipofisitis posparto": "La hipofisitis aparece semanas o meses después del parto; aquí la falla es inmediata, justo tras una hemorragia con shock (presión 80/60) que necesitó transfusión.",
    },
    "GOB-004": {
        "Enfermedad pélvica inflamatoria": "Los signos vitales son normales, sin fiebre, y la molestia pélvica es leve; la enfermedad pélvica inflamatoria suele dar fiebre y dolor importante.",
        "Cervicitis por gonorrea o clamidia": "El cuello uterino «en fresa» y el flujo verde-amarillento espumoso son propios de la tricomoniasis, no de la cervicitis por gonorrea o clamidia.",
        "Vaginosis bacteriana": "La vaginosis da flujo grisáceo sin inflamación; aquí hay eritema vulvovaginal y cuello en fresa.",
        "Candidiasis vulvovaginal": "La candidiasis da flujo blanco grumoso con pH normal (menor de 4,5); aquí el flujo es espumoso y amarillento y el pH es 5,8.",
    },
    "CIR-005": {
        "Hemofilia B": "Las dos hemofilias alargan el mismo tiempo de coagulación; el dosaje muestra el factor VIII bajo y el factor IX normal.",
        "Enfermedad de von Willebrand": "La enfermedad de von Willebrand alarga el tiempo de sangrado; aquí el tiempo de sangrado y las plaquetas son normales.",
        "Inhibidor adquirido de factor VIII": "Hay antecedentes familiares de un trastorno hemorrágico: apunta a una enfermedad hereditaria, no a un inhibidor que aparece en la vida adulta.",
        "Coagulopatía perioperatoria adquirida": "Solo está alargado el tiempo de tromboplastina parcial, con protrombina y plaquetas normales, y hay antecedentes familiares; una coagulopatía por la cirugía altera varias pruebas a la vez.",
    },
    "CIR-006": {
        "Síndrome de respuesta inflamatoria sistémica no infeccioso": "Hay un foco infeccioso claro: la radiografía muestra una neumonía en la base derecha y el hemograma tiene leucocitosis con neutrofilia.",
        "Embolia pulmonar posoperatoria": "Tiene fiebre de 38,5 °C y crepitantes localizados en la base derecha, propios de una infección pulmonar; la embolia no da crepitantes ni suele dar esa fiebre.",
        "Atelectasia u otra causa de hipoxemia": "La radiografía muestra una consolidación con broncograma aéreo, sin colapso del pulmón: es una neumonía, no una atelectasia.",
        "Delirio posoperatorio por causa metabólica o farmacológica": "La confusión llega con fiebre, taquicardia y respiración rápida por una infección pulmonar; no hace falta otra causa metabólica o farmacológica.",
    },
    "MED-007": {
        "Celulitis bacteriana": "La lesión es una mancha en diana que crece en anillo, sin la piel caliente, hinchada y mal delimitada de la celulitis.",
        "Reacción local a picadura": "Una reacción a picadura es pequeña y sin fiebre; aquí la mancha mide 17 × 19 cm y tiene fiebre de 40,1 °C.",
        "Otras infecciones transmitidas por garrapatas": "Otras infecciones por garrapatas (ehrlichiosis, anaplasmosis) bajan leucocitos y plaquetas y elevan las transaminasas; aquí todo es normal, y la mancha en diana es típica de la enfermedad de Lyme.",
    },
    "MED-008": {
        "Carcinoma escamocelular": "La lesión es perlada, con bordes enrollados y telangiectasias, típica del carcinoma basocelular; el escamocelular suele ser costroso o ulcerado.",
        "Carcinoma sebáceo palpebral": "El carcinoma sebáceo suele ser amarillento, como un chalazión que vuelve; esta lesión es perlada con telangiectasias.",
        "Queratoacantoma": "El queratoacantoma crece muy rápido, en semanas; esta lesión crece lento, en 6 meses.",
        "Chalazión persistente": "El chalazión es un nódulo liso, sin aspecto perlado ni telangiectasias.",
    },
    "PED-009": {
        "Artritis séptica": "El niño está afebril y con signos vitales estables; la artritis séptica da fiebre y aspecto de enfermo.",
        "Epifisiólisis de la cabeza femoral": "La radiografía muestra la cabeza del fémur aplanada (necrosis), no desplazada; la epifisiólisis además es más propia de adolescentes.",
        "Osteomielitis": "Sin fiebre ni signos de infección, y la radiografía muestra la cabeza del fémur aplanada, no una infección del hueso.",
        "Artritis idiopática juvenil": "La radiografía muestra la cabeza del fémur aplanada; la artritis idiopática afecta la articulación sin aplanar la cabeza femoral.",
    },
    "PED-010": {
        "Neurofibromatosis tipo 1": "La neurofibromatosis no produce displasia fibrosa del hueso ni desarrollo mamario precoz.",
        "Síndrome de Peutz-Jeghers": "En el Peutz-Jeghers las manchas son pequeñas y oscuras, en labios y boca; aquí son manchas café con leche en la piel.",
        "Displasia fibrosa ósea no sindrómica": "Además del hueso, tiene desarrollo mamario precoz y manchas café con leche: es un síndrome, no solo una displasia del hueso.",
        "Otras causas de pubertad precoz periférica": "La pubertad precoz llega con displasia fibrosa del hueso y manchas café con leche: la tríada del síndrome de McCune-Albright.",
    },
    "EME-101": {
        "Tromboembolia pulmonar aguda": "No hay viaje ni piernas hinchadas, el dímero D es normal y la angiotomografía no muestra coágulos en las arterias del pulmón.",
        "Disección aórtica aguda tipo A": "El dolor es opresivo, no desgarrante; la presión es igual en ambos brazos, el mediastino es normal y la aorta está sana en la angiotomografía.",
        "Pericarditis aguda": "El dolor no cambia con la postura ni la respiración, no hay roce, y el ECG muestra elevación del ST localizada con cambios recíprocos (en la pericarditis es difusa).",
    },
    "EME-102": {
        "Infarto agudo de miocardio con elevación del ST": "El dolor es punzante y empeora al respirar, no opresivo; el ECG no tiene elevación del ST y muestra un patrón de sobrecarga del corazón derecho.",
        "Disección aórtica aguda tipo A": "El dolor es punzante y respiratorio, no desgarrante; la presión es simétrica y la angiotomografía muestra coágulos pulmonares con la aorta normal.",
        "Pericarditis aguda": "El dolor no cambia al inclinarse hacia adelante, no hay roce, y el ECG muestra sobrecarga derecha, sin elevación difusa del ST.",
    },
    "EME-103": {
        "Infarto agudo de miocardio con elevación del ST": "El ECG no muestra elevación ni descenso del ST y la troponina es normal.",
        "Tromboembolia pulmonar aguda": "La presión es distinta entre los brazos, con un soplo de insuficiencia aórtica, y la angiotomografía muestra el colgajo en la aorta, con las arterias pulmonares normales.",
        "Pericarditis aguda": "El dolor es desgarrante y se va a la espalda, no cambia con la postura, y el ECG no muestra elevación difusa del ST.",
    },
}
