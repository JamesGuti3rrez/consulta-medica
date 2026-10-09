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

1. **Esquema**: cada archivo de `curated/`, `validated/` y `rejected/` se valida con
   `schemas/caso.schema.json` (JSON Schema 2020-12), usando el mismo validador que el servidor.
2. **Lote curado**: 10 casos con `status = curado`; el nombre de archivo coincide con `case_id`;
   los sufijos van del 001 al 010 sin huecos ni repetidos; hay 2 por especialidad; todos vienen de
   MedQA y registran quién los curó; ningún ID rechazado aparece en `curated/`.
3. **Catálogo de la API**: `server/cases/catalog.py` lee solo `data/cases/curated/`, descarta lo que
   no esté `curado` y expone exactamente esos 10 casos.
4. **Vista del estudiante**: `to_student_case` entrega solo campos públicos (paciente, motivo,
   resumen, alergias). Ni el diagnóstico, ni sus sinónimos, ni los diferenciales, ni el tratamiento
   de referencia aparecen en el JSON que recibe el navegador.
5. **Reglas cruzadas** (`backend/server/cases/rules.py`): lo que el esquema no puede expresar. Las
   aplican también la curación y la API, que rechazan un caso que las incumpla.

   | Regla | Qué exige | Especificación |
   | --- | --- | --- |
   | R01 | El prefijo del ID corresponde a la especialidad | 0001 §3 |
   | R02 | `evidence_id` únicos y del propio caso | esquema |
   | R03 | La evaluación solo cita evidencia que existe | esquema |
   | R04 | El diagnóstico no aparece en el título ni en datos visibles | esquema (`title`) |
   | R05 | Alergias coherentes con `allergies_recorded` | esquema |
   | R06 | Menor de 18 años ⇔ pediatría; ginecología ⇒ paciente femenina | 0001 §4 |
   | R07 | La procedencia refleja el estado (curado, rechazado) | esquema y `data/README.md` |
   | R08 | La licencia es la registrada para la fuente | `registry.py` |
   | R09 | Ninguna pregunta fuente se usa en dos casos | 0001 §2 |
   | R10 | IDs de caso únicos | `data/README.md` |
   | R11 | Los diferenciales no salen de `protected` | SP-002, riesgo R1 |
   | R12 | No queda texto de la pregunta de opción múltiple | SP-002, regla 4 |
   | R13 | No hay cifras que no estén en la fuente | SP-002, regla 3 |
   | W01 | Aviso: laboratorio o examen en `public` | SP-002 regla 2, arquitectura §6.1 |

6. **Banco de origen**: cada pregunta curada se busca en los archivos originales y debe pertenecer a
   un banco admitido por 0001 §1 (US o Taiwan en inglés).

## Resultado

- Esquema: `curated/` 10/10 (`curado`), `validated/` 10/10 (`validado`), `rejected/` 10/10 (`rechazado`).
- Reglas R01–R13: las cumplen los 10 curados; 4 tienen el aviso W01 (laboratorio o examen en `public`), que no bloquea hasta redistribuir los casos. En `rejected/`, PED-003 y PED-004 incumplen R06 («pediatría» con 45 años) y cuatro conservan el texto de la pregunta de opción múltiple (R12): los defectos por los que se rechazaron.
- Banco de origen: 8 casos del banco US y 2 del banco Taiwan en inglés (EME-002 y PED-010).
- Todas las comprobaciones pasan; `pytest`: 45 pruebas superadas.

## Evidencias

- [codigo/01_reglas_cruzadas.png](codigo/01_reglas_cruzadas.png) y [codigo/02_verificar_casos.png](codigo/02_verificar_casos.png): código de las reglas y de la verificación.
- [ejecucion/01_verificar_casos_terminal.png](ejecucion/01_verificar_casos_terminal.png): captura real de la terminal con toda la salida (dos páginas unidas).
- [ejecucion/01_verificar_casos.png](ejecucion/01_verificar_casos.png) ([.txt](ejecucion/01_verificar_casos.txt)): salida completa.
- [ejecucion/02_pytest_backend_terminal.png](ejecucion/02_pytest_backend_terminal.png), [ejecucion/02_pytest_backend.png](ejecucion/02_pytest_backend.png) ([.txt](ejecucion/02_pytest_backend.txt)): pruebas del backend.

## Intentos

| Intento | Resultado | Evidencia |
| --- | --- | --- |
| 1 | Fallido: EME-002 y PED-010 venían del banco Taiwan y la decisión 0001 solo admitía el banco US | [intentos/01_casos_fuera_del_banco_us/](intentos/01_casos_fuera_del_banco_us/README.md) |
| 2 | Correcto: se actualizó la decisión 0001 (§1 admite Taiwan en inglés, §5 `ia_validador`, §6 traducción con la misma información) y todo pasa | esta carpeta |
| 3 | Correcto: reglas R11–R13 y aviso W01 del validador del SP-002, aplicados por las Quality Gates | [../06_correcciones/10_quality_gates_sp002/](../06_correcciones/10_quality_gates_sp002/) |
