# 0002 · Complementos del equipo en los casos de MedQA

- **Estado:** aceptada
- **Fecha:** 2026-10-14
- **Responsable:** James Gutiérrez (datos)

## Contexto

Las preguntas de MedQA piden el diagnóstico «más probable»: el enunciado trae lo que apoya la respuesta,
pero no siempre lo que excluye las otras opciones. En el simulador eso deja al estudiante con dos o más
diagnósticos posibles aunque pida todos los datos del caso. Al revisar los 13 casos curados, 10 de los 48
diagnósticos diferenciales no tenían ningún dato que los descartara, en 6 casos (CIR-005, CIR-006,
EME-001, EME-002, GOB-003 y MED-007).

Además, en dos casos la lista de diferenciales tenía errores propios, no de falta de datos:

- **GOB-003:** uno de los diferenciales era el propio diagnóstico (síndrome de Sheehan), y otro (atonía
  uterina) explica la hemorragia, no la falta de lactancia por la que pregunta el enunciado.
- **CIR-006:** «neumonía posoperatoria» no compite con la sepsis: es su foco más probable.

La decisión 0001 (§6) establece que el caso contiene la misma información que el enunciado, «sin
completarlo». Esta decisión define una excepción acotada.

## Alternativas consideradas

1. Quitar los diferenciales que el caso no puede distinguir. El estudiante podría seguir planteándolos y el
   simulador no tendría cómo responder.
2. Reemplazar estos casos por casos sintéticos (como la familia EME-101 a EME-103). Se pierde la
   trazabilidad a MedQA de casos ya revisados.
3. Completar cada caso con el dato que decide, marcado como complemento del equipo y con fuente clínica.

## Decisión

Se adopta la alternativa 3, con estas condiciones:

- **Solo lo necesario para descartar:** cada complemento existe para descartar un diferencial concreto; no
  se agregan datos de ambientación.
- **Coherente con la fuente:** ningún complemento contradice el enunciado ni cambia la respuesta de MedQA.
- **Con fuente clínica:** cada complemento cita una fuente registrada en `clinical_sources` del archivo de
  revisión (`data/cases/reviews/medqa_lote_curacion.json`). El generador falla si falta o no existe.
- **Marcado como complemento:** en el reparto del caso, cada dato agregado lleva
  `"complemento": {"fuente": "...", "motivo": "..."}`. El JSON del caso no cambia de formato (el esquema
  no admite campos extra); la marca queda en el archivo de revisión, que es el registro de la curación.
- **Sin cifras nuevas:** los complementos se redactan de forma cualitativa («actividad del factor IX
  normal»), sin valores numéricos inventados. Así la regla R13 (cifras que no están en la fuente) sigue
  protegiendo el resto del caso.
- **Cada diferencial con su descarte:** la regla R15, que ya se aplicaba a los casos sintéticos, pasa a
  aplicarse a todo caso `curado`: si un diferencial no tiene un dato que lo descarte, el caso no se acepta.
- **Diferenciales mal planteados se corrigen**, no se completan: un diferencial que es el propio
  diagnóstico o su causa se quita y, cuando es posible, se reemplaza por una opción del enunciado original.

## Justificación

- El objetivo del simulador es que el estudiante razone hasta un diagnóstico; un caso que no permite
  descartar las alternativas no cumple ese objetivo.
- La trazabilidad se conserva: lo que viene de MedQA y lo que agregó el equipo quedan separados y con
  fuente.
- La regla R15 evita que el problema vuelva con casos nuevos.

## Consecuencias

- Los 6 casos afectados reciben exámenes o datos nuevos a petición, y sus preguntas clave incluyen el
  examen decisivo; el puntaje máximo exige pedirlo.
- No hay revisión médica de los complementos (decisión del equipo). Su respaldo es la fuente clínica de
  cada uno: las 5 fuentes nuevas (MedlinePlus y CDC) se verificaron en línea al citarlas; las demás ya
  estaban registradas desde la curación del lote. Son hallazgos cualitativos habituales para el diagnóstico de la
  fuente, no valores de un paciente real.
- La decisión 0001 §6 sigue vigente para la traducción: el enunciado se traduce sin completar; los
  complementos van como datos aparte.

## Historial de cambios

- 2026-10-14: pasa a «aceptada». El equipo decide que no habrá revisión médica de los complementos; el
  respaldo es la fuente clínica de cada uno.
