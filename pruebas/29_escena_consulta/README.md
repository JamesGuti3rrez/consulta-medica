# 29. Escena de la consulta: doctor y paciente con globo de diálogo

Con el diálogo directo (TA-017 de Rodrigo) el estudiante le pregunta al paciente sin que el doctor repita la
pregunta. La escena del simulador acompaña ese cambio. Antes era una sola ilustración fija con el doctor y el
paciente; ahora muestra solo a quien habla:

- **Presentación del caso:** el doctor, con su globo de diálogo.
- **Interrogatorio:** el paciente, en versión hombre o mujer según el sexo del caso, con su globo.
- **Hallazgos durante el interrogatorio:** si el doctor o un servicio (laboratorio, radiología o especialista) entrega
  un hallazgo, aparece el doctor con su globo. Al terminar el turno vuelve el paciente y el globo del doctor se retira;
  lo que dijo queda en el chat.
- **Globos:** en escritorio van al lado del personaje, con el pico apuntando hacia él (el del doctor a la derecha y el
  del paciente a la izquierda). En el celular van debajo de la imagen, para no tapar la cara.

La prueba se hizo junto con la unión de la rama de Rodrigo en James. Por eso esta carpeta también reúne la regresión de
todo lo que convive en el simulador: grupos, diálogo directo, panel docente, diagnóstico final, reporte final y voz.

## Cambios

| Qué | Dónde |
|---|---|
| Imágenes originales (doctor, paciente hombre, paciente mujer) | `frontend/src/assets/avatars/*.png` |
| Versiones web en dos anchos (800 y 1376 px), generadas por `npm run build:images` (también en Vercel) | `frontend/scripts/optimize-images.mjs` → `frontend/public/assets/avatars/*.webp` (no se suben a git) |
| Escena y globos de diálogo | `frontend/public/simulacion.html`, `frontend/public/css/simulacion.css` |
| Cambio de personaje según quién habla | `frontend/public/js/simulacion.js` (`setScene`, `patientScene`, `setSpeaker`, `setReady`) |
| Prueba E2E de la escena | `pruebas/29_escena_consulta/probar_escena.cjs` |
| Pruebas de navegador de Rodrigo al día con HU-006 | `pruebas/HU-014/probar_navegador.mjs` (cierre con confirmación, sin calificación), `pruebas/HU-014/servidor_evidencia.py` (voz neuronal apagada), `frontend/tests/docente.mjs` (textos «Panel Doctor») |

## Resultados

| Corrida | Archivo | Resultado |
|---|---|---|
| Antes: producción, con la ilustración fija | `ejecucion/01_antes_produccion` | 0 de 7 (no hay escena por personaje) |
| Después: paciente hombre (CIR-005), escritorio 1440x1000 | `ejecucion/02_despues_hombre_escritorio` | 18 de 18 |
| Después: paciente mujer (CIR-006), escritorio 1440x1000 | `ejecucion/03_despues_mujer_escritorio` | 18 de 18 |
| Después: paciente hombre (CIR-005), celular 390x844 | `ejecucion/04_despues_hombre_celular` | 18 de 18 |
| Regresión Panel Doctor con grupos (HU-014 de Rodrigo) | `ejecucion/05_regresion_hu014_grupos` | 9 de 9 |
| Regresión diálogo directo (TA-017 de Rodrigo), 10 turnos | `ejecucion/06_regresion_ta017_dialogo` | 13 de 13 |
| Regresión panel docente | `ejecucion/07_regresion_panel_docente` | PASA |
| Regresión diagnóstico final (HU-006) | `ejecucion/08_regresion_hu006_diagnostico` | 33 de 33 |
| Regresión reporte final (HU-007) | `ejecucion/09_regresion_hu007_reporte` | 21 de 21 |
| Regresión voz humanizada (TA-019): 6 frases, todas con voz neuronal (antes 8; el doctor ya no repite las 2 preguntas) | `ejecucion/10_regresion_voz` | PASA |
| Regresión completa del backend | `ejecucion/11_regresion_backend` | 825 pasan |

Cada corrida tiene su salida (`.txt`) y la foto real de la terminal (`_terminal.png`). Las capturas de la escena en cada
momento (presentación, interrogatorio, respuesta del paciente, hallazgo del doctor y del laboratorio) y la línea de tiempo
de imagen y globo (`escena_registro.json`) están en `resultados/<corrida>/`.

Las corridas 02 a 11 se hicieron sobre el commit 342ce58 (unión con Rodrigo) más los cambios de la escena, que entran en
el commit siguiente. Las imágenes PNG quedan solo en el equipo.

## Intentos fallidos (se conservan)

| Intento | Qué pasó |
|---|---|
| `intentos/01_antes_sin_elemento_de_escena` | La primera corrida contra producción se detuvo al no encontrar la escena (espera de 30 s) y solo informó «0 de 1». La prueba se cambió para seguir y decir qué falta. |
| `intentos/02_voz_neuronal_en_servidor_de_evidencia` | La regresión de diálogo directo falló en el turno 2. El servidor de evidencia de Rodrigo heredaba `TTS_PROVIDER=edge` del `.env` y la voz sonaba con edge-tts, no con la voz simulada que cuenta la prueba. Se fijó `TTS_PROVIDER` vacío en ese servidor. |
| `intentos/03_panel_docente_con_textos_anteriores` | La prueba del panel docente buscaba «Acceso para docentes» y el enlace «Panel docente». Rodrigo los renombró a «Panel Doctor» y no actualizó la prueba, que ya fallaba en su rama. Se actualizaron los textos. |

## Observación fuera del alcance de esta fase

Hay un comportamiento de los agentes que ya existía antes de la unión: se comprobó con la misma conversación en la versión
anterior y en producción.

- **Pregunta por el inicio del dolor.** A «¿Desde cuándo tiene el dolor?» el paciente de CIR-005 responde a veces
  «No entendí bien, doctor».
- **Exploración física.** A «Realizo exploración física» el doctor pide al estudiante que describa los hallazgos.

Corresponde a la parte de agentes (Rodrigo).

## Cómo repetir

```powershell
npm run build                     # genera las imágenes web y el CSS
# servidor local con la voz activa y sesiones en memoria, en el puerto 3100
$env:BASE_URL='http://localhost:3100'; $env:CASO='CIR-006'; node pruebas\29_escena_consulta\probar_escena.cjs pruebas\29_escena_consulta\resultados\local
# regresiones de Rodrigo: node pruebas\HU-014\sql_server.mjs y backend\.venv\Scripts\python.exe pruebas\HU-014\servidor_evidencia.py
$env:OUT='pruebas/29_escena_consulta/resultados/regresion_hu014_grupos'; node pruebas\HU-014\probar_navegador.mjs
```
