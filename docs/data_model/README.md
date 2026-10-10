# data_model/

Documentación del modelo de datos.

- Esquema oficial: `schemas/caso.schema.json` (no se duplica aquí).
- Reglas cruzadas que el esquema no expresa: implementadas en `backend/server/cases/rules.py` y aplicadas por los Quality Gates del pipeline, por la curación y por el catálogo de la API (tabla siguiente).

## Reglas cruzadas

El respaldo del esquema (EN-001) menciona reglas «E02 a E13», pero su definición no se conserva en ningún documento. Las reglas R01–R13 se derivaron de las especificaciones escritas que sí existen.

| Regla | Qué exige | Especificación | Efecto |
| --- | --- | --- | --- |
| R01 | El prefijo del ID corresponde a la especialidad | decisión 0001 §3 | Rechaza |
| R02 | `evidence_id` únicos y del propio caso | esquema (`evidence_id`) | Rechaza |
| R03 | La evaluación solo cita evidencia que existe | esquema | Rechaza |
| R04 | El diagnóstico y sus sinónimos no aparecen en el título ni en datos visibles | esquema (`title`) | Rechaza |
| R05 | Alergias coherentes con `allergies_recorded` | esquema | Rechaza |
| R06 | Menor de 18 años ⇔ pediatría; ginecología ⇒ paciente femenina | decisión 0001 §4 | Rechaza |
| R07 | La procedencia refleja el estado (curado, rechazado) | esquema y `data/README.md` | Rechaza |
| R08 | La licencia es la registrada para la fuente | `sources/registry.py` | Rechaza |
| R09 | Ninguna pregunta fuente se usa en dos casos | decisión 0001 §2 | Rechaza el lote |
| R10 | IDs de caso únicos | `data/README.md` | Rechaza el lote |
| R11 | Los diferenciales (opciones incorrectas) no salen de `protected` | SP-002, riesgo R1 | Rechaza |
| R12 | No queda texto de la pregunta de opción múltiple | SP-002, regla 4 | Rechaza |
| R13 | No hay cifras que no estén en el enunciado original (acepta cifras escritas con letras) | SP-002, regla 3 | Rechaza |
| R14 | Cada dato bajo solicitud usa el modo de su dueño (paciente `al_preguntar`, médico asistente `al_examinar`, laboratorio y radiología `al_solicitar_examen`); paciente y médico asistente solo usan los temas acordados de `requires` | Contrato de indexado del RAG | Rechaza |
| W01 | Laboratorio, imágenes y examen físico no van en `public` | SP-002 regla 2 y arquitectura §6.1 | Aviso: no bloquea hasta redistribuir los casos entre `public` y `on_request` |
- Tablas de Supabase: se documentarán aquí a partir de `backend/supabase/migrations/`.
- Observaciones del análisis: `observaciones_caso_schema.md`.
