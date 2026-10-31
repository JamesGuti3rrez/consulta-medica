# Intento 3: la voz leía el texto sin signos de puntuación

**Qué se hizo.** Para quitar las pausas de edge-tts, la voz recibía el texto sin signos de puntuación. Solo se
conservaban ¿ ?, por la entonación de pregunta, y el punto de los decimales. El texto en pantalla no cambiaba.
- Medición (`09_sin_puntuacion.py`, `ejecucion/09_sin_puntuacion.txt`): sin signos desaparecen todas las pausas
  mayores de 150 ms. La presentación del caso pasa de 12,6 s a 10,0 s y el laboratorio, de 8,7 s a 6,4 s.
- La prueba de navegador exigía textos sin signos. En rojo: 6 con signos (`ejecucion/10_signos_antes.txt`).
- Cambio en `spokenText()` de `frontend/public/js/simulacion.js` (commit `9159c37`). En verde: 0 con signos
  (`ejecucion/12_signos_despues.txt`).

**Por qué se descartó.** El usuario no quedó conforme con la lectura sin signos (2026-10-30) y pidió volver a
ellos. Sin signos, la voz lee de corrido y no separa las ideas («sexo masculino Motivo de consulta ingresó por
dolor...»). La pausa que sobraba era una sola, la del punto: la medición 09 ya mostraba unos 860 ms en el punto, mientras que la
coma, los dos puntos y el punto y coma pausan entre 240 y 310 ms.

**Cómo se corrige.** La voz vuelve a recibir los signos y solo el punto seguido de más texto se lee como coma
(medición `codigo/17_pausas_cortas.py`, en la carpeta de la fase).

**Lo que sigue valiendo.** Las pruebas del reintento (13 a 16) se corrieron con esta versión sin signos. Lo que
comprueban (el reintento ante un fallo de edge-tts, las peticiones simultáneas, las tres corridas en verde) no
depende de los signos.

**Archivos conservados sin modificar.** `09_sin_puntuacion.py` calcula su carpeta de salida respecto de su
ubicación original (`codigo/`); para repetirlo hay que copiarlo de vuelta a `codigo/`.
