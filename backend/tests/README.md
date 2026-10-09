# backend/tests/

Pruebas automatizadas (pytest) del backend y del pipeline. No llaman a un LLM real.

| Carpeta | Qué prueba |
| --- | --- |
| `unit/` | Funciones y módulos aislados (validación, reglas, máquina de estados, evaluación). |
| `integration/` | Recorrido de un turno y de una sesión a través de varios módulos, con proveedores simulados. |
| `security/` | Pruebas adversariales: fugas del diagnóstico, fuga entre roles, evidencia no autorizada, revelación de datos no autorizados. |
| `fixtures/` | Datos de prueba mínimos creados específicamente para las pruebas. |

Vacías en esta etapa.
