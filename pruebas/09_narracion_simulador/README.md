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

## Interrogatorio por micrófono (intento 3)

Como en el simulador original (`f0881ca`): al terminar la presentación desaparece el botón de inicio
(no hay «cambiar de caso»; para otro paciente se vuelve al inicio) y aparecen «Pulsa para hablar» y
«Realizar Diagnóstico».

- **Micrófono:** reconocimiento de voz del navegador (`es-ES`), con la transcripción en vivo en la
  consulta («Escuchándote...» y el texto parcial). Al terminar, la frase queda como burbuja del
  estudiante. Pulsar mientras alguien habla lo interrumpe y abre el micrófono.
- **Respuesta:** si el servidor tiene los agentes (`/api/ai`, rama `feature/integracion-sma-rag`), el
  simulador abre una sesión al iniciar y envía cada frase; responde el agente que corresponda (paciente
  con su burbuja y los puntos de «pensando»; doctor, laboratorio, radiología o especialista con la
  burbuja del equipo), con voz. Sin agentes, el doctor avisa que el interrogatorio todavía no está
  disponible.
- **Hipótesis:** agregar (escrita o dictada), descartar con motivo y retomar. El original las
  comparaba con los diferenciales del caso (`/api/hipotesis`); eso queda para la evaluación.
- **Diagnóstico:** escrito o dictado; al guardarlo se cierra la consulta (y la sesión de agentes).
  El puntaje y el reporte del original dependían de un guion fijo; la evaluación es parte del motor
  clínico (Julio).
- [probar_interrogatorio.cjs](probar_interrogatorio.cjs) sustituye el micrófono por uno simulado que
  «dice» frases de prueba, porque el navegador automático no tiene micrófono.
- Sin agentes (esta rama): [sin_agentes_1_listo_para_preguntar.png](sin_agentes_1_listo_para_preguntar.png),
  [sin_agentes_2_transcribiendo.png](sin_agentes_2_transcribiendo.png),
  [sin_agentes_3_respuestas.png](sin_agentes_3_respuestas.png),
  [sin_agentes_4_diagnostico.png](sin_agentes_4_diagnostico.png) y
  [sin_agentes_terminal.png](sin_agentes_terminal.png). El único error de consola es el 404 de
  `/api/ai/sessions`, que en esta rama no existe.

- Con agentes (rama `feature/integracion-sma-rag`, sin clave de LLM):
  [con_agentes_cirugia_general_3_respuestas.png](con_agentes_cirugia_general_3_respuestas.png) y
  [con_agentes_medicina_interna_3_respuestas.png](con_agentes_medicina_interna_3_respuestas.png)
  (con sus capturas 1, 2 y 4) y [con_agentes_terminal.png](con_agentes_terminal.png): el paciente
  revela los antecedentes familiares, el laboratorio las pruebas de coagulación y el doctor la
  exploración; sin errores de consola. Sin LLM, la respuesta es el texto del dato tal como está en el
  índice (con su etiqueta y el código de interpretación, «A» o «N»); con una clave de Groq el agente
  lo redacta.

## Evidencia

- Intento 2 (sin código del caso): [portada_3_simulador_listo.png](portada_3_simulador_listo.png) (al
  entrar, solo «Iniciar simulación»), [portada_4_caso_presentado.png](portada_4_caso_presentado.png) y
  [probar_portada_sin_codigo_terminal.png](probar_portada_sin_codigo_terminal.png) (la API devuelve
  EME-001 y el código no está visible en pantalla).
- Intento 1 (con el código del caso y el selector en el simulador): las capturas `narracion_*.png`,
  `portada_1` y `portada_2` se volvieron a tomar en el intento 2; las del intento 1 se conservan en el
  historial de Git (commits `e2de531` y `81f5489`), junto con `portada_3_caso_presentado.png` y
  `probar_portada_terminal.png`, que siguen en esta carpeta.
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
