# Informe HU-006 - Completar reporte final

| Campo | Valor |
| --- | --- |
| PBI | HU-006 - Completar reporte final (prioridad baja, 1 SP) |
| Responsable | James Bryam Gutiérrez Rubio |
| Rama | `hu-006-reporte-final` (desde `ta-011-autorizacion-sesiones`, de la que depende) |
| Fecha de ejecución | 28 de octubre de 2026 (UTC) |
| Evidencia | `pruebas/26_reporte_final/` (índice: `evidencia.html`) |

Este informe es la evidencia para la validación del Product Owner, no la aprobación del PBI.

## 1. Resumen

Antes de este cambio, la hoja de evaluación solo mostraba conteos («Obtuviste 3 de 5 datos clave»,
«Anamnesis incompleta: 2 datos clave sin obtener»): el alumno no sabía cuáles datos le faltaron ni por qué
importaban, ni cuál era el diagnóstico o el tratamiento del caso, y no existía ningún reporte en el servidor. El
diagnóstico y las hipótesis que escribía solo se guardaban en la tabla `intentos`, que no existe en producción.

Ahora el servidor arma un **reporte final** con datos del caso y de la propia consulta, lo entrega **solo al dueño
y solo después del cierre**, y la hoja de evaluación lo muestra con el diseño de siempre.

| Ejecución | Casos | PASA | FALLA | NO EJECUTADA | Evidencia |
| --- | --- | --- | --- | --- | --- |
| Suite HU006, local, **antes** (código de TA-011) | 17 | 3 | **14** | - | `ejecucion/local_antes_pytest.txt`, `02_local_antes_terminal.png`, `resultados/local_antes/` |
| Suite HU006, local, **después** | 17 | **17** | 0 | - | `ejecucion/local_despues_pytest.txt`, `04_local_despues_terminal.png`, `resultados/local_despues/` |
| Suite HU006, en vivo, **antes** (servidor real + Supabase de producción) | 17 | 3 | **14** | - | `ejecucion/vivo_antes_pytest.txt`, `03_vivo_antes_terminal.png`, `resultados/vivo_antes/` |
| Suite HU006, en vivo, **después** | 17 | **17** | 0 | - | `ejecucion/vivo_despues_pytest.txt`, `05b_vivo_despues_terminal.png`, `resultados/vivo_despues/` |
| Navegador real (E2E), caso EME-101, servidor local con Supabase de producción | 21 comprobaciones | **21** | 0 | - | `capturas/navegador_*.png`, `capturas/navegador_registro.json`, `ejecucion/08_navegador_terminal.png` |
| Reporte de los 43 casos curados | 88 | **88** | 0 | - | `ejecucion/tdd/t6_43_casos.txt` |
| Pruebas unitarias y de API | 16 | **16** | 0 | - | `ejecucion/tdd/t1_green.txt`, `t2_green.txt`, `t4_valor_unidad_green.txt` |
| Preview de Vercel | 0 | - | - | **17** | Bloqueado: `ejecucion/09_preview_vercel.txt`, `intentos/08_...` |
| Regresión completa (`backend/tests`) | antes 461 / después 582 | antes 461 / después 582 | 0 / 0 | 3 deseleccionadas (casos en vivo de TA-011) | `ejecucion/01_regresion_antes*`, `ejecucion/05_regresion_despues*` |

Los 3 casos que pasan «antes» (04, 05 y 07) comprueban que una persona ajena reciba 404: sin la ruta del reporte,
**todos** reciben 404, incluso el dueño. Pasan por la razón equivocada; los casos 01 y 02 (el dueño sí obtiene su
reporte) son los que demuestran que antes no existía.

**El modo local** usa `TestClient` (toda la pila HTTP de FastAPI) con Supabase Auth simulado. **El modo vivo** usa
un servidor real (`npm start` en `127.0.0.1:3100`) con las sesiones y los casos en el Supabase de producción, el
modelo de Groq y dos alumnos temporales que la suite crea y borra (`limpieza.json`: 4 consultas y 2 usuarios
creados y borrados, 0 eventos restantes). **El E2E** usa el simulador real en Chromium, contra el servidor local
conectado al Supabase de producción.

