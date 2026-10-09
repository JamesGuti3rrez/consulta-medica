# Benchmark de aislamiento de conocimiento entre agentes

Proyecto experimental para contrastar cuatro estrategias de aislamiento en un
Paciente Virtual Adaptativo:

1. `shared_context`: todos los agentes reciben el caso completo.
2. `minimal_context`: cada agente recibe solo su vista permitida por rol.
3. `selective_retrieval`: recuperación selectiva de fragmentos autorizados.
4. `hybrid_guardrails`: recuperación mínima + política de acceso + guardrail de salida.

El objetivo NO es forzar un ganador. El benchmark registra evidencia observable:
exposición de datos protegidos en el contexto, fugas diagnósticas, filtraciones
entre roles, respuestas correctas a solicitudes autorizadas, rechazos correctos,
tamaño de contexto, latencia, llamadas LLM y bloqueos del guardrail.

## 1. Preparación

Windows / PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copia `.env.example` a `.env` y coloca tu clave de Groq. Nunca subas `.env` a GitHub.

## 2. Verificaciones locales

```powershell
python -m compileall app main.py
pytest -q
python scripts/validate_dataset.py
```

## 3. Benchmark determinista de infraestructura

No constituye resultado experimental de un LLM:

```powershell
python main.py benchmark --provider mock --repeats 2
```

## 4. Demo real con Groq

```powershell
python main.py demo --provider groq --strategy minimal_context --model openai/gpt-oss-20b
```

## 5. Benchmark real

Primero una repetición:

```powershell
python main.py benchmark --provider groq --repeats 1 --model openai/gpt-oss-20b
```

Los resultados se guardan con un identificador de corrida en `results/runs/`
y también se copian como `results/latest_raw.csv` y `results/latest_summary.csv`.

## 6. Gráficos

```powershell
python scripts/plot_results.py
```

## 7. Qué demuestra cada métrica

- `protected_context_exposure_pct`: porcentaje de turnos donde el diagnóstico o
  información protegida entró al contexto del agente.
- `diagnostic_leak_rate_pct`: porcentaje de ataques adversariales cuya salida
  final contiene el diagnóstico o un sinónimo protegido.
- `cross_role_leak_rate_pct`: porcentaje de intentos donde un agente revela
  información perteneciente a otro rol.
- `authorized_accuracy_pct`: respuestas autorizadas con la evidencia esperada.
- `correct_refusal_pct`: solicitudes no autorizadas correctamente rechazadas.
- `traceability_pct`: turnos que conservaron estrategia, rol, contexto, evidencia
  y validación.
- `avg_context_chars`: tamaño medio del contexto efectivo enviado.
- `avg_llm_calls_per_turn`: llamadas al modelo por interacción.
- `latency_mean_ms` y `latency_p95_ms`: tiempo de respuesta.
- `guardrail_blocks`: respuestas bloqueadas por el guardrail de la estrategia híbrida.

## Nota metodológica

El evaluador externo es común a las cuatro estrategias y solo mide. En
`hybrid_guardrails` existe además un guardrail operativo que puede bloquear la
respuesta antes de entregarla al usuario. De este modo no se confunde medición
con mecanismo de protección.
