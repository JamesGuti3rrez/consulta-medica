# 36. SP-006: selección de tecnología para voz natural y avatares

Spike que compara alternativas de voz y de avatar, mide en este equipo las que se pueden probar y documenta la
selección. El informe es `Entregables/10_SP-006_Seleccion_de_voz_y_avatares/` (Word y PDF), generado con
`generar_informe.cjs` a partir de los resultados de esta carpeta.

## Selección

| Parte | Elegida | Respaldo |
|---|---|---|
| Voz | Azure AI Speech F0 (pendiente de la autorización de GitHub Student); hoy, edge-tts como puente | Voz del navegador fija por personaje y, al final, solo texto |
| Avatar | Video en bucle de LivePortrait alternado con la imagen quieta, por volumen (fase 34) | Imagen quieta |

## Pruebas

| Corrida | Archivo | Resultado |
|---|---|---|
| Voz: caracteres por presentación (43 casos), voces de edge-tts, latencia (3 voces × 2 frases × 5) | `ejecucion/01_medir_voz` | Presentación de 242 a 501 caracteres (mediana 292); las 6 voces del simulador disponibles; primer trozo con mediana de 0,95 a 0,99 s y pico de 3,69 s; Azure sin clave (no medible) |
| Navegador: voces, H.264 y carga de los videos en Google Chrome y Chromium de Playwright | `ejecucion/02_navegador` | 2 voces de México (Raúl, Sabina); H.264 en ambos; videos de 334 a 408 KB |
| Respaldo sin video (videos bloqueados) | `ejecucion/03_respaldo_sin_video` | 7 de 7 |
| Respaldo solo texto (sin videos, sin `/api/voz`, sin voz del navegador) | `ejecucion/04_respaldo_solo_texto` | 8 de 8 |

Cada corrida tiene su salida (`.txt`) y la foto real de la terminal (`_terminal.png`); los datos están en `resultados/`.

```
backend/.venv/Scripts/python.exe pruebas/36_sp006_voz_y_avatar/medir_voz.py pruebas/36_sp006_voz_y_avatar/resultados/voz.json
node pruebas/36_sp006_voz_y_avatar/probar_navegador.cjs pruebas/36_sp006_voz_y_avatar/resultados/navegador.json
RESPALDO=sin_video  node pruebas/36_sp006_voz_y_avatar/probar_respaldos.cjs pruebas/36_sp006_voz_y_avatar/resultados/sin_video
RESPALDO=solo_texto node pruebas/36_sp006_voz_y_avatar/probar_respaldos.cjs pruebas/36_sp006_voz_y_avatar/resultados/solo_texto
NODE_PATH=<carpeta con docx@9.5.1> node pruebas/36_sp006_voz_y_avatar/generar_informe.cjs "<salida>.docx"
```

`probar_navegador.cjs` usa el servidor principal (puerto 3000, solo archivos estáticos). Los respaldos usan el servidor de
prueba del puerto 3100 (sesiones en memoria, sin Supabase de producción), como en las fases 34 y 35.

## Corrección a la fase 34

La prueba del navegador mostró que el Chromium de Playwright sí reproduce H.264 en Windows. En la fase 34 se había
escrito lo contrario y que su regresión 03 probaba el respaldo sin video; no era así. Se corrigió ese README y el
respaldo sin video se probó aquí, bloqueando los videos.

## Fuentes externas

Los datos que no se pudieron medir (precios, licencias, Azure) se tomaron de las fuentes F1 a F9 del informe,
consultadas el 4 de noviembre de 2026.
