# Fase 13 · Guiones por paciente: los 13 casos funcionando (2026-10-12)

[guiones.py](guiones.py) tiene, para cada uno de los 13 pacientes, qué preguntar en orden (con el agente
que debe responder y los datos que debe revelar) y qué no preguntar (cosas que el caso no tiene o que el
estudiante no debe hacer). Es la fuente única de la batería y del documento «Guiones por paciente»
(Entregables/05_Guia_de_pruebas).

[bateria_guiones.py](bateria_guiones.py) recorre los 13 guiones con el modelo real (Groq,
`openai/gpt-oss-20b`) y la configuración del sitio publicado. Comprueba en cada pedido: el agente, los
datos revelados (y que no se revele nada en lo que no se debe preguntar), que se cuenten las cifras del
dato, que no se nombre el diagnóstico ni los diferenciales, que no se inventen síntomas y que no se usen
términos internos.

**Resultado: 114 de 114 pedidos correctos** ([bateria_guiones_terminal.png](bateria_guiones_terminal.png),
7 páginas unidas; detalle en [resultados_guiones.json](resultados_guiones.json)).

## Cambios para que los 13 casos funcionen

| Cambio | Commit |
| --- | --- |
| Respuestas naturales cuando no hay dato: «Ese examen no se realizó en este paciente»; el médico asistente anota hipótesis, diagnósticos y tratamientos sin confirmarlos | `d0eb498` |
| «Le indico…», «le doy…», «administro…» se reconocen como propuesta de tratamiento; «¿Está en tratamiento?» o «¿Qué le recetaron?» van al paciente; «dígame el diagnóstico» va al médico asistente | `0e3ca5b` |
| «Voy a tomar los signos vitales» se reconoce como exploración (GOB-003) | `f633b5c` |
| Si la respuesta omite cifras del dato, el agente pide una corrección una vez | `ae0891c` |
| Antecedentes reconocidos con «enfermedad» en singular (EME-002) | `415d229` |

## Intentos

1. [intentos/01_primera_corrida](intentos/01_primera_corrida/README.md): 102 de 114. Ocho «fallos» eran
   de la batería (contaba como nuevo lo ya revelado); los otros cuatro llevaron a las correcciones de la
   tabla.

## Limitaciones que se mantienen

- El simulador no evalúa al estudiante: anota hipótesis, diagnósticos y tratamientos, pero no dice si
  son correctos ni advierte de un tratamiento contraindicado (motor de evaluación pendiente).
- En EME-001 y EME-002 el paciente llega con la conciencia alterada y aun así responde.
- Los casos de MedQA no traen algunos estudios que serían lo indicado (por ejemplo, la tomografía de
  cráneo en EME-002); el simulador responde que no se realizaron.
