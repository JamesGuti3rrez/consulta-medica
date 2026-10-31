# HU-006 Reporte final: plan de implementación

> **Renumeración (2026-10-31):** esta historia ahora es **HU-007: Completar reporte final**. Se entregó como HU-006; los ids de los casos de su evidencia (HU006-01 a HU006-17) equivalen a HU007-01 a HU007-17 de `backend/tests/security/test_hu007_report.py`. La HU-006 nueva es «Proponer y registrar diagnóstico final» (`pruebas/28_diagnostico_final/`).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Al cerrar una consulta, el dueño recibe un reporte completo (diagnóstico de referencia y propuesto, preguntas clave obtenidas y faltantes con su porqué, exámenes, tratamiento, puntajes y evidencia revelada) armado solo con datos de ese caso, y la hoja de evaluación lo muestra.

**Architecture:** Una función pura `build_report` arma el reporte desde la sesión, el caso completo y los eventos. El servicio la llama al cerrar y en la ruta nueva `GET /api/ai/sessions/{id}/report`, protegida por `authorize_session` (TA-011). La pantalla pinta el reporte en la hoja actual.

**Tech Stack:** FastAPI + pytest (backend), JavaScript sin framework + Tailwind compilado (frontend), Playwright (navegador), docx (Word).

**Spec:** `docs/superpowers/specs/2026-10-28-hu006-reporte-final-design.md`

## Global Constraints

- Rama `hu-006-reporte-final` (sale de `ta-011-autorizacion-sesiones`).
- Un commit por cambio; mensajes en español, sin emojis, sin `Co-Authored-By` ni «Generated with».
- 409 con `{"detail": "El reporte estará disponible al terminar la consulta."}` si la consulta no está finalizada.
- Ningún `evidence_id` del reporte puede empezar con otro prefijo que `<case_id>.`.
- El reporte no llama al RAG ni al LLM.
- Texto del servidor en la pantalla siempre con `textContent`, nunca `innerHTML`.
- Las pruebas fijan `SESSION_STORE=memoria CASE_STORE=local RAG_BACKEND=local SYNTHETIC_CASE_DATA=false LANGSMITH_TRACING=false` salvo en modo vivo.
- Evidencia en `pruebas/26_reporte_final/`; fotos reales con `pruebas/_herramientas/captura_terminal.ps1`; intentos fallidos sin modificar en `intentos/`; fotos y Word solo en el equipo.

## Review Focus

1. Consulta cerrada sin ningún mensaje (cero evidencia pedida): el reporte sale igual, con todo en «faltó» y listas vacías donde corresponda. Prueba en Task 1.
2. Hipótesis o diagnóstico con caracteres especiales o HTML (`<b>`): se muestran como texto. Prueba en Task 5 (E2E) y en Task 1 (el reporte devuelve el texto tal cual).
3. Consultas creadas antes del despliegue (sin `student_diagnosis` en el estado): el reporte sale con la propuesta vacía, sin error 500. Prueba en Task 2.
4. Sesión en Supabase: el reporte tras recargar el estado desde el almacén (no solo en memoria). Prueba en Task 4, modo vivo.
5. Examen pedido que no está en `tests` del caso: no aparece como recomendado ni innecesario, solo en la evidencia revelada. Prueba en Task 1.

---

### Task 1: Función pura `build_report`

**Files:**
- Create: `backend/server/report/__init__.py`, `backend/server/report/builder.py`
- Test: `backend/tests/unit/test_report_builder.py`

**Interfaces:**
- Produces: `build_report(session: dict, case: dict, events: list[dict]) -> dict` con estas claves:
  `case_id`, `finished_at`, `patient` (`alias`, `age_years`, `sex`), `chief_complaint` (texto),
  `diagnosis` {`student`: str, `reference`: str, `synonyms`: list[str]},
  `hypotheses` [{`name`, `discarded`, `reason`}], `differentials` [str],
  `score` {`score`, `earned_weight`, `total_weight`, `completed_questions`, `total_questions`},
  `key_questions` {`obtained`: [Q], `missing`: [Q]} con Q = {`id`, `topic`, `weight`, `critical`, `error_type`,
  `error_name`, `why`: str, `helps_discard`: [str]},
  `tests` {`recommended_requested`, `recommended_missing`, `optional_requested`, `unnecessary_requested`: [{`name`, `label`}], `other_indications`: [str]},
  `treatment` {`proposed`: [{`message`, `alerts`: [str]}], `reference_summary`: str, `key_actions`: [str]},
  `revealed_evidence` [{`evidence_id`, `label`, `text`}], `recommendations` [str].
