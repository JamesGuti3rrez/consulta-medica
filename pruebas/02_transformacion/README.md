# Fase 2 · Conversión a JSON

## Objetivo

Volver a ejecutar la conversión de MedQA a casos JSON y comprobar que genera los 10 casos esperados,
con IDs ordenados del 001 al 010, y que el resultado coincide con lo versionado.

## Comandos

```powershell
cd backend
.\.venv\Scripts\python.exe -m case_preparation adapters extract --dataset medqa
.\.venv\Scripts\python.exe -m case_preparation curation
cd ..
git diff --ignore-cr-at-eol --exit-code --stat -- data/cases
```

1. **Extraer** recorre los 30 `.jsonl` de `data_clean.zip`: 225 908 registros leídos y 53 151
   candidatos con contexto de paciente, que quedan en `data/interim/medqa_candidatos.jsonl`.
2. **Curar** toma de esos candidatos las 10 preguntas seleccionadas, las convierte al formato de
   `schemas/caso.schema.json`, las valida y escribe `data/cases/validated_second_pass/` y
   `data/cases/curated/`. La adaptación al español y la revisión clínica están registradas en
   `data/cases/reviews/` (curación asistida por IA). El enunciado, las opciones y la respuesta
   originales se conservan en la sección protegida del caso.
3. **Comprobar** que `git diff` no muestra diferencias (código de salida 0): la regeneración es
   determinista y reproduce exactamente los JSON versionados.

## Resultado

| Posición | ID | Especialidad |
| --- | --- | --- |
| 001–002 | EME-001, EME-002 | Emergencias |
| 003–004 | GOB-003, GOB-004 | Ginecología y obstetricia |
| 005–006 | CIR-005, CIR-006 | Cirugía general |
| 007 | PED-007 | Pediatría |
| 008–009 | MED-008, MED-009 | Medicina interna |
| 010 | PED-010 | Pediatría |

El sufijo indica la posición en el lote y el prefijo la especialidad; hay 2 casos por especialidad.

## Evidencias

- [ejecucion/02_extract_medqa.png](ejecucion/02_extract_medqa.png) ([.txt](ejecucion/02_extract_medqa.txt)): extracción de candidatos y conteo por especialidad. [Foto de la terminal](ejecucion/02_extract_medqa_terminal.png).
- [ejecucion/03_curation_medqa.png](ejecucion/03_curation_medqa.png) ([.txt](ejecucion/03_curation_medqa.txt)) y [captura de terminal](ejecucion/03_curation_medqa_terminal.png): 10 casos escritos, IDs en orden, `schema_valid: true`.
- [resultados/04_reproducibilidad_casos.png](resultados/04_reproducibilidad_casos.png) ([.txt](resultados/04_reproducibilidad_casos.txt)) y [captura de terminal](resultados/04_reproducibilidad_casos_terminal.png): sin diferencias con lo versionado.
- [resultados/05_seleccion_final_10.png](resultados/05_seleccion_final_10.png): criterios de selección y conteos de la selección final.

## Intentos

| Intento | Resultado | Evidencia |
| --- | --- | --- |
| 1 | Rechazado: selección automática (MED-001 … EME-010) con curación heurística defectuosa y resúmenes de estudios | [intentos/01_primera_seleccion_rechazada/](intentos/01_primera_seleccion_rechazada/README.md) |
| 2 | Correcto: 10 casos revisados, IDs 001–010, regeneración idéntica a lo versionado | esta carpeta |

Los casos del intento 1 se conservan en `data/cases/rejected/` con su motivo y no se usan en la demo.

## Corrección realizada

La curación leía `data/interim/medqa_candidatos_reparados.jsonl`, un archivo que ningún comando
generaba. Se comprobó que es idéntico, byte a byte, a la salida actual de `adapters extract`
(SHA-256 `0ce22650…`), y la curación ahora lee directamente la salida estándar del extractor.

Segunda revisión (frente a las especificaciones):

- `provenance.created_by` decía `medqa_selection`, el módulo de la primera selección; ahora indica `medqa_final_review`, que es el que genera los casos.
- Las fechas del lote dependían del día de ejecución; ahora son fijas (`BATCH_DATE = 2026-10-08`), así que la regeneración es idéntica cualquier día.
- La etiqueta «Adaptación clínica en español (no literal)» contradecía la decisión 0001 §6; ahora dice «Traducción al español».
- La curación aplica el esquema y las reglas cruzadas R01–R10 antes de escribir cada caso.
