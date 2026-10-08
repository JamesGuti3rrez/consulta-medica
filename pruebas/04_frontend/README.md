# Fase 4 · Conexión con el frontend

## Objetivo

Cargar varios casos en el simulador y verificar que la pantalla muestra solo datos públicos, sin
revelar el diagnóstico ni otra información protegida.

## Cómo se hizo

Con el servidor en marcha (`npm start`, o `uvicorn server.main:app --port 3100` desde `backend/`):

```powershell
$env:BASE_URL = "http://localhost:3100"
node pruebas\_herramientas\capturar_frontend.cjs pruebas\04_frontend\capturas 5
```

El script abre `/simulacion.html` en Chromium con una ventana de **1440 × 1100 (escritorio/PC)**, pulsa
**Iniciar simulación demo** / **Cargar otro caso** hasta reunir un caso de cada una de las 5 especialidades y, en cada uno:

- toma una captura de la ficha cargada;
- confirma que la respuesta de `GET /api/caso` no contiene `protected`, `on_request`, `source` ni `provenance`;
- busca en el texto visible de la página el diagnóstico, los sinónimos, los diferenciales y el tratamiento de referencia del JSON original, y comprueba que no aparecen.

`/api/caso` devuelve un caso al azar: los repetidos o de una especialidad ya vista se omiten, y el registro indica en qué intento apareció cada caso.

## Resultado

5 casos distintos cargados, uno por especialidad, con 0 textos protegidos visibles. El detalle está en
[capturas/resultado_frontend.txt](capturas/resultado_frontend.txt).

## Evidencias

- `capturas/01_simulador_catalogo_disponible.png`: estado inicial, «10 casos curados disponibles».
- `capturas/02_…` a `06_ficha_<ID>.png`: ficha de cada caso cargado (los nombres exactos figuran en `resultado_frontend.txt`).
- `capturas/07_respuesta_api_caso.png`: respuesta JSON de `GET /api/caso` tal como llega al navegador.
- [ejecucion/01_capturar_frontend.png](ejecucion/01_capturar_frontend.png): salida de la prueba.
- [../../docs/evidence/simulador-caso-curado.png](../../docs/evidence/simulador-caso-curado.png): captura previa del caso PED-010.

## Intentos

| Intento | Resultado | Evidencia |
| --- | --- | --- |
| 1 | Correcto, pero incompleto: 3 y luego 5 casos al azar, con especialidades repetidas (por ejemplo, dos de emergencias) | [intentos/01_sin_regla_por_especialidad/](intentos/01_sin_regla_por_especialidad/) |
| 2 | Correcto: un caso por cada una de las 5 especialidades | `capturas/` |

En el intento 1 ninguna captura mostró información protegida; se repitió para garantizar que todas
las especialidades quedaran cubiertas. Los números del nombre de archivo corresponden a corridas
distintas, por eso algunos se repiten.

## Límites

La ficha muestra el resumen clínico del enunciado fuente. En algunos casos, ese resumen describe
hallazgos muy característicos (por ejemplo, PED-010); eso es parte del caso, no una fuga del campo
protegido. El diálogo clínico interactivo todavía no está implementado.
