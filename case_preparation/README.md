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

## Indexación offline (LightRAG)

La etapa `index` construye un índice local desde casos curados y, únicamente si existe,
`data/knowledge/registry.json` permite fuentes Markdown previamente aprobadas. No descarga contenido:
las fuentes se registran en `data/knowledge/approved/` después de una decisión clínica/de licencia.
Cada registro aprobado declara `id`, `path` (Markdown directo dentro de `approved/`), `license`,
`reviewed_by`, `scope` (`conversation` o `evaluation`) y `approved: true`.

Instale la dependencia opcional y ejecute desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[indexing]"
.\.venv\Scripts\python.exe -m case_preparation index
```

Los documentos de caso se particionan por caso, ámbito (`public`, `paciente`,
`medico_asistente`, `laboratorio`, `radiologia`) y conjunto `requires`; así el índice no mezcla
casos ni niveles de autorización. Se conservan los `requires` como metadatos.
Solo se serializan datos demográficos públicos, el motivo y datos explícitamente bajo solicitud;
`protected`, la ficha pública ampliada, títulos, procedencia y respuestas no son campos de entrada
del índice. El indexador rechaza `requires` fuera del contrato compartido y falla si detecta en el
texto autorizado una frase presente en diagnóstico, diferenciales, tratamiento o evaluación
protegidos. Se exige que los casos estén redistribuidos conforme al contrato: el lote actual no es
apto hasta que esa revisión esté completa.

La instalación queda fijada en `lightrag-hku==1.5.7`. El índice usa embedding léxico local
determinista y desactiva llamadas de extracción de entidades (callback que solo devuelve el marcador
de finalización vacío); no configura claves, proveedores externos ni LLM. Cada huella de contenido
se escribe en su propio subdirectorio de `data/indexes/lightrag/`, junto con un manifiesto; es
regenerable y está ignorado por Git.
La validación de documentos no requiere instalar LightRAG y nunca consulta una API.

La comprobación completa, con evidencias, está en `pruebas/` (`pruebas/_herramientas/recorrido_completo.py`).
