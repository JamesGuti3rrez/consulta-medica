# schemas/

Contratos de datos **oficiales** del sistema. Una sola copia por esquema: nadie lo duplica en otra carpeta.

| Archivo | Qué define | Versión |
| --- | --- | --- |
| `caso.schema.json` | Estructura oficial de un caso clínico (public / on_request / protected, evidence_id, reveal_policy, status, provenance). | 1.0.0 (JSON Schema 2020-12) |

Reglas:

- El esquema es la fuente de verdad. El backend (`backend/server/cases/`), el pipeline (`backend/case_preparation/`) y las pruebas lo **leen desde aquí**.
- Las reglas que cruzan campos **no** están en el esquema: están en `backend/server/cases/rules.py` (R01–R13 y el aviso W01; detalle en `docs/data_model/README.md`). La descripción del esquema remite a `validar_caso.py`, que no existe: esa función la cumple `rules.py`.
- Cambios al esquema: SemVer (`schema_version`) y una decisión registrada en `docs/decisions/`.
- Observaciones detectadas en el análisis (sin corregir): `docs/data_model/observaciones_caso_schema.md`.
- Qué NO va aquí: casos, plantillas de casos, ejemplos ni datos de prueba.
