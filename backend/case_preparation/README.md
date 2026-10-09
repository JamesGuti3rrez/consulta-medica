# backend/case_preparation/

Pipeline de preparación de casos: **Obtener → Extraer → Transformar → Validar (Quality Gates) → Curar → Cargar → Indexar**.

Está fuera de `server/` porque se ejecuta una sola vez por caso, antes del uso con estudiantes, y no debe desplegarse con el servidor.

| Etapa | Dónde | Entrada → salida |
| --- | --- | --- |
| Obtener | `sources/` | fuente oficial → `data/raw/` (sin modificar) |
| Extraer | `adapters/` | `data/raw/` → registro bruto |
| Transformar | `transform/` | registro bruto → caso candidato (`data/interim/`) |
| Validar | `quality_gates/` | candidato → `data/cases/validated/` o `data/cases/rejected/` |
| Curar | revisión asistida por IA documentada | `validated_second_pass/` → `curated/`, registro en `data/cases/reviews/` |
| Indexar | `indexing/` | `curated/` → `data/indexes/` |

Reglas:

- La validación del esquema y las reglas cruzadas viven en `server/cases/`; aquí se **reutilizan**, no se copian.
- La curación del lote MedQA usa las evaluaciones caso por caso de `transform/medqa_final_review.py`; registra `curacion_asistida_por_ia` en la procedencia y no modifica el contenido clínico.
- La curación automática heurística anterior está deshabilitada; no infiere edad, sexo ni aprobación de revisión a partir del texto.
- La IA (si se usa en un adaptador) solo propone; las reglas fijas aceptan o rechazan.
- Qué NO va aquí: casos, datasets, resultados de corridas (todo eso va en `data/`).

Ejemplos de ejecución:

Flujo que produce los casos de la demo:

```bash
cd backend
.\.venv\Scripts\python.exe -m case_preparation sources fetch --dataset medqa
.\.venv\Scripts\python.exe -m case_preparation adapters extract --dataset medqa
.\.venv\Scripts\python.exe -m case_preparation curation
```

`sources fetch` descarga `MedQA-master.zip` y `data_clean.zip`, verifica su SHA-256 contra `sources/registry.py` y escribe `data/raw/medqa/source_manifest.json`.
`adapters extract` deja los candidatos filtrados en `data/interim/medqa_candidatos.jsonl` y un resumen de conteos por especialidad en `data/interim/medqa_candidatos_summary.json`.
`curation` toma de esos candidatos las 10 preguntas seleccionadas, las valida contra `schemas/caso.schema.json`, las copia a `data/cases/curated/` y registra las decisiones en `data/cases/reviews/medqa_second_pass_curation_summary.json`. Es determinista: volver a ejecutarla reproduce los JSON versionados.

`transform --dataset medqa --count 10` es la primera selección automática; sus casos se rechazaron en la revisión clínica (`data/cases/rejected/`) y no se usan en la demo.

La comprobación completa, con evidencias, está en `pruebas/` (`pruebas/_herramientas/recorrido_completo.py`).
