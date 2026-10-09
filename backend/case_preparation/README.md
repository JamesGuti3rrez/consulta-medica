# backend/case_preparation/

Pipeline de preparación de casos: **Obtener → Extraer → Transformar → Validar (Quality Gates) → Curar → Indexar**.

Está fuera de `server/` porque se ejecuta una sola vez por caso, antes del uso con estudiantes, y no debe desplegarse con el servidor.

| Etapa | Dónde | Entrada → salida |
| --- | --- | --- |
| Obtener | `sources/` | fuente oficial → `data/raw/`, con huella SHA-256 verificada y manifiesto |
| Extraer | `adapters/` | `data/raw/` (sin modificarlo) → candidatos en `data/interim/` |
| Transformar | `transform/medqa_case_builder.py` | candidato → caso con el formato de `schemas/caso.schema.json` |
| Validar | `quality_gates/` | caso → aceptado (`data/cases/validated/`) o rechazado |
| Curar | `transform/medqa_final_review.py` | `validated/` → `curated/`, con registro en `data/cases/reviews/` |
| Indexar | `indexing/` | `curated/` → `data/indexes/` (pendiente; corresponde al RAG) |

Reglas:

- La validación (esquema y reglas cruzadas R01–R13) vive en `server/cases/`; `quality_gates/` la **reutiliza**, no la copia.
- Los datos de curación del lote (selección, traducción, revisión y ajustes de cada caso) están en `data/cases/reviews/medqa_lote_curacion.json`, no en el código.
- La IA (si se usa en un adaptador) solo propone; las reglas fijas aceptan o rechazan.
- Qué NO va aquí: casos, datasets, resultados de corridas (todo eso va en `data/`).

Flujo que produce los casos de la demo:

```bash
cd backend
.\.venv\Scripts\python.exe -m case_preparation sources fetch --dataset medqa
.\.venv\Scripts\python.exe -m case_preparation adapters extract --dataset medqa
.\.venv\Scripts\python.exe -m case_preparation curation
```

- `sources fetch` descarga `MedQA-27b02f66.zip` (repositorio oficial en el commit `27b02f6`) y `data_clean.zip` (preguntas), rechaza cualquier archivo cuya huella no coincida con `sources/registry.py` y escribe `data/raw/medqa/source_manifest.json`.
- `adapters extract` lee las preguntas dentro de `data_clean.zip` sin descomprimirlo, solo de los bancos admitidos por la decisión 0001 (`US/US_qbank.jsonl` y `Taiwan/tw_translated_jsonl/en/`), aplica el filtro del SP-002 (enunciado de 250 caracteres o más, que pida diagnóstico o tratamiento y no dependa de una imagen), descarta duplicados y guarda cada candidato con su archivo y línea de origen.
- `curation` construye los 10 casos seleccionados, los pasa por los Quality Gates, los escribe en `data/cases/validated/` y `data/cases/curated/`, y registra el índice del lote en `data/cases/reviews/`. Es determinista: volver a ejecutarla reproduce los JSON versionados.

La primera selección automática (comando `transform`) se retiró: sus 10 casos se rechazaron en la revisión y se conservan en `data/cases/rejected/`.

La comprobación completa, con evidencias, está en `pruebas/` (`pruebas/_herramientas/recorrido_completo.py`).
