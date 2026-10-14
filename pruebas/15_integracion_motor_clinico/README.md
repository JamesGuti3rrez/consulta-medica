# 15. Integración del motor clínico

> Numeración: este README usa los códigos de casos anteriores a la fase 23. Equivalencias actuales: MED-008 → MED-007 (Patricia Vargas), MED-009 → MED-008 (Alberto Núñez) y PED-007 → PED-009 (Mateo Quispe).

## Objetivo

Integrar a `main` el trabajo de la rama `julio` (motor clínico: estado del avatar, alertas de seguridad
y evaluación final) y dejarlo conectado de punta a punta: API, sesiones guardadas y simulador.

## Qué se hizo

| Paso | Cambio | Commit |
| --- | --- | --- |
| 1 | Integración de los 18 commits de `julio` sin conflictos (avance rápido, la rama ya contenía todo `main`) | `9548f90` |
| 2 | Docstring duplicado en `engine/evaluation/__init__.py` | `5f1271e` |
| 3 | La evaluación ya no penaliza la evidencia que se entrega al presentar el caso (ver intento 1) | `e28ad2f` |
| 4 | Los scripts de `14_motor_clinico/` guardan sus resultados en `14_motor_clinico/resultados/` y el README no usa rutas de otro equipo | `93c9d11` |
| 5 | Resultados del motor con los 13 casos curados | `57fd356` |
| 6 | La «Hoja de evaluación clínica» del simulador, que existía en `simulacion.html` sin datos, se llena con la respuesta de `/finish` | `fac6423` |
| 7 | Documentación en `frontend/README.md` y `backend/server/README.md` | `6d27164` |

Conexiones revisadas:

- **API**: `POST /api/ai/sessions` devuelve `avatar_state`; cada `/message` devuelve `safety_alerts`;
  `/finish` devuelve `evaluation`.
- **Sesiones en Supabase**: el estado se guarda como JSONB en `sma_sesiones.state`, así que los campos
  nuevos (`avatar_state`, `requested_evidence_ids`, `evaluation`) no necesitan migración. Las sesiones
  creadas antes de la integración se completan al vuelo (`_ensure_clinical_state`).
- **Simulador**: muestra la alerta de seguridad al proponer un tratamiento contraindicado y, al guardar el
  diagnóstico, abre la hoja con puntaje, datos clave obtenidos, omisiones por tipo de error, hipótesis y
  recomendaciones. El botón «Realizar Diagnóstico» pasa a «Ver hoja de evaluación».
- **Datos protegidos**: la hoja solo recibe puntaje y conteos; no se muestran temas, fármacos ni motivos
  de `protected`, y el código del caso no aparece en pantalla.

## Comandos

Desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe ..\pruebas\14_motor_clinico\probar_casos_curated.py
```

Pruebas del simulador en el navegador, con el servidor en modo local determinístico (sin Groq) en el
puerto 3000. En PowerShell, desde `backend/`:

```powershell
$env:GROQ_API_KEYS = ""; .\.venv\Scripts\python.exe -m uvicorn server.main:app --port 3000
```

Y desde la raíz, en otra terminal:

```powershell
node pruebas/15_integracion_motor_clinico/probar_evaluacion.cjs completo
node pruebas/15_integracion_motor_clinico/probar_evaluacion.cjs parcial
```

`completo` pide los datos clave de MED-008 y propone doxiciclina (contraindicada en el caso); `parcial`
hace solo una pregunta y la misma propuesta.

## Resultados

| Ejecución | Resultado | Evidencia |
| --- | --- | --- |
| Pruebas del backend | 151 aprobadas (150 de la rama más la nueva de evaluación) | `ejecucion/01_pruebas_backend.txt`, `_terminal.png` |
| Motor con los 13 casos curados | Roles, evidencia y signos vitales correctos en todos; alertas en EME-103 y MED-008; 100 % al pedir todos los datos clave | `ejecucion/02_motor_casos_curados.txt`, `_terminal.png` |
| Simulador, guion completo | Alerta de contraindicación en pantalla; hoja con 100 %, 4 de 4 datos clave; la hoja se cierra y se reabre; sin errores de consola | `ejecucion/03_simulador_completo.txt`, `_terminal.png`, `resultados/completo_*.png` |
| Simulador, guion parcial | Hoja con 18,75 %, 1 de 4 datos clave y una omisión de cada tipo (negligencia, anamnesis incompleta, razonamiento clínico) | `ejecucion/04_simulador_parcial.txt`, `_terminal.png`, `resultados/parcial_*.png` |

Las fotos (`.png`) se guardan en el equipo y no se suben a GitHub.

## Prueba en Vercel (producción)

El push a `main` (commit `04d9395`) desplegó automáticamente el sitio en
`https://consulta-medica-three.vercel.app`; GitHub marcó el despliegue como «Deployment has completed».
Allí el servidor usa el modelo real (Groq, `openai/gpt-oss-20b`) y guarda las sesiones en Supabase.

