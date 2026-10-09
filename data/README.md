# data/

Datos del sistema, separados por etapa. El lote MedQA tiene 10 casos curados en `cases/curated/`. La
primera selección automática (10 casos) se rechazó y se conserva en `cases/rejected/` para auditoría.

| Carpeta | Contenido | ¿Se versiona? |
| --- | --- | --- |
| `raw/` | Datasets fuente tal como se obtienen, uno por subcarpeta. Los deja aquí `backend/case_preparation/sources/` y nada los modifica después. | No, salvo `raw/<fuente>/source_manifest.json`: URL, huella SHA-256 y fechas de cada archivo |
| `interim/` | Candidatos extraídos (`medqa_candidatos.jsonl`) y su resumen de conteos. | No |
| `cases/validated/` | Casos que pasaron los Quality Gates y esperan curación (`status: validado`). | Sí |
| `cases/curated/` | Casos `curado`: los únicos que ve el estudiante. Quedan congelados. | Sí |
| `cases/rejected/` | Casos rechazados, con su motivo, para auditoría. | Sí |
| `cases/reviews/` | Registros de la curación: datos de entrada del lote (`medqa_lote_curacion.json`), revisión de cada caso, índice con el archivo y la línea de origen de cada pregunta, y avisos de los Quality Gates. | Sí |
| `cases/final_selection/` | Criterios y conteos de la selección final del lote. | Sí |
| `indexes/` | Índice vectorial local generado desde `cases/curated/`. Se puede regenerar. | No |
| `knowledge/` | Fuentes de conocimiento clínico general para el RAG (pendiente de decisión). | Por definir |

Reglas:

- El esquema oficial está en `schemas/`, no aquí.
- El campo `status` del JSON es la fuente de verdad; la carpeta solo refleja la etapa.
- Los datos definitivos se construyen desde cero con el pipeline del proyecto; regenerarlos produce exactamente los mismos JSON.
- El sufijo del ID (001–010) es la posición del caso en el lote, y coincide con el número del alias («Paciente 1» es EME-001); el prefijo identifica la especialidad.
- Solo datos públicos o sintéticos; nunca datos de pacientes reales.
