# Fase 4 · Conexión con el frontend

## Objetivo

Cargar varios casos en el simulador y verificar que la pantalla muestra solo datos públicos, sin
revelar el diagnóstico ni otra información protegida.

## Cómo se hizo

Con el servidor en marcha (`npm start`, o `uvicorn server.main:app --port 3100` desde `backend/`):

```powershell
$env:BASE_URL = "http://localhost:3100"
node pruebas\_herramientas\capturar_frontend.cjs pruebas\04_frontend\capturas
```

El script abre `/simulacion.html` en Chromium con una ventana de **1440 × 1100 (escritorio/PC)**, pulsa
**Iniciar simulación demo** / **Cargar otro caso** hasta haber mostrado el primer caso de cada especialidad (EME-001, GOB-003, CIR-005, PED-007 y MED-008) y, en cada uno:

- toma una captura de la ficha cargada;
- confirma que la respuesta de `GET /api/caso` no contiene `protected`, `on_request`, `source` ni `provenance`;
- busca en el texto visible de la página el diagnóstico, los sinónimos, los diferenciales y el tratamiento de referencia del JSON original, y comprueba que no aparecen.

`/api/caso` devuelve un caso al azar; los que no están en la lista se omiten. Así cada ejecución captura los mismos cinco casos con los mismos nombres de archivo; solo cambia el número de intento en el que apareció cada uno.

## Resultado

5 casos cargados, uno por especialidad (EME-001, GOB-003, CIR-005, PED-007, MED-008), con 0 textos protegidos visibles. El detalle está en
[capturas/resultado_frontend.txt](capturas/resultado_frontend.txt).

## Evidencias

- `capturas/01_simulador_catalogo_disponible.png`: estado inicial, «10 casos curados disponibles».
- `capturas/02_ficha_EME-001.png` a `06_ficha_MED-008.png`: ficha de cada caso cargado.
- `capturas/07_respuesta_api_caso.png`: respuesta JSON de `GET /api/caso` tal como llega al navegador.
- [ejecucion/01_capturar_frontend_terminal.png](ejecucion/01_capturar_frontend_terminal.png): foto de la terminal donde se ejecutó la prueba.
- [ejecucion/01_capturar_frontend.png](ejecucion/01_capturar_frontend.png): salida de la prueba generada desde el texto.
- [../../docs/evidence/simulador-caso-curado.png](../../docs/evidence/simulador-caso-curado.png): captura previa del caso PED-010.

## Intentos

| Intento | Resultado | Evidencia |
| --- | --- | --- |
| 1 | Correcto, pero incompleto: 3 y luego 5 casos al azar, con especialidades repetidas (por ejemplo, dos de emergencias) | [intentos/01_sin_regla_por_especialidad/](intentos/01_sin_regla_por_especialidad/) |
| 2 | Correcto, pero no repetible: un caso por especialidad elegido al azar y sin foto de terminal | [intentos/02_casos_al_azar_sin_terminal/](intentos/02_casos_al_azar_sin_terminal/README.md) |
| 3 | Correcto: siempre los mismos cinco casos, con foto real de la terminal | `capturas/` y `ejecucion/` |

En el intento 1 ninguna captura mostró información protegida; se repitió para garantizar que todas
las especialidades quedaran cubiertas. Los números del nombre de archivo corresponden a corridas
distintas, por eso algunos se repiten.

## Límites

La ficha muestra el resumen clínico del enunciado fuente. En algunos casos, ese resumen describe
hallazgos muy característicos (por ejemplo, PED-010); eso es parte del caso, no una fuga del campo
protegido. El diálogo clínico interactivo todavía no está implementado.