- `ERROR_NAMES` y textos de `why` por tipo (fijos):
  negligencia → «Dato de seguridad: se pregunta antes de indicar un tratamiento.»;
  anamnesis_incompleta → «Forma parte de una historia clínica completa.»;
  razonamiento_clinico → «Orienta o confirma el diagnóstico del caso.».
- `recommendations`: los mismos tres textos de `RECOMMENDATIONS` de `frontend/public/js/simulacion.js:748-752`, uno por tipo con omisiones, más el de alerta de seguridad si hubo alertas; si no hay nada, el texto por defecto de `simulacion.js` («Mantén el mismo orden…»).

- [ ] **Step 1: Escribir las pruebas que fallan** con el caso `backend/tests/fixtures/cases/MED-900.json` y una sesión armada a mano:
  - `test_reporte_con_dos_preguntas_obtenidas`: pedidos `MED-900.anamnesis.inicio_dolor` y `MED-900.anamnesis.alergias` → `obtained` ids `["kq1","kq3"]`, `missing` ids `["kq2"]`, `missing[0].error_type == "negligencia"`, `critical is True`, `helps_discard == ["Meningitis", "Hemorragia subaracnoidea"]`, `score` igual al de `ClinicalEvaluationEngine.evaluate` para la misma evidencia.
  - `test_diagnostico_de_referencia_y_propuesta`: `diagnosis.reference == "Migraña sin signos de alarma"`, `synonyms == ["migraña","cefalea migrañosa"]`, `diagnosis.student` y `hypotheses` iguales a los de la sesión (incluido el texto `"<b>x</b>"` sin cambios).
  - `test_examenes`: pedido `MED-900.laboratorio.hemograma` → `optional_requested == [{"name":"hemograma","label":"Hemograma"}]`; `tomografia` corresponde a `MED-900.imagen.tomografia_craneo` (regla: el último segmento del id es igual al nombre o empieza por `nombre + "_"`) y, sin pedirla, no aparece en ninguna lista de pedidos; `evaluacion_clinica` no tiene evidencia → `other_indications == ["Evaluacion clinica"]` (guiones bajos por espacios, primera letra en mayúscula) y `recommended_missing == []`.
  - `test_tratamiento`: eventos `{"type":"turn","intent":"propose_treatment","student_message":"Indico paracetamol","safety_alerts":["known_allergy"]}` → `proposed == [{"message":"Indico paracetamol","alerts":["known_allergy"]}]`; `reference_summary` y `key_actions` del caso.
  - `test_evidencia_revelada`: cada id de `session["revealed_evidence_ids"]` aparece con `label` y `text` del caso, en el mismo orden.
  - `test_consulta_sin_preguntas`: sin evidencia pedida → `obtained == []`, los tres en `missing`, `tests` sin pedidos, no lanza.
  - `test_ids_ajenos_se_descartan`: un id `OTRO-001.x` en `revealed_evidence_ids` no aparece en el reporte.
- [ ] **Step 2:** `cd backend && .venv\Scripts\python.exe -m pytest tests/unit/test_report_builder.py -q` → falla por `ModuleNotFoundError: server.report`.
- [ ] **Step 3: Implementar `build_report`** usando `ClinicalEvaluationEngine` sólo si la sesión no trae `evaluation` (no recalcular la guardada); las preguntas puntuables son las mismas que excluye el motor (evidencia inicial vía `MultiAgentDisclosurePolicy.initial_evidence_ids`). Sin llamadas de red.
- [ ] **Step 4:** el mismo comando → todas pasan.
- [ ] **Step 5: Commit** `HU-006: la funcion build_report arma el reporte solo con datos del caso y la sesion`.

### Task 2: Servicio y API

**Files:**
- Modify: `backend/server/orchestration/service.py` (`finish`, nuevo `report`, `_public`)
- Modify: `backend/server/api/ai.py` (ruta `/report`, `finish` pasa diagnóstico e hipótesis, excepción → 409)
- Test: `backend/tests/integration/test_api_report.py`

**Interfaces:**
- Consumes: `build_report` (Task 1).
- Produces: `MultiAgentSessionService.finish(session_id: str, diagnosis: str | None = None, hypotheses: list[dict] | None = None) -> dict` guarda `student_diagnosis` y `student_hypotheses` sólo en el primer cierre; `MultiAgentSessionService.report(session_id: str) -> dict`; excepción `SessionNotFinished(Exception)` en `service.py`; `GET /api/ai/sessions/{session_id}/report` con `dependencies=[Depends(authorize_session)]`; la respuesta de `POST /finish` incluye `report`.

