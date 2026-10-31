# 28. Proponer y registrar diagnóstico final (HU-006)

> La historia «Completar reporte final», que se entregó como HU-006 (`26_reporte_final/`), ahora es **HU-007**.
> Esta carpeta es la HU-006 nueva.

## Objetivo

HU-006 pide: **campo obligatorio de diagnóstico; validación de texto; confirmación de cierre; almacenamiento por
estudiante/case_id/sesión/intento; no exposición de protected; evitar doble envío; pruebas de fallo y acceso ajeno.**

Antes, el servidor aceptaba cerrar sin diagnóstico, «Guardar y finalizar» cerraba sin confirmar, no había número de
intento y, si el cierre fallaba, el simulador igual daba la consulta por cerrada. Ahora el diagnóstico es obligatorio
y se valida en el navegador y en el servidor; el alumno confirma el cierre viendo lo que escribió; el servidor lo
registra en `diagnosticos_finales` (alumno, caso, sesión y número de intento) antes de cerrar; si el registro falla,
la consulta sigue abierta; un segundo envío nunca cambia lo registrado. Los invitados cierran con las mismas reglas,
pero no se registran (decisión del usuario).

Diseño con todas las decisiones: `docs/superpowers/specs/2026-10-31-hu006-diagnostico-final-design.md`.

## Qué se hizo

| Pieza | Archivo |
| --- | --- |
| Validación y normalización del texto | `backend/server/domain/final_diagnosis.py` |
| Registro en memoria y en Supabase | `backend/server/persistence/diagnoses.py` |
| Tabla `diagnosticos_finales` (única por sesión y por alumno/caso/intento, RLS sin políticas) | `backend/supabase/migrations/0007_diagnosticos_finales.sql` |
| Cierre: valida, exige `confirmado: true`, registra y después cierra; 503 sin cerrar si el registro falla | `backend/server/api/ai.py` (`finish`) |
| Simulador: validación en pantalla, paso de confirmación, un solo envío, sin cierre ante 422/503/red | `frontend/public/simulacion.html`, `frontend/public/js/simulacion.js` |

Pruebas nuevas (80): `tests/unit/test_final_diagnosis.py` (34), `tests/unit/test_diagnoses_store.py` (21),
`tests/security/test_hu006_final_diagnosis.py` (25). Las suites de TA-011, HU-007 y la API ahora cierran con
diagnóstico y confirmación (contrato nuevo, mismas comprobaciones).

## Resultados

| Prueba | Antes | Después | Evidencia |
| --- | --- | --- | --- |
| Validación del texto (unitarias) | No existe el módulo | 34 de 34 | `ejecucion/tdd/t1_*` |
| Registro en memoria y Supabase (unitarias) | No existe el módulo | 21 de 21 | `ejecucion/tdd/t2_*` |
| Suite HU006 en local (25 casos) | 20 fallan, 5 pasan | 25 de 25 | `ejecucion/local_*`, `resultados/local_*/logs` |
| Navegador real, invitado y alumno (E2E) | Se detiene: no hay confirmación (2 de 5) | 33 de 33 | `ejecucion/navegador_*`, `resultados/navegador_*` |
| Regresión de HU-007 en el navegador | - | 21 de 21 | `ejecucion/regresion_hu007_navegador.txt` |
| Regresión completa del backend | 582 pasan | 662 pasan (582 + 80) | `ejecucion/tdd/suite_*` |
| Suite HU006 en vivo con Supabase | Pendiente: migración 0007 | - | - |

Los 5 casos que ya pasaban antes son de acceso ajeno (otro alumno, otro invitado, sin credencial, consulta
inexistente) y la consulta abierta sin datos protegidos: los cubría TA-011.

## Casos de la suite HU006

