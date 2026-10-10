# Fase 9 · Presentación narrada del caso en el simulador (2026-10-09)

## Objetivo

Recuperar la presentación del caso que tenía el simulador original: al iniciar, el doctor presenta
al paciente con su burbuja sobre la escena y con voz, la ficha se completa a medida que habla y la
pestaña «Consulta» guarda cada intervención como mensaje de chat. Ahora el caso sale al azar del
catálogo curado, dentro de la especialidad elegida.

## Qué cambió

- **Portada original restaurada** (`frontend/public/index.html`, `js/landing.js`, `css/landing.css`, tal
  como estaban en `f0881ca`). El commit `93ba45b` la había cambiado por una página genérica sin
  ejemplos. Con ella vuelve el recorrido original: «Probar la simulación» abre la ventana «Elige tu
  caso» (nombres, apellidos y especialidad) y «Generar caso aleatorio» lleva a
  `simulacion.html?especialidad=…`. Los nombres quedan en la sesión del navegador; en la URL solo
  viaja la especialidad.
- `frontend/public/simulacion.html`: en el primer intento tenía un selector de especialidad junto al
  botón de inicio; se quitó porque la especialidad ya se elige en la portada. Al entrar, el simulador
  muestra la especialidad recibida y solo el botón «Iniciar simulación».
- El estudiante no ve qué caso le tocó: ni el código del caso (EME-002…) en los mensajes ni en la
  etiqueta de la tablilla, que dice «En consulta». `capturar_frontend.cjs` comprueba ahora que el
  código no aparezca en pantalla.
- `frontend/public/js/simulacion.js`: al iniciar pide `GET /api/caso?especialidad=…` y el doctor
  narra, en orden, el paciente y el motivo de consulta, cada dato público de la ficha (datos de
  llegada, signos vitales…) y las alergias; termina con «Doctor, puede comenzar con el interrogatorio».
  La voz usa la síntesis del navegador (`es-ES`) y lee las unidades completas («109 sobre 62
  milímetros de mercurio»); si el navegador no tiene voz, cada frase dura un tiempo de lectura. «Cargar
  otro caso» detiene la narración en curso y empieza otra.
- La narración usa solo los datos públicos del caso (`to_student_case`): lo que está en
  `on_request` se sigue obteniendo al preguntar.

## Evidencia

- Intento 2 (sin código del caso): [portada_3_simulador_listo.png](portada_3_simulador_listo.png) (al
  entrar, solo «Iniciar simulación»), [portada_4_caso_presentado.png](portada_4_caso_presentado.png) y
  [probar_portada_sin_codigo_terminal.png](probar_portada_sin_codigo_terminal.png) (la API devuelve
  EME-001 y el código no está visible en pantalla).
- Intento 1: las capturas de abajo todavía muestran el código del caso y el selector de especialidad
  en el simulador.
- [portada_1_inicio.png](portada_1_inicio.png), [portada_2_elige_tu_caso.png](portada_2_elige_tu_caso.png)
  y [portada_3_caso_presentado.png](portada_3_caso_presentado.png): recorrido desde la portada
  (emergencias) hasta el caso presentado; [probar_portada_terminal.png](probar_portada_terminal.png),
  ejecución de [probar_portada.cjs](probar_portada.cjs) (EME-001, sin errores en la consola).
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
