# Fase 3 · Intento 1 (fallido) — 2026-10-08

Revisión de los casos curados frente a las especificaciones escritas: el esquema y la descripción de
sus campos, `docs/decisions/0001` y `data/README.md`.

## Qué se añadió

- `backend/server/cases/rules.py`: reglas cruzadas R01–R10, cada una con la especificación de la que sale. Las aplican la curación (antes de escribir) y el catálogo de la API (al cargar).
- `verificar_casos.py`: secciones 5 (reglas cruzadas) y 6 (banco de origen de cada pregunta).
- `backend/tests/test_case_rules.py`: una prueba por regla; 31 pruebas en total.

## Resultado

| Comprobación | Resultado |
| --- | --- |
| Esquema, lote curado, API y vista pública (secciones 1–4) | OK |
| Reglas R01–R10 en `curated/` y `validated_second_pass/` | OK |
| Reglas en `rejected/` (informativo) | PED-003 y PED-004 incumplen R06: «pediatría» con 45 años, el defecto por el que se rechazaron |
| Banco de origen (0001 §1: «los JSONL del banco de preguntas de US … sin combinar con otros conjuntos») | **FALLA**: EME-002 y PED-010 vienen del banco de **Taiwán** (traducción al inglés) |

Código de salida: 1. Detalle en `01_verificar_casos.txt`.

## Causa

El extractor recorre los 30 `.jsonl` de `data_clean.zip` (US, Mainland y Taiwan), en lugar de solo el
banco US que fija la decisión 0001. Por eso dos preguntas del banco de Taiwán llegaron a la selección final.

## Correcciones hechas en esta revisión

- `provenance.created_by` de los 20 casos decía `medqa_selection`, el módulo de la primera selección (rechazada). Ahora indica `medqa_final_review`, que es el que los genera.
- Las fechas del lote dependían del día de ejecución, así que regenerar otro día cambiaba los JSON. Ahora son fijas (`BATCH_DATE = 2026-10-08`).
