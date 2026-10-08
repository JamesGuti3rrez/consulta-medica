# Fase 3 · Validación de los casos

## Objetivo

Confirmar que los JSON cumplen el esquema oficial y que la demo usa solo los casos curados.

## Comandos

```powershell
backend\.venv\Scripts\python.exe pruebas\03_validacion\verificar_casos.py
cd backend
.\.venv\Scripts\python.exe -m pytest -v
```

## Qué se comprueba

1. **Esquema**: cada archivo de `curated/`, `validated_second_pass/` y `rejected/` se valida con
   `schemas/caso.schema.json` (JSON Schema 2020-12), usando el mismo validador que el servidor.
2. **Lote curado**: 10 casos con `status = curado`; el nombre de archivo coincide con `case_id`;
   los sufijos van del 001 al 010 sin huecos ni repetidos; hay 2 por especialidad; todos vienen de
   MedQA y registran quién los curó; ningún ID rechazado aparece en `curated/`.
3. **Catálogo de la API**: `server/cases/catalog.py` lee solo `data/cases/curated/`, descarta lo que
   no esté `curado` y expone exactamente esos 10 casos.
4. **Vista del estudiante**: `to_student_case` entrega solo campos públicos (paciente, motivo,
   resumen, alergias). Ni el diagnóstico, ni sus sinónimos, ni los diferenciales, ni el tratamiento
   de referencia aparecen en el JSON que recibe el navegador.

## Resultado

- Esquema: `curated/` 10/10 (`curado`), `validated_second_pass/` 10/10 (`validado`), `rejected/` 10/10 (`rechazado`).
- Todas las comprobaciones pasan; `pytest`: 19 pruebas superadas.

## Evidencias

- [ejecucion/01_verificar_casos.png](ejecucion/01_verificar_casos.png) ([.txt](ejecucion/01_verificar_casos.txt))
- [ejecucion/02_pytest_backend.png](ejecucion/02_pytest_backend.png) ([.txt](ejecucion/02_pytest_backend.txt))
