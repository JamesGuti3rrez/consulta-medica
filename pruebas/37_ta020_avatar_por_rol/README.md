# 37. TA-020: avatar conversacional por rol (reactivado)

Cierra la tarea de los avatares (fase 34) contra sus criterios de aceptación. El informe es
`Entregables/11_TA-020_Avatar_conversacional_por_rol/` (Word y PDF), generado con `generar_informe.cjs` a partir de los
resultados de esta carpeta y de las fases 34 a 36.

## Criterios y qué se hizo

| Criterio | Qué se hizo |
|---|---|
| Avatar o indicador de personaje activo para cada rol habilitado | Avatar del doctor y del paciente (hombre o mujer). Corrección de esta fase: el globo de la escena decía siempre «Doctor» aunque hablara el laboratorio, radiología o el especialista; ahora nombra al rol y cambia su ícono, y el estado dice «Laboratorio hablando», etc. (`setSpeaker`, `doctor-name`, `doctor-icon`). |
| Sincronización básica visual o estado de habla; explicitar si no hay lip-sync | Video mientras suena la voz, imagen en los silencios (por volumen, fase 34); estado «Hablando», «Listo», «Tu turno». No hay lip-sync, y el informe lo dice. |
| Pruebas en navegadores definidos y degradación accesible | Chrome, Edge, Firefox y WebKit (motor de Safari), celular. Correcciones de esta fase: con «reducir movimiento» no se muestra el video (`setTalking`); el chat es `role="log"` y el estado `role="status"`, ambos con `aria-live="polite"`. Sin video y solo texto, fase 36. |

## Pruebas

`probar_ta020.cjs` recorre una consulta (CIR-005) con un turno de cada rol: presentación del doctor, pregunta al
paciente, exploración física (doctor), hemograma (laboratorio), radiografía (radiología) e interconsulta (especialista).
Toma una muestra cada 40 ms y comprueba el indicador de cada rol, la imagen mostrada, el texto alternativo, el estado de
habla, el video y las regiones para lectores de pantalla. Servidor de prueba del puerto 3100 como en las fases 34 a 36.

| Corrida | Archivo | Resultado |
|---|---|---|
| Google Chrome | `ejecucion/01_chrome` | 13 de 13 |
| Microsoft Edge | `ejecucion/02_edge` | 13 de 13 |
| Firefox (Playwright) | `ejecucion/03_firefox` | 13 de 13 |
| WebKit (Playwright, motor de Safari) | `ejecucion/04_webkit` | 13 de 13 |
| Chrome con «reducir movimiento» | `ejecucion/05_chrome_reducir_movimiento` | 13 de 13 |
| Chrome en celular (390×844) | `ejecucion/06_chrome_celular` | 13 de 13 |
| Regresión escena (fase 29) | `ejecucion/07_regresion_escena_29` | 18 de 18 |
| Regresión voz constante (fase 35, escenario A) | `ejecucion/08_regresion_voz_constante` | 7 de 7 |

Cada corrida tiene su salida (`.txt`), la foto real de la terminal (`_terminal.png`), capturas de cada turno y
`ta020_registro.json` en `resultados/<corrida>/`.

## Intentos fallidos (se conservan)

| Intento | Qué pasó |
|---|---|
| `intentos/01_alt_durante_el_cambio` | El texto alternativo se midió durante los 180 ms del cambio de personaje y no coincidía. La prueba lo mide fuera del cambio. |
| `intentos/02_firefox_current_time_en_cero` | Firefox mostró 480 ms de video «sin audio» al empezar. El registro muestra que el audio ya sonaba (`paused=false`, datos cargados) pero Firefox deja `currentTime` en 0 al principio. La prueba ahora considera sonando un audio en reproducción con datos. |
| `intentos/03_escena_29_esperaba_doctor_hablando` | La prueba de la fase 29 esperaba «Doctor hablando» cuando habla el laboratorio; ahora el estado dice «Laboratorio hablando», como pide el criterio. Se actualizó esa prueba. |
| `intentos/04_capturas_antes_de_la_respuesta` | Las seis primeras corridas pasaron, pero sus capturas de los turnos se tomaban a 1,2 s fijos: salían sin globo y una justo durante el cambio de imagen. Ahora la captura espera a que hable el rol, y se agregó la comprobación de la imagen mostrada. |
| `intentos/05_firefox_mostraba_la_imagen_anterior` | Con la comprobación nueva, Firefox falló (12 de 13): al pasar del doctor al paciente se veía un instante al doctor, porque Firefox mantiene la imagen anterior hasta decodificar la nueva. Error real del simulador: `setScene` ahora quita el fundido solo cuando la nueva imagen está decodificada (`img.decode()`). Se repitieron las seis corridas y la regresión de la escena. |