| Id | Criterio | Qué comprueba |
| --- | --- | --- |
| 01-02 | CA1 | Sin diagnóstico, `null`, sin cuerpo, vacío o solo espacios: 422, la consulta sigue abierta, nada registrado |
| 03-04 | CA2 | Menos de 3 letras, más de 2000 caracteres, caracteres de control, `<` `>` y tipos incorrectos: 422 con su motivo |
| 05 | CA2, CA4 | El texto se registra normalizado |
| 06-07 | CA3 | Sin `confirmado` o con `false`: 422; tras el rechazo la consulta sigue respondiendo y se cierra después |
| 08-09 | CA4 | Fila con alumno, case_id, sesión, intento, texto e hipótesis; intentos consecutivos por alumno y caso |
| 10-11 | CA1-CA4 | El invitado cierra sin registro y también debe escribir y confirmar |
| 12-14 | CA6 | Segundo envío, 8 envíos simultáneos y envío inválido tras el cierre: una sola fila, sin cambios |
| 15-17 | CA7 | Supabase falla (500, 503, sin red): 503 y la consulta sigue abierta; falla el cierre tras registrar: el reintento no duplica; consulta inexistente |
| 18-22 | CA7 | Otro alumno, sin credencial, otro invitado, cruces alumno-invitado y dueño falso en el cuerpo |
| 23-25 | CA5 | La fila no contiene protected; la consulta abierta no expone evaluación ni registro; la respuesta del registro solo trae guardado, id e intento |

## Comandos

Desde la raíz del repositorio:

```powershell
# Una prueba con entorno fijo, salida y foto real (ejecucion\tdd\<nombre>.txt y _terminal.png)
.\pruebas\28_diagnostico_final\correr_prueba.ps1 -Nombre t1_green -Pytest "tests/unit/test_final_diagnosis.py -v"

# Suite HU006 en local (evidencia en resultados\<fase>)
.\pruebas\28_diagnostico_final\correr_suite.ps1 -Fase local_despues

# Navegador real (E2E): servidor con sesiones en memoria en el puerto 3100
$env:PORT='3100'; $env:SESSION_STORE='memoria'; $env:CASE_STORE='local'; $env:RAG_BACKEND='local'; $env:RAG_SERVICE_URL=''; npm start
$env:BASE_URL='http://localhost:3100'; node pruebas\28_diagnostico_final\probar_navegador.cjs pruebas\28_diagnostico_final\resultados\navegador_despues

# En vivo (requiere la migración 0007 en Supabase): servidor con sesiones en Supabase y la suite contra él
$env:PORT='3100'; $env:SESSION_STORE='supabase'; $env:RAG_SERVICE_URL=''; $env:LANGSMITH_TRACING='false'; npm start > <log>
.\pruebas\28_diagnostico_final\correr_suite.ps1 -Fase vivo_despues -Modo vivo -BaseUrl http://127.0.0.1:3100 -LogServidor <log>
```

## Estructura

- `ejecucion/`: salidas `.txt` (las fotos reales de la terminal, `_terminal.png`, quedan solo en local);
  `ejecucion/tdd/`, las corridas en rojo y en verde de cada tarea y la regresión completa.
- `resultados/<fase>/logs/HU006-XX.json`: petición y respuesta reales de cada caso, tokens enmascarados.
- `resultados/navegador_*/`: registro de la prueba de navegador y sus capturas.
- `intentos/`: intentos fallidos, conservados sin modificar.

## Intentos

| Intento | Qué falló | Corrección |
| --- | --- | --- |
| [01_preparacion_sin_registro](intentos/01_preparacion_sin_registro/README.md) | La suite «antes» falló en la preparación: `get_diagnoses` aún no existía | `raising=False`, como TA-011 con su verificador |
| [02_evaluation_null_como_fuga](intentos/02_evaluation_null_como_fuga/README.md) | La prueba tomaba `"evaluation": null` de la consulta abierta como fuga | Falla solo si esas claves traen un valor |

## Pendiente

- **Migración 0005 en Supabase** (SQL Editor) y la suite en vivo. Debe ejecutarse antes de publicar: sin la tabla,
  el cierre de un alumno con sesión responde 503 (la consulta sigue abierta y no se pierde nada, pero no se cierra).
