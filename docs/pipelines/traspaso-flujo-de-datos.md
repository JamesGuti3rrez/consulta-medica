# Traspaso: flujo de datos de casos → siguiente etapa

**Responsable de esta etapa:** James Gutiérrez · **Fecha:** 2026-10-08

Esta nota resume qué entrega la etapa de datos y qué debe saber quien implemente el diálogo clínico o
la base de datos. Aquí no se implementa nada de esas etapas.

## Qué queda listo

- **Fuente identificada y reproducible:** MedQA (MIT), dos archivos con URL y SHA-256 en
  `backend/case_preparation/sources/registry.py`. `sources fetch` los descarga y verifica.
- **10 casos curados** en `data/cases/curated/` (EME-001 … PED-010, 2 por especialidad), regenerables
  con `adapters extract` + `curation` de forma determinista.
- **Validación:** todos los JSON cumplen `schemas/caso.schema.json`; la API sirve solo los casos curados.
- **Frontend conectado:** `/simulacion.html` carga un caso con `GET /api/caso` y muestra solo la vista
  pública (`to_student_case`), sin `protected`, `on_request`, `source` ni `provenance`.
- **Evidencias** de cada fase en `pruebas/`; todo se repite con
  `backend\.venv\Scripts\python.exe pruebas\_herramientas\recorrido_completo.py`.

## Limitación que afecta al diálogo clínico

En los 10 casos, **toda la historia clínica está en la ficha pública** (`public.chief_complaint` y
`public.items`). En `on_request` hay un solo elemento por caso (`solicitud.exploracion_fisica`), cuyo
texto es un marcador: «los hallazgos … ya están incluidos en la historia pública; no se documentan
otros hallazgos para revelar».

Consecuencia: hoy no hay información que el paciente o el médico asistente puedan revelar al
preguntar o examinar. Un diálogo sobre estos casos solo repetiría la ficha o, si usa un LLM, tendría
que inventar respuestas.

Antes del diálogo habrá que redistribuir cada caso, como nueva versión del lote curado:

| Dónde | Qué | Quién lo revela (`reveal_policy`) |
| --- | --- | --- |
| `public` | Motivo de consulta, edad y sexo | — (visible desde el inicio) |
| `on_request` | Anamnesis (tiempo de evolución, antecedentes, hábitos…) | `paciente`, `al_preguntar` |
| `on_request` | Exploración física | `medico_asistente`, `al_examinar` |
| `on_request` | Laboratorio e imágenes | `laboratorio` / `radiologia`, `al_solicitar_examen` |

El esquema ya admite todo esto; solo cambia el contenido de los casos. El enunciado original de MedQA
se conserva en `protected` y sirve para verificar que no se pierda ni se invente ningún dato.

## Idea de funcionamiento recogida (pendiente de decidir)

Propuesta del equipo, todavía sin registrar como decisión:

1. El estudiante da una orden: «pregúntele al paciente desde cuándo le duele».
2. Un LLM (se mencionó **Grok**, sin confirmar) la reformula y el médico en pantalla la dice: «¿Desde cuándo tiene ese dolor?».
3. El paciente responde.

Puntos a resolver en una decisión `docs/decisions/0002-…` antes de implementar:

- El médico solo debería reformular: no ver el caso ni añadir preguntas que el estudiante no hizo (si no, la evaluación deja de medir al estudiante). La evaluación debería usar la orden original.
- El paciente solo debería responder con los datos que las reglas permiten para esa pregunta, nunca con `protected`, y responder «no sé» ante lo que no esté en el caso.
- Exploración y exámenes pueden entregarse tal cual desde el caso, sin LLM, para no inventar valores.
- Toda respuesta mostrada debería pasar un filtro que busque el diagnóstico, los diferenciales y el tratamiento. `pruebas/03_validacion/verificar_casos.py` y `pruebas/_herramientas/capturar_frontend.cjs` ya hacen esa comprobación sobre la ficha y se pueden reutilizar.
- La decisión 0001 descartó el uso de LLM en el sprint 1; la nueva debe justificar el cambio, el proveedor, el costo por turno y la gestión de la clave.

## Convención de evidencias

Cada etapa se documenta en `pruebas/NN_<fase>/` con `codigo/`, `ejecucion/`, `resultados/`, capturas
en vista de escritorio (1440 px) y una tabla de intentos. Los intentos fallidos se conservan en
`intentos/`; ver `pruebas/README.md`.