## 2. Matriz de trazabilidad

| Criterio | Qué se exige | Casos | Antes | Después |
| --- | --- | --- | --- | --- |
| **CA1** Solo poscierre | Sin reporte mientras la consulta está abierta | HU006-03, HU006-08, E2E «antes de cerrar: 409» | FALLA (404: no existía) | PASA (409 con el mensaje exacto, sin datos protegidos) |
| **CA2** Propietario validado | Solo el dueño; los demás, 401 o 404 sin datos | HU006-01, 02, 04, 05, 06, 07, 16, 17, E2E «otro navegador» | 01, 02, 06, 16, 17 FALLA; 04, 05, 07 PASA por la razón equivocada | PASA |
| **CA3** Contenido completo | Diagnóstico de referencia, propuesta, tratamiento, puntajes, evidencia revelada | HU006-01, 08 a 14, E2E (9 secciones con contenido) | FALLA | PASA |
| **CA4** Ninguna fuente ajena al `case_id` | Solo ids y nombres del propio caso | HU006-15, `test_report_all_cases.py` (43 casos × 2 escenarios + control negativo), `test_ids_ajenos_se_descartan` | FALLA (sin reporte) | PASA |
| **CA5** E2E | Navegador real, servidor real, Supabase real | `probar_navegador.cjs` (21 comprobaciones) y la suite en vivo | 15 de 20 FALLA (`ejecucion/tdd/navegador_red`) | 21 de 21 PASA |

Detalle por caso (resultado en local y en vivo, que coinciden):

| Caso | Qué comprueba | Antes | Después |
| --- | --- | --- | --- |
| HU006-01 | A obtiene el reporte de su consulta cerrada, con las 13 secciones | **FALLA** (404) | PASA |
| HU006-02 | El invitado obtiene su reporte con su credencial de capacidad | **FALLA** (404) | PASA |
| HU006-03 | Consulta abierta: 409 «El reporte estará disponible al terminar la consulta.», sin diagnóstico de referencia | **FALLA** (404) | PASA |
| HU006-04 | B pide el reporte de A: 404 sin datos de A | PASA (sin la ruta, 404) | PASA |
| HU006-05 | El invitado 2, con su credencial, pide el del invitado 1: 404 | PASA (sin la ruta, 404) | PASA |
| HU006-06 | Sin credencial: 401 | **FALLA** (404) | PASA |
| HU006-07 | Reporte ajeno y UUID inexistente: mismo código y mismo cuerpo | PASA (sin la ruta, 404) | PASA |
| HU006-08 | `finish.report` igual a `GET /report`, estable en tres lecturas | **FALLA** | PASA |
| HU006-09 | Diagnóstico e hipótesis del primer cierre (cerrar otra vez no los cambia); referencia y diferenciales del caso | **FALLA** | PASA |
| HU006-10 | Puntaje: pesos de las obtenidas = `earned_weight`; preguntas = las puntuables del caso; mismo puntaje que la evaluación del cierre | **FALLA** | PASA |
| HU006-11 | Por qué de cada pregunta que faltó: tipo, crítico y diferenciales que ayudaba a descartar, tomados del caso | **FALLA** | PASA |
| HU006-12 | Exámenes recomendados clasificados en pedidos, no pedidos u otras indicaciones | **FALLA** | PASA |
| HU006-13 | La propuesta «Le indico paracetamol para el dolor» con sus alertas, y el tratamiento de referencia | **FALLA** | PASA |
| HU006-14 | Evidencia revelada: mismos ids y orden que la consulta, con el texto del caso | **FALLA** | PASA |
| HU006-15 | Ningún id de evidencia ni nombre de diagnóstico o diferencial de otro caso (revisa los 43 casos) | **FALLA** | PASA |
| HU006-16 | 401, 404 y 409 sin rutas, trazas, SQL ni claves | **FALLA** | PASA |
| HU006-17 | El intento de B sobre `/report` deja una línea `[autorizacion] 404 ... motivo=ajena` con su id | **FALLA** | PASA |

