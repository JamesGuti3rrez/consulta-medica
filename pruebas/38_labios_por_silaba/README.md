# 38. Boca por sílaba y leve balanceo de la cabeza (trabajo correctivo de la TA-020)

Corrige los avatares de la TA-020 (fase 37). Los videos en bucle de LivePortrait hacían que la cabeza cambiara de
tamaño en cada pausa de la voz, la boca no seguía lo que se decía y había gestos raros. Ahora la escena apila capas
transparentes sobre la imagen quieta: la cabeza, que se balancea un poco mientras el personaje habla (intensidad 0,4),
y cuatro bocas (pequeña, A, E/I, O/U) que cambian por sílaba según el texto. En silencio se ve la imagen original.

El informe es `Entregables/12_TA-020_Correctivo_boca_por_silaba/` (Word, PDF y video), generado con
`generar_informe.cjs` a partir de los resultados de esta carpeta. Código en el commit `e50a4d5` (rama James, unida a
main y publicada en Vercel).

## Archivos

| Archivo | Qué hace |
|---|---|
| `probar_labios.cjs` | Prueba E2E: recorre una consulta (CIR-005) y toma una muestra de la escena cada 40 ms. Variables: `NAVEGADOR` (chrome, msedge, firefox), `MOVIMIENTO` (normal, reducido), `CAPAS=bloqueadas`, `ANCHO`/`ALTO`. Servidor de prueba en el puerto 3100 con `SESSION_STORE=memoria`. |
| `medir_antes_y_despues.py` | Mide la escala, el giro y el desplazamiento de la cabeza en cada fotograma de los videos de la TA-020 (sacados de git, commit `f9fc8eb`) frente a la imagen quieta, comprueba que las capas nuevas coinciden al píxel con ella y arma las figuras del informe. |
| `ejecutar_en_terminal.py` | Ejecuta un comando en una ventana real de PowerShell («Evidencia consulta-medica <commit>») y guarda su salida (`ejecucion/<nombre>.txt`) y la foto de la ventana (`_terminal.png`). |
| `grabar_video.cjs` | Graba una consulta corta en Chrome y guarda cada audio de la voz neuronal con su hora de inicio, más un destello de sincronía. |
| `montar_video.py` | Monta el video «antes y después» con ffmpeg: ubica cada audio con el destello, agrega rótulos y un acercamiento a la cara. |
| `generar_informe.cjs` | Genera el informe Word con las cifras y capturas de `resultados/` y `ejecucion/`. |
| `prototipos/` | Las bocas de los prototipos v1 y v2 (sacadas del video) y las páginas de los prototipos, para la figura de versiones. |

## Pruebas

| Corrida | Archivo | Resultado |
|---|---|---|
| Medición antes y después | `ejecucion/00_medicion_antes_y_despues` | PASA (antes: cabeza hasta +3,8 %; ahora 0,00 %) |
| Google Chrome | `ejecucion/01_chrome` | 11 de 11 |
| Microsoft Edge | `ejecucion/02_edge` | 11 de 11 |
| Firefox (Playwright) | `ejecucion/03_firefox` | 11 de 11 |
| Chrome con «reducir movimiento» | `ejecucion/04_chrome_reducir_movimiento` | 7 de 7 |
| Chrome en celular (390×844) | `ejecucion/05_chrome_celular` | 11 de 11 |
| Chrome con las capas bloqueadas | `ejecucion/06_chrome_capas_bloqueadas` | 4 de 4 |
| Unitarias de sílabas (`frontend/tests/labios.test.mjs`) | `ejecucion/07_pruebas_unitarias_silabas` | 12 pasan, 0 fallan |
| Regresión TA-020 (fase 37) | `ejecucion/08_regresion_ta020` | 13 de 13 |
| Suite completa del backend | `ejecucion/09_suite_backend` | 898 pasan, 6 saltadas |

Cada corrida E2E deja capturas y `labios_registro.json` en `resultados/<corrida>/`.

## Intentos fallidos (se conservan)

| Intento | Qué pasó |
|---|---|
| `intentos/02_capas_bloqueadas_una_muestra_sin_imagen` | Con las capas bloqueadas, una sola muestra (40 ms) sin la imagen visible al pasar del paciente al doctor (3 de 4). Se vio en 2 de 10 corridas y no se reprodujo en 6 más. La imagen vuelve con un fundido de 250 ms que empieza en opacidad 0; la prueba ahora cuenta los 300 ms tras un cambio como parte del cambio. Queda como observación. |
| `intentos/03_suite_backend_sin_salida` | La foto mostraba 898 pasadas, pero el `.txt` quedó vacío: `Tee-Object` solo recibía la salida de `cd ..`. Se agrupó el comando en un bloque. |
| `intentos/04_medicion_umbral_y_acentos` | La medición exigía que la capa de la cabeza fuera idéntica a la imagen con margen de 2 niveles; la compresión WebP llega a 12 en pocos píxeles (media 1,1). El umbral no estaba medido: ahora se comprueba la escala y el giro, con el mismo método que los videos. Además faltaba `PYTHONIOENCODING=utf-8`. |
| `intentos/01_variable_tramos_fuera_de_alcance` | Al agregar el modo `CAPAS=bloqueadas`, la variable `tramos` quedó dentro de un bloque y las corridas de Chrome, Edge y Firefox terminaron con «tramos is not defined», aunque las 11 comprobaciones del simulador pasaban. Se corrigió la prueba y se repitieron todas las corridas. |

Antes de esta carpeta, durante el desarrollo: en Firefox la cabeza seguía moviéndose 0,06° al terminar el turno
(10 de 11), porque el freno del balanceo dependía de los fotogramas por segundo. Ahora depende del tiempo
(`SWAY_EASE_MS` en `simulacion.js`).

## Cómo repetirlo

```powershell
# Servidor de prueba (no escribe en Supabase)
cd backend; $env:SESSION_STORE='memoria'; .venv\Scripts\python.exe -m uvicorn server.main:app --port 3100
# Pruebas, desde la raíz
python pruebas\38_labios_por_silaba\ejecutar_en_terminal.py 01_chrome "$env:NAVEGADOR='chrome'; node pruebas/38_labios_por_silaba/probar_labios.cjs pruebas/38_labios_por_silaba/resultados/01_chrome"
# Video: versión anterior (commit f9fc8eb) en otro puerto, por ejemplo 3101, y luego
$env:BASE_URL='http://localhost:3101'; node pruebas/38_labios_por_silaba/grabar_video.cjs pruebas/38_labios_por_silaba/resultados/video/antes
$env:BASE_URL='http://localhost:3100'; node pruebas/38_labios_por_silaba/grabar_video.cjs pruebas/38_labios_por_silaba/resultados/video/despues
$env:FFMPEG='<ruta a ffmpeg.exe>'; python pruebas\38_labios_por_silaba\montar_video.py pruebas/38_labios_por_silaba/resultados/video/antes pruebas/38_labios_por_silaba/resultados/video/despues "<salida.mp4>" pruebas/38_labios_por_silaba/resultados/video
# Informe
node pruebas/38_labios_por_silaba/generar_informe.cjs "<salida.docx>"
```
