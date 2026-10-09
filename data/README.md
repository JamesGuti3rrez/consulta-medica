# data/

Datos del sistema, separados por etapa. El lote MedQA de segunda pasada ya fue revisado y copiado a `cases/curated/`. Se retiraron seis curaciones heurísticas defectuosas y cuatro resúmenes de estudios que no son casos de pacientes; se conservan en `cases/rejected/` para auditoría.

| Carpeta | Contenido | ¿Se versiona? |
| --- | --- | --- |
| `raw/` | Datasets fuente tal como se obtienen (MedQA, Synthea), uno por subcarpeta. Los deja aquí `backend/case_preparation/sources/`. | No |
| `interim/` | Resultados temporales de la transformación. | No |
| `cases/validated/` | Casos que superaron los Quality Gates. | Sí |
| `cases/validated_second_pass/` | Lote de diez casos con fidelidad a fuente y revisión asistida registradas. | Sí |
| `cases/curated/` | Diez casos con estado `curado` mediante revisión asistida por IA. Mantienen intacto el contenido clínico; solo cambia estado y procedencia de curación. | Sí |
| `cases/rejected/` | Casos rechazados, con su motivo, para auditoría. | Sí |
| `cases/reviews/` | Registros de la revisión clínica de cada caso. | Sí |
| `indexes/` | Índice vectorial local generado desde `cases/curated/`. Se puede regenerar. | No |
| `knowledge/` | Fuentes de conocimiento clínico general para el RAG (pendiente de decisión). | Por definir |

Reglas:

- El esquema oficial está en `schemas/`, no aquí.
- El campo `status` del JSON es la fuente de verdad; la carpeta solo refleja la etapa.
- Los datos definitivos se construyen desde cero con el pipeline del proyecto.
- El resumen y los criterios de curación del lote MedQA están en `cases/reviews/medqa_second_pass_curation_summary.json`; el detalle de coherencia y fuentes está en `cases/reviews/clinical_coherence_review.json`.
- Los sufijos de los IDs de esta selección identifican su posición 001–010 dentro del lote; el prefijo identifica la especialidad. Los IDs completos son únicos.
- Solo datos públicos o sintéticos; nunca datos de pacientes reales.