- [ ] **Step 1: Pruebas que fallan** (mismo arreglo que `tests/integration/test_api_sma.py:20-35`):
  - `test_reporte_solo_tras_cerrar`: invitado crea MED-900, `GET /report` con su credencial → 409 y el `detail` exacto; tras `finish` → 200 y `report.case_id == "MED-900"`.
  - `test_finish_devuelve_el_mismo_reporte`: `finish(...)["report"] == GET /report`.
  - `test_cerrar_dos_veces_no_cambia_la_propuesta`: segundo `finish` con otro diagnóstico → `report.diagnosis.student` sigue siendo el primero.
  - `test_reporte_de_consulta_sin_propuesta_guardada`: borrar `student_diagnosis` del estado en `STORE` → 200, `diagnosis.student == ""`, `hypotheses == []`.
  - `test_reporte_ajeno_e_inexistente`: credencial de otra consulta → 404; sin credencial → 401; UUID inexistente → 404 con el mismo cuerpo.
- [ ] **Step 2:** `pytest tests/integration/test_api_report.py -q` → fallan (404 en `/report`).
- [ ] **Step 3: Implementar** en `service.py` y `ai.py`; `_public` no expone `student_diagnosis` ni `student_hypotheses`.
- [ ] **Step 4:** el mismo comando pasa; `pytest -q` completo (con el entorno de Global Constraints) pasa salvo `test_09` de TA-011.
- [ ] **Step 5: Commit** `HU-006: ruta GET /report solo para el dueno y despues del cierre`.

### Task 3: Inventario de rutas de TA-011

**Files:** Modify `backend/tests/security/test_ta011_session_authz.py:420-423`, `pruebas/25_autorizacion_sesiones/01_inventario_rutas.md`

- [ ] **Step 1:** agregar `"GET /api/ai/sessions/{session_id}/report"` a `expected` en `test_09`; agregar la fila de la ruta al inventario.
- [ ] **Step 2:** `pytest tests/security/test_ta011_session_authz.py -q -m "not vivo"` → 37 passed.
- [ ] **Step 3: Commit** `HU-006: el inventario de rutas de TA-011 incluye /report`.

### Task 4: Suite HTTP HU006 con evidencia (local y vivo)

**Files:**
- Create: `backend/tests/security/test_hu006_report.py`
- Modify: `backend/tests/security/conftest.py` (los hooks aceptan el marcador `hu006` además de `ta011`; la carpeta de evidencia sale de `HU006_EVIDENCIA` para `hu006`)
- Create: `pruebas/26_reporte_final/correr_suite.ps1` (copia de `pruebas/25_autorizacion_sesiones/correr_suite.ps1` con `HU006_*`), `pruebas/26_reporte_final/generar_capturas.py` (reusa el de la fase 25 con casos `HU006-XX`)

**Interfaces:**
- Consumes: la fixture `mundo` y `_mundo_vivo`/`_mundo_local` de `test_ta011_session_authz.py` (importarlas, no copiarlas); `Caso` de `ta011_evidencia.py`.
- Casos `@pytest.mark.hu006(id=..., criterio=..., titulo=..., nombre=..., esperado=...)`:
  HU006-01 A obtiene su reporte tras cerrar (200, todas las claves de Task 1) · 02 invitado con su credencial ·
  03 antes de cerrar: 409 sin `reference`, `key_questions` ni `treatment` en el cuerpo · 04 B sobre el reporte de A: 404 ·
  05 invitado 2 sobre el de invitado 1: 404 · 06 sin credencial: 401 · 07 ajeno igual a inexistente (mismo cuerpo) ·
  08 `finish.report` igual a `GET /report` y estable en tres lecturas · 09 propuesta guardada (diagnóstico e hipótesis) ·
  10 puntaje: suma de pesos de `obtained` = `earned_weight`, ids de `obtained`+`missing` = preguntas puntuables ·
  11 porqué: tipo, crítico y diferenciales coinciden con el caso · 12 exámenes clasificados según `tests` ·
  13 tratamiento propuesto con alerta (vivo: mensaje «Le indico aspirina», caso EME-001 si el caso lo permite) y de referencia ·
  14 evidencia revelada = `revealed_evidence_ids` de la sesión · 15 ninguna fuente ajena (ids con prefijo, ningún nombre de diagnóstico ni diferencial de otro caso) ·
  16 errores sin detalles internos · 17 el registro `[autorizacion]` anota el intento ajeno sobre `/report` (vivo: log del servidor).
- Antes = código de TA-011 (sin `/report`): los casos de contenido fallan con 404/405.

- [ ] **Step 1:** escribir los 17 casos y los cambios de `conftest.py`; `pytest tests/security -q -m "not vivo"` → TA011 37 passed y HU006 pasan.
- [ ] **Step 2:** en un worktree con el código de `ta-011-autorizacion-sesiones` (servidor sin `/report`) y la suite nueva, `correr_suite.ps1 -Fase local_antes` → fallan los casos de reporte.
- [ ] **Step 3: Commit** `HU-006: suite HTTP HU006-01 a HU006-17 con evidencia por caso` (pruebas) y `HU-006: herramientas de ejecucion de la fase 26` (scripts), por separado.

