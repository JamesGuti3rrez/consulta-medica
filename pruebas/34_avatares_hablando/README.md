# 34. Avatares que hablan: imagen quieta y video en bucle (LivePortrait)

La escena de la consulta (fase 29) mostraba ilustraciones fijas del doctor y del paciente. Ahora cada personaje es
una imagen realista sobre el mismo consultorio y mueve la boca mientras habla:

- **Doctor** presenta el caso; luego aparece **el paciente**, hombre o mujer según `patient.sex` del caso.
- Mientras suena la voz se ve un **video en bucle** del personaje hablando; en los silencios (comas, pausas entre frases)
  vuelve su **imagen quieta**. Solo se ve un personaje a la vez.

## Cómo se hicieron los videos

Con LivePortrait (KwaiVGI) en Google Colab (GPU T4): imagen del personaje (Gemini, montada en Photopea sobre el fondo del
consultorio a 1280x720) + video guía de 4-5 s de una persona hablando de frente, con pasteback para conservar el
consultorio. Resultado: un MP4 de 5,36 s (75 fotogramas, 14 fps) por personaje. Los originales están en
`frontend/src/assets/avatars/videos/` (`doctor-hablando.mp4`, `paciente-hombre-hablando.mp4`,
`paciente-mujer-hablando.mp4`, renombrados sin espacios desde Descargas).

## Qué se verificó del plan inicial y qué se cambió

| Plan inicial | Qué se hizo | Por qué |
|---|---|---|
| Usar `medico.png`, etc. como imagen quieta | La imagen quieta es el **primer fotograma del video** | El PNG de Photopea y el video difieren en color (~2 niveles de 255 en promedio) por la compresión; el primer fotograma coincide al píxel y tiene la boca cerrada, así el cambio no se nota. |
| Repetir el video tal cual | **Bucle de ida y vuelta** (adelante y luego al revés, 10,6 s) | El último fotograma tiene la boca abierta: al volver al inicio se veía un salto. |
| `edge_tts` con `boundary="WordBoundary"` para saber cuándo se pronuncia cada palabra | Se mide el **volumen del audio que suena** (Web Audio, `AnalyserNode`) | `/api/voz` transmite el audio en trozos para que suene enseguida; pedir los tiempos de palabra obligaba a esperar el audio completo o a sintetizar dos veces. El volumen sigue al audio real, incluidas las pausas de las comas. |
| Voces: médico es-PE-AlexNeural, paciente hombre es-MX-JorgeNeural, paciente mujer es-PE-CamilaNeural | Se mantienen las de TA-019 (`backend/server/voice/tts.py`) | Ya estaban decididas y probadas: paciente hombre Alex, paciente mujer Camila, y el doctor nunca comparte voz con el paciente (Jorge con paciente hombre, Alex con paciente mujer). |
| Imágenes con gesto de dolor (`paciente-*-dolor.png`) | No se integraron | No están entre los archivos entregados. |
| Archivos en `public/` sin espacios y misma resolución | Así quedó: `frontend/public/assets/avatars/*-hablando.mp4` (1280x720) e imágenes `*-1280.webp` / `*-800.webp` (16:9) | La escena pasó de la proporción 1376/768 a 16:9, la del video. |

Si la voz neuronal falla y habla la del navegador, la boca se mueve durante toda la frase. Si el navegador no puede
reproducir el video, se queda la imagen quieta y la consulta sigue igual (comprobado en la fase 36 bloqueando los videos).

## Cambios

| Qué | Dónde |
|---|---|
| Preparar los videos (bucle de ida y vuelta, imagen quieta = primer fotograma); necesita ffmpeg y se ejecuta solo al cambiar un video | `frontend/scripts/prepare-avatar-videos.mjs` |
| Imágenes quietas (fuente) y videos originales | `frontend/src/assets/avatars/*.png`, `frontend/src/assets/avatars/videos/*.mp4` |
| Videos publicados | `frontend/public/assets/avatars/*-hablando.mp4` |
| Imágenes web en 1280 y 800 px | `frontend/scripts/optimize-images.mjs` |
| Escena en 16:9 y video encima de la imagen | `frontend/public/simulacion.html`, `frontend/public/css/simulacion.css` |
| Video por personaje, medidor de volumen y alternancia | `frontend/public/js/simulacion.js` (`sceneVideo`, `setTalking`, `followVoice`, `stopLips`) |
| Prueba E2E | `pruebas/34_avatares_hablando/probar_avatares.cjs` |

