# 35. Voz constante: cada personaje conserva su voz toda la consulta

## Problema

Entre un diálogo y otro, a veces el doctor cambiaba de voz. La voz neuronal (`/api/voz`, edge-tts) tenía un respaldo
**frase por frase**: si una frase fallaba o no empezaba a sonar en 4 s, solo esa frase sonaba con la voz del navegador
y la siguiente volvía a la neuronal. Además, la voz del navegador no estaba fija: era la predeterminada.

El límite de 4 s cortaba frases que solo eran lentas. Medido en el servidor, el primer trozo de audio de una frase
larga tarda entre 1,1 y 3,4 s (5 mediciones), y el navegador necesita algo más antes de empezar a sonar. En una corrida
de prueba previa la primera frase del doctor salió con la voz del navegador sin que fallara nada.

## Corrección (`frontend/public/js/simulacion.js`, `speak`)

- **La primera frase de la consulta decide la voz** (`consultationVoice`, que se reinicia en cada consulta).
- **Si la voz neuronal ya sonó, se queda hasta el final.** Una frase que falla se vuelve a pedir enseguida, hasta 3 veces
  (con `&intento=N` para que el navegador no reutilice la respuesta fallida). Si se agotan, la frase se muestra sin voz:
  nunca con otra voz.
- **Una frase lenta no es un fallo:** el límite pasa de 4 s a 12 s y solo corta una petición colgada. Los fallos reales
  llegan antes: el servidor reintenta edge-tts y responde 502.
- **Si la voz neuronal falla desde la primera frase,** toda la consulta usa la voz del navegador y no se vuelve a pedir la
  neuronal.
- **La voz del navegador es fija por personaje:** la primera vez se le asigna una voz en español distinta de las ya
  asignadas (en este equipo, doctor «Microsoft Raul» y paciente «Microsoft Sabina») y la conserva.

Las voces neuronales siguen siendo las de TA-019: el doctor y el paciente siempre reciben la misma voz para el mismo caso
(se elige por el sexo del paciente, que no cambia durante la consulta).

## Cómo se probó

`probar_voz_constante.cjs` (Google Chrome, servidor de prueba en el puerto 3100 como en la fase 34) fuerza fallos de red
en `/api/voz` con Playwright y registra qué voz suena en cada frase:

- **Escenario A:** la voz neuronal suena; la 2.ª frase falla al primer intento y la 3.ª en todos.
- **Escenario B:** la voz neuronal falla desde la primera frase.

## Resultados

| Corrida | Archivo | Resultado |
|---|---|---|
| Antes (código de HEAD), escenario A | `ejecucion/01_antes_escenario_a` | 4 de 7: el doctor empieza con la voz neuronal, pasa a la del navegador en las frases 2 y 3 y vuelve a la neuronal |
| Después, escenario A | `ejecucion/02_despues_escenario_a` | 7 de 7: la 2.ª frase suena neuronal al reintentar, la 3.ª sin voz, el navegador nunca |
| Después, escenario B | `ejecucion/03_despues_escenario_b` | 8 de 8: todo con el navegador, una voz por personaje |
| Regresión avatares, paciente hombre (fase 34) | `ejecucion/04_regresion_avatares_hombre` | 16 de 16 |
| Regresión avatares, paciente mujer (fase 34) | `ejecucion/05_regresion_avatares_mujer` | 16 de 16 |
| Regresión escena (fase 29) | `ejecucion/06_regresion_escena_29` | 18 de 18 |

Cada corrida tiene su salida (`.txt`), la foto real de la terminal (`_terminal.png`) y `voz_registro.json` con las
frases, las peticiones y las voces que sonaron (`resultados/<corrida>/`).

## Intentos fallidos (se conservan)

| Intento | Qué pasó |
|---|---|
| `intentos/01_reintento_cortaba_frases_lentas` | Primera versión de la corrección con un límite de 5 s por intento. La voz ya no cambiaba (escenario B 8 de 8), pero en el escenario A la 2.ª frase sonó recién en el 3.er intento: el 2.º llegó bien del servidor y se cortó por lento. Se midió la latencia (1,1 a 3,4 s hasta el primer trozo) y se separó el fallo real (reintento inmediato) de la lentitud (límite de 12 s). |