### Task 5: Hoja de evaluación

**Files:**
- Modify: `frontend/public/simulacion.html` (secciones nuevas dentro de la hoja, con `data-role`)
- Modify: `frontend/public/js/simulacion.js` (`showEvaluation(report, diagnosis)`; guardar `lastReport` para reabrir)
- Modify: `frontend/public/css/simulacion.css` (clases `.sheet-why`, `.sheet-chip` y variantes, `.sheet-compare`, `.sheet-fold`, tomadas del boceto aprobado `.superpowers/brainstorm/978-1793170287/content/reporte-secciones-v2.html`)
- Create: `pruebas/26_reporte_final/probar_navegador.cjs`

**Interfaces:**
- Consumes: `report` de la respuesta de `finish` (Task 2).
- `data-role` nuevos: `evaluation-reference`, `evaluation-key-ok`, `evaluation-key-missing`, `evaluation-tests-ok`, `evaluation-tests-warn`, `evaluation-other-indications`, `evaluation-differentials`, `evaluation-treatment-proposed`, `evaluation-treatment-reference`, `evaluation-treatment-actions`, `evaluation-revealed`.

- [ ] **Step 1:** `probar_navegador.cjs` (Playwright, como `pruebas/25_autorizacion_sesiones/probar_navegador.cjs`): invitado abre MED-007, pregunta, pide un examen, propone un tratamiento, registra una hipótesis con `<b>prueba</b>` y cierra; comprueba que cada `data-role` tiene contenido, que `<b>prueba</b>` aparece como texto, captura cada sección; otro navegador pide `/report` → 401/404; antes de cerrar `/report` → 409. Falla hoy porque las secciones no existen.
- [ ] **Step 2: Implementar** HTML, JS y CSS; sin `innerHTML` con datos del servidor; si `report` es nulo, el mensaje de error que ya existe.
- [ ] **Step 3:** con el servidor en `localhost:3000`, `node pruebas/26_reporte_final/probar_navegador.cjs pruebas/26_reporte_final/capturas` → código 0.
- [ ] **Step 4: Commit** HTML+CSS y JS por separado: `HU-006: secciones del reporte en la hoja de evaluacion` y `HU-006: el simulador pinta el reporte del servidor`.

### Task 6: Contenido en los 43 casos curados

**Files:** Create `backend/tests/integration/test_report_all_cases.py`

- [ ] **Step 1:** parametrizada sobre `data/cases/curated/*.json`, dos escenarios por caso (toda la evidencia `on_request` pedida; ninguna): `build_report` no lanza; cada `evidence_id` empieza con `<case_id>.`; ningún `topic` supera 120 caracteres; ningún nombre de diagnóstico o diferencial de otro caso aparece en el JSON del reporte (salvo los que el propio caso comparte); con toda la evidencia, `missing == []` y `score.score == 100.0`.
- [ ] **Step 2:** `pytest tests/integration/test_report_all_cases.py -q` → 86 passed.
- [ ] **Step 3: Commit** `HU-006: el reporte de los 43 casos curados no usa datos de otros casos`.

### Task 7: Ejecuciones, evidencia y documentos

**Files:** `pruebas/26_reporte_final/` (README, `01_contrato_reporte.md`, `INFORME_HU-006.md`, `ejecucion/`, `resultados/`, `capturas/`, `codigo/`, `intentos/`), `pruebas/README.md`, `Entregables/07_HU-006_Reporte_final/` (Word y PDF, solo en el equipo).

- [ ] **Step 1:** con foto de terminal cada una: regresión antes (rama TA-011) y después; suite HU006 local antes y después; suite en vivo antes (servidor con el código de TA-011) y después contra el Supabase de producción, verificando la limpieza; navegador real; preview de Vercel si sus claves de Groq ya funcionan (si no, queda como intento con su causa).
- [ ] **Step 2:** `generar_capturas.py` → tarjetas por caso, `evidencia.html`, `verificacion_capturas.txt` sin secretos; capturas del código cambiado.
- [ ] **Step 3:** README, contrato del reporte, informe con matriz CA1-CA5 → casos, defectos, intentos y recomendación; fila de la fase 26 en `pruebas/README.md`. Commits separados: resultados, herramientas y documentos.
- [ ] **Step 4:** Word y PDF del informe con el formato de TA-011 (generador del scratchpad), en `Entregables/07_HU-006_Reporte_final/`.
- [ ] **Step 5:** push de `hu-006-reporte-final`.
