# Paciente Virtual Adaptativo — benchmark de arquitecturas

Prototipo experimental para comparar cuatro patrones de orquestación con el mismo caso, batería de preguntas, herramientas, prompts y verificador:

- Supervisor central
- Grafo/Estado (LangGraph StateGraph)
- Handoffs
- Supervisor + Handoffs

El objetivo es medir resultados observados y **no forzar** el orden de la matriz teórica del informe.

## Proveedor LLM del experimento

La ejecución real usa **GroqCloud** mediante `GROQ_API_KEY` y, por defecto, el modelo:

```text
openai/gpt-oss-20b
```

Se usa el mismo modelo, temperatura y configuración para las cuatro arquitecturas. Esto es importante para que la variable principal que cambia sea la **orquestación**.

El modo `mock` sigue disponible únicamente para comprobar que el software funciona sin consumir solicitudes de API.

> El Free Plan de Groq tiene límites de solicitudes y tokens. No es ilimitado. El proyecto introduce una pausa mínima entre solicitudes y el SDK reintenta errores transitorios, pero conviene revisar los límites de la cuenta antes del benchmark final.

## Métricas implementadas

- Cobertura de evidencia.
- Evidencia no soportada / entidades potencialmente inventadas.
- Valores y unidades incorrectos.
- Fugas de diagnóstico.
- Exactitud de routing para preguntas con ruta esperada.
- Consistencia de la ruta entre repeticiones.
- Latencia media, P50 y P95.
- Llamadas al LLM por turno.
- Tokens de entrada y salida cuando Groq los reporta.
- Registro crudo por interacción en CSV.

## Importante sobre el modo mock

`mock` es determinista y sirve para probar que el pipeline, las herramientas, el verificador y los archivos de resultados funcionan. **No debe usarse para sacar conclusiones sobre qué arquitectura es mejor.**

## Ejecución recomendada en VS Code / PowerShell

Ejecuta los siguientes pasos desde la carpeta `paciente_virtual_benchmark`.

### 1. Crear el entorno virtual

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación, puedes ejecutar temporalmente:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

### 2. Instalar dependencias

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Ejecutar pruebas automatizadas

```powershell
pytest -q
```

Una ejecución correcta debe terminar sin fallos. Esta captura es útil para el informe porque demuestra que las pruebas unitarias pasan antes del benchmark.

### 4. Validar el dataset progresivo

```powershell
python scripts/validate_dataset.py
```

Esta prueba comprueba la estructura del caso y que el diagnóstico protegido no aparezca en la presentación inicial.

### 5. Ejecutar el benchmark mock

```powershell
python main.py benchmark --provider mock --repeats 3
```

Este paso **solo valida la infraestructura**. No usar sus resultados como evidencia experimental del comportamiento de un LLM.

### 6. Configurar Groq

Copia el archivo de ejemplo:

```powershell
Copy-Item .env.example .env
```

Abre `.env` y reemplaza:

```text
GROQ_API_KEY=tu_api_key_de_groq_aqui
```

por tu clave real.

**No subas `.env` a GitHub y no incluyas la clave en capturas del informe.**

Configuración por defecto:

```text
GROQ_MODEL=openai/gpt-oss-20b
GROQ_TEMPERATURE=0.2
GROQ_REASONING_EFFORT=low
GROQ_MIN_INTERVAL_SECONDS=2.1
```

No cambies estos valores entre arquitecturas durante una comparación.

### 7. Prueba real corta de conectividad

Antes del benchmark completo:

```powershell
python main.py demo --provider groq --architecture stategraph --model openai/gpt-oss-20b
```

Debe devolver un JSON con la arquitectura, ruta, respuesta, evidencia, validación, latencia y uso de tokens.

### 8. Benchmark real inicial

Primero ejecuta una sola repetición para verificar que todo funciona con Groq:

```powershell
python main.py benchmark --provider groq --repeats 1 --model openai/gpt-oss-20b
```

### 9. Benchmark comparativo con repeticiones

Cuando la corrida anterior finalice correctamente:

```powershell
python main.py benchmark --provider groq --repeats 3 --model openai/gpt-oss-20b
```

Esta corrida ya sirve para observar variabilidad entre repeticiones. Si Groq devuelve un error `429`, espera a que el límite se restablezca o aumenta `GROQ_MIN_INTERVAL_SECONDS` en `.env`.

Los resultados se guardan en:

- `results/raw_results.csv`
- `results/summary.csv`

### 10. Generar gráficos

```powershell
python scripts/plot_results.py
```

### 11. Medir el proxy de complejidad

```powershell
python scripts/complexity_proxy.py
```

Este resultado se considera únicamente un **proxy descriptivo de complejidad de implementación**, no una medición directa de facilidad.

## Capturas recomendadas para el informe

Guarda capturas separadas de:

1. `pytest -q` con todas las pruebas aprobadas.
2. `python scripts/validate_dataset.py`.
3. Benchmark `mock`, indicando que es validación de infraestructura.
4. Demo real con Groq sin mostrar la API key.
5. Benchmark real de Groq y su tabla resumen.
6. `results/summary.csv` abierto en VS Code/Excel.
7. Uno o dos fragmentos representativos de `results/raw_results.csv`.
8. Gráficos generados por `scripts/plot_results.py`.
9. Salida de `scripts/complexity_proxy.py`.

Conserva también los CSV originales porque son la evidencia reproducible de cada corrida.

## Google Colab

1. Sube/descomprime el proyecto o clónalo desde GitHub.
2. Instala dependencias:

```python
!pip install -r requirements.txt
```

3. Prueba sin API:

```python
!pytest -q
!python main.py benchmark --provider mock --repeats 3
```

4. Define `GROQ_API_KEY` en **Secrets** de Colab. No escribas la clave directamente en una celda que luego vayas a compartir.

5. Prueba real:

```python
!python main.py demo --provider groq --architecture stategraph --model openai/gpt-oss-20b
```

6. Benchmark:

```python
!python main.py benchmark --provider groq --repeats 3 --model openai/gpt-oss-20b
```

## Diseño de cada arquitectura

### Supervisor
Una llamada LLM decide el especialista; el especialista genera la respuesta. Ruta típica:
`supervisor -> laboratory -> supervisor`.

### StateGraph
El routing crítico es código determinista; LangGraph modela las etapas explícitas. Ruta típica:
`detect_intent -> laboratory -> validator`.

### Handoffs
El médico asistente decide mediante LLM a qué agente transferir el turno. Ruta típica:
`assistant -> laboratory`.

### Supervisor + Handoffs
Hay coordinación global y una segunda decisión de handoff. Ruta típica:
`supervisor -> assistant -> laboratory -> assistant -> supervisor`.

Esta diferencia es intencional: operacionaliza el costo y la variabilidad que el informe atribuye a cada patrón.

## Escalar al protocolo del informe

El repositorio trae **1 microcaso** y una batería pequeña para validar la infraestructura. Para el experimento final:

- agregar 20 casos a `data/cases/`;
- ampliar la batería de fidelidad hasta 30 sondas por caso;
- mantener 10 ataques de fuga por caso;
- utilizar al menos 3 repeticiones cuando los límites de API lo permitan;
- no modificar modelo, temperatura, prompts, herramientas ni verificador entre arquitecturas durante una corrida comparativa.

## Validación adicional

```powershell
python scripts/validate_dataset.py
python scripts/complexity_proxy.py
python scripts/plot_results.py
```

`validate_dataset.py` operacionaliza parte de la Brecha 4. `complexity_proxy.py` solo reporta LOC como **proxy descriptivo**.