## Cómo se probó

Servidor aparte en el puerto 3100, sin tocar Supabase de producción ni el servicio RAG externo, con la voz neuronal activa:

```
cd backend
PYTHONUNBUFFERED=1 SESSION_STORE=memoria CASE_STORE=local RAG_BACKEND=local RAG_EMBEDDED=false RAG_SERVICE_URL= \
SYNTHETIC_CASE_DATA=false LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false HISTORIAL_ALUMNOS=false TTS_PROVIDER=edge \
.venv/Scripts/python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 3100
```

`probar_avatares.cjs` usa Google Chrome instalado (el navegador que usan los estudiantes) y toma una muestra de la
escena cada 40 ms: personaje en escena, video visible, si suena el audio de la voz neuronal y si habla la voz del navegador.

## Resultados

| Corrida | Archivo | Resultado |
|---|---|---|
| Paciente hombre (CIR-005), escritorio 1440x1000 | `ejecucion/01_paciente_hombre` | 16 de 16 |
| Paciente mujer (CIR-006), escritorio 1440x1000 | `ejecucion/02_paciente_mujer` | 16 de 16 |
| Regresión de la escena de la fase 29 (Chromium de Playwright) | `ejecucion/03_regresion_escena_29` | 18 de 18 |

Corrección (fase 36): una versión anterior de este README decía que el Chromium de Playwright no reproduce H.264 y que
la regresión 03 solo mostraba imágenes quietas. En Windows sí lo reproduce (usa los códecs del sistema; medido en
`pruebas/36_sp006_voz_y_avatar`), así que esa regresión no probó el respaldo sin video. El respaldo se probó después,
bloqueando los videos, en la fase 36.

Comprobaciones principales: el video y la imagen tienen 1280x720 y ocupan la misma caja; durante la presentación el video
del doctor aparece y desaparece con las pausas (11 a 17 veces); nunca se ve un video sin audio sonando, nunca el de otro
personaje ni durante el cambio de personaje; el paciente correcto (hombre o mujer) habla con su video y queda quieto al
terminar. Cada corrida tiene su salida (`.txt`), la foto real de la terminal (`_terminal.png`), capturas de la escena
(`resultados/<corrida>/`) y el registro `avatares_registro.json`. Las imágenes PNG quedan solo en el equipo.

## Intentos fallidos (se conservan)

| Intento | Qué pasó |
|---|---|
| `intentos/01_rag_externo_y_medida_srcset` | El servidor de prueba heredó del `.env` `RAG_SERVICE_URL`, un servicio local que no estaba levantado: el paciente no respondió. Además, la prueba medía la imagen con `naturalWidth`, que con `srcset` viene corregido por la densidad (950x534) y no es el tamaño del archivo. Se fijó `RAG_SERVICE_URL` vacío y `RAG_EMBEDDED=false`, y la prueba mide el archivo elegido. |
| `intentos/02_llm_no_disponible` | El agente del paciente respondió 503 (`proveedor_no_disponible`). En el mismo momento edge-tts no resolvía `speech.platform.bing.com` (`getaddrinfo failed`): fue una caída de la conexión a internet. Las tres claves de Groq respondían bien al revisarlas; al repetir pasó. |
| `intentos/03_paciente_mujer_sin_audio_medido` | La respuesta de la paciente se vio con su video, pero la prueba no midió audio de la voz neuronal y lo contó como «video sin audio». El registro del servidor estaba en búfer y se perdió, así que no se pudo confirmar si habló la voz del navegador (respaldo). Se añadió a la prueba la voz del navegador y el servidor se inició con `PYTHONUNBUFFERED=1`; al repetir, la paciente habló con la voz neuronal y pasó. |
