# TA-021 · Calificación diagnóstica final

Código actual según `Backlog_Sprint2_Fases_y_Dependencias_Completado.docx`.
La carpeta `pruebas/TA-012` conserva el nombre usado cuando se ejecutaron las pruebas.
El informe actualizado está en `Entregables/Sprint2/TA-021_Calificacion_diagnostico_final.docx`.

Implementado el 28 de octubre de 2026. La comparación es determinística, usa exclusivamente
el diagnóstico y los sinónimos del caso y solo se invoca desde el cierre autorizado de la consulta.

| Escenario | Resultado | Puntuación | Motivo |
| --- | --- | --- | --- |
| Diagnóstico de referencia | correct | 100/100 | reference_match |
| Sinónimo admitido | correct | 100/100 | synonym_match |
| Incorrecto | incorrect | 0/100 | no_match |
| Vacío, ausente o null | empty | 0/100 | empty_input |
| Varias respuestas, duda o etiqueta compartida | ambiguous | 0/100 y revisión | multiple_answers, uncertain_answer o shared_label |

La normalización contempla Unicode NFKD, tildes, mayúsculas, espacios y puntuación.
También reconoce encabezados como «Mi diagnóstico final es:» y «Dx:».
La coincidencia es completa: no se acepta una palabra contenida en una frase, un error
tipográfico o una respuesta inventada por un modelo. Un sinónimo registrado que incluye
«probable» conserva su condición de respuesta admitida.

La nota del diagnóstico es **independiente** del puntaje de anamnesis. No se inventó una
ponderación entre ambos. Una respuesta ambigua recibe 0 automático y queda identificada
para revisión; no se confunde con una respuesta incorrecta ni implementa adjudicación manual.

## Persistencia y contrato

- Sesión: `state.diagnosis_evaluation` en `sma_sesiones`, cuando `SESSION_STORE=supabase`.
- Auditoría de cierre: `sma_eventos.payload.diagnosis_evaluation`.
- Historial: `intentos.reporte.diagnosis_evaluation`, si el historial está habilitado y el
  alumno tiene sesión. `intentos.puntaje` continúa representando la anamnesis.
- API de cierre: `POST /api/ai/sessions/{id}/finish` devuelve `diagnosis_evaluation`;
  el reporte contiene `diagnosis.grading` con el mismo resultado guardado.
- La consulta del reporte no vuelve a calificar. Los cierres repetidos conservan la
  propuesta y la nota originales, también si el primer guardado del historial falló.
- No se requieren columnas nuevas ni otra migración: se usan los JSONB existentes.
- Antes del cierre no se expone la nota, referencia ni sinónimos; se mantienen las
  credenciales de TA-011 y los códigos 401/404 para sesiones no autorizadas.
- Las consultas históricas cerradas sin esta nueva calificación siguen siendo legibles;
  no se recalifican automáticamente.

## Archivos principales

- `backend/server/engine/evaluation/diagnosis.py`: normalización y clasificador.
- `backend/server/engine/evaluation/service.py`: barrera de cierre.
- `backend/server/orchestration/service.py`: cierre, persistencia y entrega inmutable.
- `backend/server/engine/evaluation/report.py`: muestra la calificación persistida.
- `backend/server/api/ai.py` y `backend/server/persistence/attempts.py`: historial coherente.
- `frontend/public/js/simulacion.js`, `simulacion.html` y `css/simulacion.css`: resultado visual.
- `backend/tests/unit/test_final_diagnosis.py` y `integration/test_ta012_diagnosis.py`.

## Reproducción

Desde la raíz, en la terminal de VS Code:

```powershell
npm run setup -- --extras dev
$env:TA012_EVIDENCIA = (Join-Path (Get-Location) 'pruebas/TA-012/resultados')
npm run test:diagnosis -- --junitxml=../pruebas/TA-012/pytest.xml
```

Para el navegador, levantar otra instancia local en el puerto 3017 con
`CASE_STORE=local`, `SESSION_STORE=memoria`, `RAG_BACKEND=local`, `RAG_EMBEDDED=false`
y sin proveedores externos. Después:

```powershell
node frontend/tests/ta012.mjs
```

El navegador utiliza la API local real; solo se acelera la lectura de voz y se omite
la descarga de fuentes externas. No se simulan las respuestas de `/finish`.

## Evidencia obtenida

- `pytest.xml`: 566 pruebas aprobadas; 93 de TA-021. Otras tres pruebas de seguridad
  que requieren servicios reales se deseleccionaron por configuración.
- `resultados/*.json`: los cinco resultados HTTP y sus comprobaciones de persistencia.
- `navegador.json`: 5/5 escenarios aprobados con la API local real.
- `capturas/*.png`: resultado visible de correcto, incorrecto, sinónimo, vacío y ambigüedad.
- Se corrigió además la configuración de una prueba docente para que use credenciales
  ficticias y no dependa de tener un `.env` local.

Con el `.env` proporcionado se verificaron además **5/5 escenarios contra Supabase real**:
la puntuación y el motivo coinciden en `sma_sesiones` y `sma_eventos`, un servicio nuevo
recupera el resultado y repetir `/finish` conserva la entrega original. Se comprobó
el bloqueo anterior al cierre y la ausencia de acceso anónimo. La cuenta temporal,
las cinco sesiones y sus eventos se eliminaron y se confirmó la limpieza.

**Límite del historial:** `intentos` no está instalada en esta base (404/PGRST205) y
`HISTORIAL_ALUMNOS` está desactivado. La ruta opcional del historial se probó con
transporte HTTP simulado; no se afirma una escritura real en esa tabla. No se ejecutaron
migraciones ni se modificaron casos curados, roles existentes o el `.env`.

La evidencia remota está en `supabase_real.json`. Para repetirla:

```powershell
.\backend\.venv\Scripts\python.exe pruebas/TA-012/verificar_supabase_real.py
```

Este script necesita las claves del `.env`, crea datos temporales y los elimina al terminar.
No registra claves, contraseñas ni tokens. Los registros originales de las ejecuciones están
en `terminal/pytest.txt`, `terminal/supabase-real.txt` y `terminal/navegador.txt`.

Para capturar estos registros, se abre una ventana nativa propia de PowerShell por archivo,
se muestra el registro original sin modificarlo y se captura exclusivamente esa ventana:

```powershell
.\backend\.venv\Scripts\python.exe pruebas/TA-012/capturar_terminal.py
```

La captura requiere Pillow como herramienta documental. `terminal/capturas.json` conserva
la procedencia y el SHA-256 de cada registro. Estas son capturas de ventanas nativas que
muestran la salida registrada; no se presentan como capturas de la terminal integrada de VS Code.

## Documento Word

El generador requiere `python-docx` solo como herramienta de documentación:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install python-docx
.\backend\.venv\Scripts\python.exe pruebas/TA-012/generar_informe.py
```

Produce `Entregables/Sprint2/TA-021_Calificacion_diagnostico_final.docx`.
El generador exige que la batería, los cinco casos del navegador y las cinco comprobaciones
remotas estén aprobados, que la limpieza esté confirmada y que los registros coincidan
con los hashes de las capturas. Incorpora ocho capturas: cinco de la interfaz y tres
de los registros en PowerShell. El Word se entrega aparte
y está excluido de Git según la política actual del repositorio.

