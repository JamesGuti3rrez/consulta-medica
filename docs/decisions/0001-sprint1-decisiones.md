# 0001 · Decisiones del sprint 1 para preparación de casos

- **Estado:** propuesta
- **Fecha:** 2026-10-08
- **Responsable:** James Gutiérrez (datos)

## Contexto

El sprint 1 requiere preparar un pipeline de datos para generar 10 casos clínicos a partir de una fuente pública, con validación determinística y trazabilidad. El proyecto exige que la lógica del caso se decida mediante reglas y no por IA, y que `schemas/caso.schema.json` se respete sin alterarlo.

## Alternativas consideradas

1. Usar un único dataset público de preguntas clínicas y seleccionar 10 casos.
2. Añadir Synthea para completar datos sintéticos.
3. Convertir casos de forma manual o con IA supervisada por validación.
4. Traducir texto libremente o de forma literal y clínica.

## Decisión

### 1. Fuente de MedQA

Se usará la fuente oficial del repositorio `jind11/MedQA`.

- URL oficial: `https://github.com/jind11/MedQA`
- Versión: registro del repositorio y del paquete de datos al momento del sprint; la descarga se fija por `sha256` local.
- Licencia: `MIT`, verificada en el archivo `LICENSE` del repositorio oficial.
- Archivos: `data_clean.zip`, enlazado desde el README oficial, con los bancos de preguntas en `.jsonl`.
- Bancos admitidos: **US** (inglés original) y **Taiwan en su versión en inglés** (`tw_translated_jsonl/en/` y `metamap/`, que publica el mismo repositorio). El banco Mainland (chino) no se usa.
- Motivo de admitir Taiwan: amplía las preguntas disponibles en emergencias y pediatría. EME-002 y PED-010 provienen de ese banco. Como es una traducción del chino, cuando el enunciado es ambiguo el caso lo señala en vez de completar el dato (por ejemplo, PED-010 con la función tiroidea).
- Los archivos no se transforman ni se combinan entre sí: cada caso sale de una sola pregunta de un solo banco.

### 2. Uso de Synthea

Se deja para un sprint posterior. En este sprint no se mezclan datos generados por Synthea con preguntas de MedQA ni con ningún otro caso. La regla es estricta: cada caso se construye a partir de una única fuente y una sola pregunta clínica.

### 3. Prefijo de `case_id`

Se usará una convención por especialidad, con prefijos de 3 a 5 letras en mayúsculas:

- `MED` para medicina interna
- `PED` para pediatría
- `GOB` para ginecología y obstetricia
- `CIR` para cirugía general
- `EME` para emergencias

La forma final cumple `^[A-Z]{3,5}-\d{3}$`.

### 4. Selección y clasificación por especialidad

La clasificación será determinística y explicable:

- `pediatria`: edad menor de 18 años.
- `ginecologia_obstetricia`: embarazo, puerperio o patología ginecológica.
- `cirugia_general`: cuadros de manejo quirúrgico o con indicación quirúrgica clara.
- `emergencias`: presentación aguda en urgencias, trauma, dolor torácico con riesgo inmediato, shock o deterioro agudo.
- `medicina_interna`: el resto de cuadros clínicos en adultos que no encajen en las reglas anteriores.

La clasificación se asociará a cada candidato junto con la regla que la motivó.

### 5. Método de conversión

Se usa `ia_validador` (`source.method`), en línea con la arquitectura del proyecto («Conversión de MedQA con IA, validador y revisión, una sola vez»).

- La IA propone la conversión; el validador decide. Ningún caso se acepta sin pasar el esquema `schemas/caso.schema.json` y las reglas cruzadas R01–R10 de `backend/server/cases/rules.py`.
- La conversión se ejecuta una sola vez por caso, antes del uso con estudiantes; el resultado queda versionado y se regenera de forma determinista con `python -m case_preparation curation`.
- El diagnóstico y la respuesta de la fuente quedan siempre en `protected`; la vista del estudiante no los incluye.

### 6. Traducción al español

El caso contiene la misma información que el enunciado original en inglés, traducida al español con terminología clínica, sin inferencia ni dramatización. La traducción no debe:

- introducir diagnóstico ni tratamiento nuevos;
- cambiar la intención del enunciado;
- ocultar o suavizar datos ya presentes;
- mover el diagnóstico fuera de `protected`.

Se conservarán los códigos de sistema, `evidence_id` y las unidades UCUM sin reinterpretación. El enunciado, las opciones y la respuesta originales en inglés se guardan en `protected.evaluation` para poder cotejar la traducción.

## Justificación

Estas decisiones priorizan:

- estricta trazabilidad desde la fuente;
- reproducibilidad y validación automática;
- ausencia de mezcla de fuentes;
- seguridad clínica y cumplimiento del esquema.

## Consecuencias

- El pipeline será determinista y auditable.
- Ningún caso llega a los estudiantes sin pasar el validador (esquema y reglas cruzadas).
- El equipo podrá revisar la selección y la conversión antes de pasar a curación clínica.

## Historial de cambios

- 2026-10-08: §1 admite el banco Taiwan en inglés además del US; §5 pasa de `manual` a `ia_validador`, como indica la arquitectura; §6 precisa que la traducción conserva la misma información que el original en inglés. Se ajusta el documento a lo que se hizo.
