# 0001 · Decisiones del sprint 1 para preparación de casos

- **Estado:** propuesta
- **Fecha:** 2026-10-08
- **Responsable:** Copilot + equipo clínico

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
- Archivos que se descargarán: los JSONL del banco de preguntas de US (y, si hace falta, el split oficial) publicados por el repositorio, sin transformar ni combinar con otros conjuntos.

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

Se recomienda `manual` para el sprint 1.

- Ventaja: evita dependencia de un proveedor externo de LLM y reduce el riesgo de inventar o filtrar diagnóstico.
- La conversión sigue siendo determinística y se valida con `backend/server/cases/`.
- Si en el futuro el equipo quiere `ia_validador`, se hará con una clave de entorno específica y un máximo de 2 reintentos, pero no en este sprint.

### 6. Traducción al español

Se traducirá de forma literal y clínica, sin inferencia ni dramatización. La traducción no debe:

- introducir diagnóstico ni tratamiento nuevos;
- cambiar la intención del enunciado;
- ocultar o suavizar datos ya presentes;
- mover el diagnóstico fuera de `protected`.

Se conservarán los códigos de sistema, `evidence_id` y las unidades UCUM sin reinterpretación.

## Justificación

Estas decisiones priorizan:

- estricta trazabilidad desde la fuente;
- reproducibilidad y validación automática;
- ausencia de mezcla de fuentes;
- seguridad clínica y cumplimiento del esquema.

## Consecuencias

- El pipeline será determinista y auditable.
- El sprint 1 no depende de APIs externas ni de decisiones subjetivas del modelo.
- El equipo podrá revisar la selección y la conversión antes de pasar a curación clínica.