```powershell
$env:BASE_URL = 'https://consulta-medica-three.vercel.app'
node pruebas/15_integracion_motor_clinico/probar_evaluacion.cjs parcial pruebas/15_integracion_motor_clinico/vercel
```

| Comprobación | Resultado |
| --- | --- |
| Respuestas de los agentes | Redactadas por Groq; el doctor anota la doxiciclina sin revelar la contraindicación |
| Alerta de seguridad | `case_contraindication` en pantalla al proponer doxiciclina |
| Hoja de evaluación | 18,75 %, 1 de 4 datos clave, una omisión de cada tipo y las cuatro recomendaciones; se cierra y se reabre |
| Sesión en Supabase | Una sesión aparte, leída de nuevo tras `/finish`, conserva la evaluación guardada |
| Datos protegidos | El código del caso no aparece en pantalla; sin errores de consola |

Evidencia: `vercel/05_simulador_vercel.txt`, `vercel/05_simulador_vercel_terminal.png` y las capturas
`vercel/parcial_*.png`.

## Intentos fallidos

### Intento 1: la evaluación tenía un techo imposible

`intentos/01_evaluacion_con_techo/` guarda la corrida del motor tal como llegó de la rama `julio`
(ejecutada sobre el commit `9548f90` en una copia temporal del repositorio). En 10 de los 13 casos el
puntaje máximo quedaba entre 72,73 % y 86,36 % aunque se pidieran todos los datos.

Causa: en los casos convertidos de MedQA, la pregunta clave `kq1` exige `motivo.queja_principal`, que el
doctor entrega al presentar el caso. El evaluador solo contaba la evidencia *pedida* por el estudiante,
así que esa pregunta nunca se cumplía y siempre sumaba un error de razonamiento clínico.

Corrección (`e28ad2f`): las preguntas cuya evidencia ya está en la presentación no se puntúan ni cuentan
como omisión. Prueba nueva: `test_evidence_given_at_the_start_does_not_count_as_an_omission`.

De esta corrida solo hay `.txt` y `.json`: se hizo sin foto de terminal y la copia temporal ya se borró.

### Intento 2: panel de evaluación duplicado

`intentos/02_panel_duplicado/` guarda la primera prueba en el navegador. Se había agregado un panel de
evaluación nuevo con `data-role="evaluation-panel"`, sin notar que `simulacion.html` ya tenía la «Hoja de
evaluación clínica» con el mismo `data-role`, diseñada y sin conectar. Playwright encontró dos elementos y
se detuvo. Corrección: se quitó el panel nuevo y se conectó la hoja existente.

## Observaciones

- El puntaje mide los datos clave obtenidos; no califica el diagnóstico escrito. La hoja lo dice.
- En los casos de MedQA, el `topic` de `kq1` es el enunciado original completo de la pregunta. No se
  muestra (la API solo devuelve conteos), pero conviene limpiarlo en la conversión de casos.
- La prueba del navegador usa el proveedor local determinístico; con Groq el flujo es el mismo, pero la
  redacción de las respuestas cambia.