## 3. Contrato del reporte

Detalle completo en `01_contrato_reporte.md` (+ `.png`). En resumen:

- `GET /api/ai/sessions/{id}/report`: 200 al dueño con la consulta cerrada; 409 si sigue abierta; 401 sin
  credencial; 404 ajena o inexistente (mismo cuerpo). `POST /finish` devuelve además `report`.
- El cierre guarda el diagnóstico y las hipótesis del alumno en la consulta, solo la primera vez.
- El reporte lo arma el **motor de evaluación**, el único que (con el de seguridad) puede leer la parte protegida
  del caso; no consulta el RAG ni el modelo de lenguaje y descarta cualquier id de otro caso.
- El «por qué» de lo que faltó usa una frase fija por tipo de omisión, la marca «Crítico» y los diferenciales que
  ese dato ayudaba a descartar: no se escribe texto clínico nuevo.
- El diagnóstico escrito no se califica automáticamente: se muestra junto al de referencia.

## 4. Cambios de código

| Commit | Archivo | Cambio |
| --- | --- | --- |
| `c835f86`, `8f1d254`, `0a1d735` | `backend/server/engine/evaluation/report.py`, `service.py` | `build_report(session, case, events)` y `ClinicalEvaluationEngine.report(session, events)` |
| `169c005` | `backend/server/orchestration/service.py`, `backend/server/api/ai.py` | `finish(session_id, diagnosis, hypotheses)` guarda la propuesta; `report(session_id)` y `SessionNotFinished`; ruta `GET /report` con `authorize_session` y 409 |
| `fc76495` | `frontend/public/simulacion.html`, `css/simulacion.css` | Secciones nuevas de la hoja con sus estilos; una sección solo se oculta si todas sus listas están vacías |
| `c5fafb5` | `frontend/public/js/simulacion.js` | `showEvaluation(report, diagnosis)` pinta el reporte con `textContent` |

Diff completo: `ejecucion/06_git_diff_cambios.txt` (8 archivos, 421 líneas agregadas y 52 eliminadas). Capturas
del código: `codigo/`. Pruebas y herramientas: `753cbc6` (inventario de TA-011), `36177d5` y `06032f7` (suite
HU006), `b8c1366` (43 casos), `375ff0e`, `a17cb62`, `9e24bf1` (lanzadores).

## 5. Defectos y hallazgos

| ID | Severidad | Defecto o hallazgo | Evidencia | Estado |
| --- | --- | --- | --- | --- |
| D-01 | Media | No existía un reporte final: la hoja solo mostraba conteos, sin qué faltó ni por qué | `resultados/local_antes/` (HU006-01 a 03) | Corregido (`169c005`, `fc76495`, `c5fafb5`) |
| D-02 | Media | El diagnóstico y las hipótesis del alumno no se guardaban en la consulta (solo en `intentos`, que no existe en producción) | HU006-09 | Corregido (`169c005`) |
| D-03 | Baja | La primera versión del reporte leía la parte protegida del caso fuera de los motores | `intentos/02_reporte_fuera_del_motor/` | Corregido (`8f1d254`) |
| D-04 | Baja | Los datos con valor y unidad (sin `text`) salían vacíos | `ejecucion/tdd/t4_valor_unidad_red.txt` | Corregido (`0a1d735`) |
| D-05 | Baja | Un dato revelado repetía su etiqueta en la hoja | `intentos/05_dato_con_etiqueta_repetida/` | Corregido (`c5fafb5`) |
| D-06 | Media (entorno) | Las claves de Groq del entorno Preview de Vercel no funcionan (D-09 de TA-011) | `ejecucion/09_preview_vercel.txt` | Abierto: bloquea la suite en el preview |
| D-07 | Baja (datos) | 10 preguntas clave tienen como nombre el enunciado completo del examen original; nunca llegan al reporte (son evidencia inicial) | `test_report_all_cases.py` (ningún nombre de más de 120 caracteres) | Sin cambios en los datos |

