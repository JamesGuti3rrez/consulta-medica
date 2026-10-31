# Intento 2: la regresión de diálogo directo contó voces que no eran las simuladas

`pruebas/TA-017_Dialogo/probar_navegador.mjs` cuenta las frases leídas por la voz simulada del navegador. El servidor
de evidencia de Rodrigo (`pruebas/HU-014/servidor_evidencia.py`) heredaba `TTS_PROVIDER=edge` del `.env`, así que las
frases sonaban con la voz neuronal (TA-019) y el turno 2 falló («actual 1, expected 2»). No es un fallo del simulador:
el servidor de evidencia ya fijaba el resto de variables, y ahora fija también `TTS_PROVIDER` vacío. La corrida válida
es `ejecucion/06_regresion_ta017_dialogo` (13 de 13).
