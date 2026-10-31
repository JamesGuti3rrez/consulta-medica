# 32. Cierre de consulta mientras falta la migración 0007

El localhost usa el Supabase real (`SESSION_STORE=supabase`). Hasta aplicar la migración 0007 no existe la tabla
`diagnosticos_finales`, así que el cierre de un alumno con sesión respondía 503 y la consulta quedaba abierta:
en local ningún alumno podía terminar una consulta ni entregar una actividad de grupo.

Ahora, si Supabase responde que la tabla no existe (HTTP 404 con código `PGRST205`):

- **El cierre funciona igual.** La consulta se cierra y el diagnóstico queda en la consulta y en el reporte final.
  El alumno ve «Tu diagnóstico quedó guardado en esta consulta.» y el servidor responde
  `registro = {"guardado": false, "motivo": "registro_pendiente"}`.
- **El registro por intentos espera a la migración.** No se numeran los intentos hasta que se aplique; después el
  registro funciona solo, sin cambiar nada.
- **El resto de fallos no cambia.** Un error 500 o 503 de Supabase, o una caída de red, siguen respondiendo 503 y
  dejan la consulta abierta (HU-006).

## Cambios

| Qué | Dónde |
|---|---|
| `DiagnosisTableMissing`, solo para la tabla inexistente (`PGRST205`) | `backend/server/persistence/diagnoses.py` |
| El cierre continúa sin registro por intentos y lo informa como `registro_pendiente` | `backend/server/api/ai.py` |
| Mensaje para el alumno | `frontend/public/js/simulacion.js` |
| Tabla inexistente en el Supabase simulado (`fail_tables[...] = "sin_tabla"`) | `backend/tests/fakes_supabase.py` |
| Pruebas (7) | `backend/tests/integration/test_hu006_sin_migracion.py` |
| Prueba en el navegador contra el localhost real | `pruebas/32_cierre_sin_migracion/probar_cierre_alumno.cjs` |

## Resultados

| Corrida | Archivo | Resultado |
|---|---|---|
| Pruebas con el código anterior | `ejecucion/01_antes` | 2 fallan (las del comportamiento nuevo), 5 pasan |
| Navegador, localhost real sin la tabla, código anterior | `ejecucion/02_navegador_antes` | 5 de 8: el cierre responde 503 y no aparece la hoja |
| Navegador, localhost real sin la tabla, con la corrección | `ejecucion/03_navegador_despues` | 10 de 10 |
| Pruebas con la corrección | `ejecucion/04_despues` | 7 de 7 |
| Regresión completa del backend | `ejecucion/05_regresion_backend` | 875 pasan |

La prueba de navegador crea un alumno temporal en Supabase Auth y lo borra al terminar.
