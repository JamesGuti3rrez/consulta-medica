# Fase 9 · Presentación narrada del caso en el simulador (2026-10-09)

## Objetivo

Recuperar la presentación del caso que tenía el simulador original: al iniciar, el doctor presenta
al paciente con su burbuja sobre la escena y con voz, la ficha se completa a medida que habla y la
pestaña «Consulta» guarda cada intervención como mensaje de chat. Ahora el caso sale al azar del
catálogo curado, dentro de la especialidad elegida.

## Qué cambió

- `frontend/public/simulacion.html`: selector de especialidad junto al botón de inicio
  («Cualquier especialidad» o una de las cinco). Respeta `?especialidad=` en la URL.
- `frontend/public/js/simulacion.js`: al iniciar pide `GET /api/caso?especialidad=…` y el doctor
  narra, en orden, el paciente y el motivo de consulta, cada dato público de la ficha (datos de
  llegada, signos vitales…) y las alergias; termina con «Doctor, puede comenzar con el interrogatorio».
  La voz usa la síntesis del navegador (`es-ES`) y lee las unidades completas («109 sobre 62
  milímetros de mercurio»); si el navegador no tiene voz, cada frase dura un tiempo de lectura. «Cargar
  otro caso» detiene la narración en curso y empieza otra.
- La narración usa solo los datos públicos del caso (`to_student_case`): lo que está en
  `on_request` se sigue obteniendo al preguntar.

## Evidencia

- [narracion_1_narrando.png](narracion_1_narrando.png): pediatría elegida; el doctor presenta a la
  paciente y la ficha muestra solo lo narrado.
- [narracion_2_terminada.png](narracion_2_terminada.png): presentación terminada; historial de la
  consulta como chat.
- [probar_narracion_terminal.png](probar_narracion_terminal.png): ejecución de
  [probar_narracion.cjs](probar_narracion.cjs) (caso PED-010, sin errores en la consola del navegador).
- `capturar_frontend.cjs` (fase 4) sigue pasando: 5 casos, uno por especialidad, sin información
  protegida visible.

## Pendiente

El interrogatorio (micrófono o texto → agentes) no está conectado en esta rama: los agentes están en
`feature/integracion-sma-rag` (`/api/ai`). Al terminar la presentación, la consulta lo indica.
