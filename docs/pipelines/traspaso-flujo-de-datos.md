# Traspaso: flujo de datos de casos → siguiente etapa

**Responsable de esta etapa:** James Gutiérrez · **Fecha:** 2026-10-08 · **Actualizada:** 2026-10-09 (reparto de los casos)

Esta nota resume qué entrega la etapa de datos y qué debe saber quien implemente el diálogo clínico o
la base de datos. Aquí no se implementa nada de esas etapas.

## Qué queda listo

- **Fuente identificada y reproducible:** MedQA (MIT), dos archivos con URL y SHA-256 en
  `backend/case_preparation/sources/registry.py`. `sources fetch` los descarga y verifica.
- **10 casos curados** en `data/cases/curated/` (EME-001 … PED-010, 2 por especialidad), regenerables
  con `adapters extract` + `curation` de forma determinista.
- **Validación:** todos los JSON cumplen `schemas/caso.schema.json` y las reglas cruzadas R01–R13
  (`backend/server/cases/rules.py`, tabla en `docs/data_model/README.md`). Las aplican las Quality
  Gates del pipeline, la curación y el catálogo de la API, que rechaza un caso que no las cumpla.
- **Frontend conectado:** `/simulacion.html` carga un caso con `GET /api/caso` y muestra solo la vista
  pública (`to_student_case`), sin `protected`, `on_request`, `source` ni `provenance`.
- **Caso por especialidad:** `GET /api/caso?especialidad=pediatria` devuelve solo casos de esa
  especialidad (422 si no existe), `GET /api/status` informa cuántos hay por especialidad y el simulador
  pasa a la API el parámetro `?especialidad=` de su URL. Falta un selector en la portada para elegirla.
- **Trazabilidad:** cada caso indica de qué archivo y línea de MedQA salió
  (`data/cases/reviews/second_pass_selection.json`).
- **Evidencias** de cada fase en `pruebas/`; todo se repite con
  `backend\.venv\Scripts\python.exe pruebas\_herramientas\recorrido_completo.py`.

## Reparto de los casos para el diálogo clínico

Desde el 2026-10-09 cada caso separa lo que el estudiante ve al inicio de lo que debe obtener
(`pruebas/08_redistribucion_casos/`):

| Dónde | Qué | Quién lo revela (`reveal_policy`) |
| --- | --- | --- |
| `public` | Alias, edad y sexo, motivo de consulta, datos de llegada y signos vitales (arquitectura §6.1) | — (visible desde el inicio) |
| `on_request` | Anamnesis: evolución, síntomas asociados, antecedentes, medicación, alergias, hábitos | `paciente`, `al_preguntar` |
| `on_request` | Exploración física | `medico_asistente`, `al_examinar` |
| `on_request` | Laboratorio e imágenes | `laboratorio` / `radiologia`, `al_solicitar_examen` |

En total hay 34 datos a petición y 38 preguntas clave en los 10 casos. Los temas de `requires` son los
del contrato de indexado del RAG (Julio) y la regla R14 los comprueba. El reparto vive en
`data/cases/reviews/medqa_lote_curacion.json` (`distribution`) y el enunciado original de MedQA se
conserva en `protected` para verificar que no se pierda ni se invente ningún dato.

Para quien implemente el diálogo: en EME-001, EME-002 y CIR-006 el paciente no puede contestar y en
PED-007 y PED-010 es un menor; el rol `paciente` representa al acompañante o a la historia clínica.

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