## 6. Bloqueos y dependencias

- **Depende de TA-011**, que todavía no está en `main`: la rama sale de `ta-011-autorizacion-sesiones` y usa su
  `authorize_session`. Hay que integrar TA-011 primero o las dos juntas.
- **Preview de Vercel: bloqueado.** Con el token de bypass, el preview responde y `GET /report` sin credencial da
  401, pero sus tres claves de Groq quedan `available: false` al primer mensaje (en producción, `true`). Falta
  configurar `GROQ_API_KEYS` para el entorno Preview en Vercel y repetir con
  `correr_suite.ps1 -Fase vercel_preview -Modo vivo` y `probar_navegador.cjs` con `VERCEL_BYPASS`.

## 7. Riesgos residuales

1. **El reporte se pide una sola vez al cerrar.** Si el servidor no responde en ese momento, la hoja muestra «No se
   pudo obtener el reporte»; no reintenta. Mejora posible: botón para pedirlo con `GET /report`.
2. **Recargar la página pierde el reporte del invitado**, porque la credencial vive solo en memoria (igual que la
   consulta, TA-011). El alumno registrado podría pedirlo de nuevo; la pantalla aún no lo ofrece.
3. **El «por qué» es genérico por tipo.** No hay explicaciones clínicas por dato sin revisión médica; los
   diferenciales que ayudaba a descartar sí son específicos del caso.
4. **Cierre algo más lento.** El cierre ahora lee los eventos para armar el reporte: unos 4,3 s en vivo contra
   Supabase (`intentos/07_corte_de_red_con_supabase/`).

## 8. Recomendación

**SÍ: HU-006 cumple sus cinco criterios de aceptación** con el código de la rama `hu-006-reporte-final`:

- **CA1:** con la consulta abierta el reporte responde 409 sin datos protegidos (local, vivo y navegador).
- **CA2:** solo el dueño lo obtiene; sin credencial 401, ajeno o inexistente 404 con el mismo cuerpo, y cada
  intento ajeno queda en el registro del servidor.
- **CA3:** el reporte trae diagnóstico de referencia y propuesto, hipótesis, diferenciales, puntaje y preguntas
  clave con su porqué, exámenes, tratamiento propuesto y de referencia, evidencia revelada y recomendaciones, y la
  hoja los muestra.
- **CA4:** ningún dato de otro caso en el reporte de los 43 casos curados, y el control negativo demuestra que la
  prueba lo detectaría.
- **CA5:** 21 de 21 comprobaciones en el navegador real y 17 de 17 en vivo contra el Supabase de producción.

**Reserva:** falta la repetición en el preview de Vercel (sección 6). La decisión final es del Product Owner.

## Verificación final

- [x] Cada caso ejecutado tiene su JSON y su tarjeta (`resultados/verificacion_capturas.txt`).
- [x] Ningún token, clave secreta, clave publicable ni token de bypass en las evidencias (búsqueda directa con los
      valores del `.env`).
- [x] Regresión antes (461) y después (582), con el entorno fijo en memoria.
- [x] Datos de prueba limpios en Supabase: cada corrida en vivo borró sus usuarios y consultas
      (`limpieza.json`); las 6 consultas del navegador y sus 36 eventos se borraron
      (`ejecucion/10_limpieza_navegador.txt`); Auth quedó con sus 2 usuarios.
- [x] Fotos reales de terminal de cada ejecución, incluidas las corridas en rojo y en verde de cada tarea
      (`ejecucion/tdd/`), y los intentos 1 a 8 conservados sin modificar.
