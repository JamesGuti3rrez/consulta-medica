# Prueba del motor clínico con los casos curados

Este recorrido usa todos los JSON de `data/cases/curated/`, sin fijar la cantidad de casos ni la distribución por especialidad. Comprueba el acceso por rol y la evidencia que revela la API de sesiones, verifica las alertas para tratamientos contraindicados cuando el caso los define, y registra la evaluación y la conservación de signos vitales.

El repositorio acepta únicamente casos con estado `curado`; el ejecutor conserva ese control y no cambia el comportamiento del servidor.

Ejecutar desde `backend/` en Windows:

```powershell
.\.venv\Scripts\python.exe ..\pruebas\14_motor_clinico\probar_casos_curated.py
```

El script invoca la misma aplicación FastAPI mediante `TestClient` y usa intencionalmente el proveedor local determinístico para evitar costos, cuotas o resultados variables de un LLM. El resultado detallado se guarda en `pruebas/14_motor_clinico/resultados/resultados_casos_curados.json`.

La prueba local verifica routing, autorización, recuperación, evaluación y reglas determinísticas; no mide calidad de redacción ni requiere una clave Groq ni conexión externa.

## Visualizar resultados

Después de generar los JSON de resultados, crea un informe HTML con tablas para los casos curados, validados y la corrida clínica anterior. Desde `backend/`:

```powershell
.\.venv\Scripts\python.exe ..\pruebas\14_motor_clinico\visualizar_resultados.py
```

El HTML se guarda en `pruebas/14_motor_clinico/resultados/visualizacion_resultados_clinicos.html`; ábrelo con el navegador. Incluye un resumen por especialidad y una tabla por cada JSON disponible en `resultados/`. Si falta algún archivo de resultados, el informe indica cuál prueba debe ejecutarse. Puedes elegir otro destino con `--output ruta\informe.html`.
