# schemas/

Contratos de datos **oficiales** del sistema. Una sola copia por esquema: nadie lo duplica en otra carpeta.

| Archivo | Qué define | Versión |
| --- | --- | --- |
| `caso.schema.json` | Estructura oficial de un caso clínico (public / on_request / protected, evidence_id, reveal_policy, status, provenance). | 1.0.0 (JSON Schema 2020-12) |

Reglas:

- El esquema es la fuente de verdad. El backend (`backend/server/cases/`), el pipeline (`backend/case_preparation/`) y las pruebas lo **leen desde aquí**.
- Las reglas que cruzan campos (E02–E13 mencionadas en la documentación) **no** están en el esquema: vivirán en `backend/server/cases/` como validación semántica.
- Cambios al esquema: SemVer (`schema_version`) y una decisión registrada en `docs/decisions/`.
- Observaciones detectadas en el análisis (sin corregir): `docs/data_model/observaciones_caso_schema.md`.
- Qué NO va aquí: casos, plantillas de casos, ejemplos ni datos de prueba.
