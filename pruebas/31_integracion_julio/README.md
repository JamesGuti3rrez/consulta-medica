# 31. Integración del PR #3 de Julio (métricas RAGAS del RAG)

El PR #3 (`julio` → `main`, 7 commits del 31 de octubre) añade un benchmark verificable del RAG con métricas de
recuperación y RAGAS (Groq como juez y embeddings locales), sus reportes y pruebas. También incluye dos
refactorizaciones del servidor:

- **Recuperador:** la elección del recuperador sale de `api/ai.py` a `server/rag/factory.py`.
- **Gateway de Groq:** `build_gateway` acepta una configuración.

Además añade un `tests/conftest.py` que aísla las pruebas del `.env` personal. `backend/evals/` y `backend/run_tests.py`
quedan fuera de Vercel, y RAGAS es un extra opcional (`[evals]`), así que no cambia lo que se publica.

## Revisión

| Punto | Resultado |
|---|---|
| Cambios en el servidor | Solo reubican código (selección del recuperador) y permiten pasar una configuración al gateway; el comportamiento es el mismo |
| Despliegue en Vercel | Sin cambios: el `pyproject.toml` de la raíz no cambia y `evals/` está en `.vercelignore` |
| PR tal cual sobre `main` | **3 pruebas fallan**: falta `backend/evals/datasets/clinical_v1.json`, que no se subió. Lo genera su propio script, de forma determinista, desde los casos curados (`python -m evals.build_dataset`). Se generó y se incluye; es idéntico sobre `main` y sobre `James`. |
| `tests/conftest.py` | Vaciaba `SUPABASE_URL` y las claves también en las suites en vivo (TA-011, HU-006, HU-007), que crean alumnos temporales en el Supabase real. Con `TA011_MODO=vivo` ahora conserva las credenciales y el almacenamiento del `.env`, y la telemetría sigue apagada. En local mantiene el aislamiento. |
| Conflicto con `James` | `tests/integration/test_teaching_api.py`: Rodrigo y Julio hicieron el mismo arreglo; queda el de Julio (comentado) y un solo import. |

## Resultados

| Corrida | Archivo | Resultado |
|---|---|---|
| PR #3 tal cual sobre `main` | `ejecucion/00_pr3_tal_cual_sobre_main` | 3 fallan (archivo de datos ausente), 622 pasan |
| Backend completo en `James` con todo unido | `ejecucion/01_regresion_backend_james` | 868 pasan (841 + 27 de Julio); 6 saltadas por no tener RAGAS |
| Escena en el navegador (CIR-006) | `ejecucion/02_regresion_escena` | 18 de 18 |
| Diagnóstico final HU-006 en el navegador | `ejecucion/03_regresion_hu006_diagnostico` | 33 de 33 |
| Pruebas de evaluación con RAGAS 0.4.3 instalado (Python 3.13, entorno aparte) | `ejecucion/04_pruebas_ragas_python313` | 33 de 33 |

RAGAS no se instala con Python 3.14, el del proyecto, porque su dependencia `scikit-network` no tiene versión para
3.14. Con Python 3.13 se instala sin problemas. Para usar el benchmark completo conviene un entorno con Python 3.13.
