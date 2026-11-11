# 38. Métricas del sistema (TA-024 y resultados de TA-023)

Mide lo que el informe técnico tenía como **[PENDIENTE]**:

| Métrica | Script | Sección del informe |
|---|---|---|
| Latencia por turno, p50, p90, p95 y p99, por agente y por tipo de pregunta | `codigo/01_latencia_turnos.py` | 3.2.2 Rendimiento · 5.x |
| Throughput y tasa de error con 1, 2, 4 y 8 alumnos a la vez | `codigo/02_carga_concurrente.py` | 3.2.2 Escalabilidad |
| Latencia de la voz: primer trozo y audio completo | `codigo/03_latencia_voz.py` | 3.2.2 · 5.x |
| Precisión@k, Recall@k, Hit@k, abstención y RAGAS (TA-023) | `python -m evals` (ya existía) | 5.x Evaluación RAG |
| Lighthouse en móvil y escritorio, y Core Web Vitals | `codigo/04_frontend_lighthouse_axe.mjs` | 3.2.2 Usabilidad · 5.x |
| Accesibilidad WCAG 2.1 AA con axe-core | `codigo/04_frontend_lighthouse_axe.mjs` | 3.2.2 Accesibilidad |
| Usabilidad percibida (SUS) | `codigo/05_sus.py` + `datos/` | 5.x Piloto |
| **Gráficos y tablas de todo lo anterior** | `codigo/graficar.py` | → `graficos/` y `resultados/resumen_metricas.md` |

Cada script guarda sus datos crudos en `resultados/`, y `graficar.py` arma los gráficos con lo que encuentre ahí.

## Comandos (PowerShell, desde la raíz del proyecto)

### 0. Preparar (una sola vez)

```powershell
npm install
npm run setup -- --extras evals,voz,dev
npm install --no-save lighthouse axe-core
npx playwright install chromium
```

En `.env` deben estar las claves de Groq (`GROQ_API_KEYS`) para medir con el modelo real, y `TTS_PROVIDER=edge`
para la voz.

### 1. Levantar el servidor (terminal 1, déjelo abierto)

```powershell
npm start
```

### 2. Mediciones (terminal 2)

Todo se ejecuta **desde la raíz del proyecto**; `$PY` y `$M` usan rutas absolutas y sirven desde cualquier carpeta.

```powershell
$PY = "$PWD\backend\.venv\Scripts\python.exe"; $M = "$PWD\pruebas\38_ta024_metricas\codigo"; $env:PYTHONIOENCODING = "utf-8"

# Latencia por turno: 10 casos × 10 preguntas = 100 turnos por repetición (unos 5–10 min con Groq)
& $PY $M\01_latencia_turnos.py --repeticiones 2

# Throughput con 1, 2, 4 y 8 alumnos simultáneos
& $PY $M\02_carga_concurrente.py --concurrencias 1 2 4 8 --turnos 5

# Voz neuronal: 48 frases
& $PY $M\03_latencia_voz.py

# Frontend: Lighthouse y axe
node $M\04_frontend_lighthouse_axe.mjs
```

### 3. RAG (TA-023), con el recuperador configurado en `.env`

```powershell
cd backend
.\.venv\Scripts\python.exe -m evals --k 3 5 --ragas ids --output ..\pruebas\38_ta024_metricas\resultados\rag\configurado
# Opcional, con juez LLM (faithfulness y answer relevancy; usa Groq y tarda más):
.\.venv\Scripts\python.exe -m evals --k 3 5 --ragas llm --generate-responses --output ..\pruebas\38_ta024_metricas\resultados\rag\con_juez
cd ..
```

La carpeta de `--output` debe estar vacía. Para repetir, bórrela o use otro nombre. `graficar.py` toma la última
corrida, en orden alfabético. Para elegir una, use `--rag <carpeta>`.

### 4. SUS (cuando tengan las encuestas)

1. Pasen el cuestionario de `datos/cuestionario_sus.md` después de una consulta completa (n ≥ 8 ideal).
2. Anoten una fila por participante en `datos/sus_respuestas.csv`.
3. Ejecuten: `& $PY $M\05_sus.py`

### 5. Gráficos y tablas

```powershell
& $PY $M\graficar.py
```

El aviso `fatal: not a git repository` del arnés RAG no es un error: intenta anotar el commit medido. En una copia
sin `.git` (descargada como zip) guarda `git_commit: null` y sigue. Si lo corren en el clon del repositorio, el
commit queda registrado.

Salida: `graficos/G01…G13*.png` y `resultados/resumen_metricas.md`, que trae todas las tablas con los números
para el informe.

### Medir el despliegue de Vercel (opcional)

Agregue `--base-url https://<su-app>.vercel.app --etiqueta vercel` a los scripts 01 a 04. Los archivos se guardan
con el sufijo `_vercel` y se grafican con `& $PY graficar.py --etiqueta vercel`. En Vercel la carga concurrente
consume cuota: use `--concurrencias 1 2 4`.

## Gráficos que se generan

| Archivo | Qué muestra |
|---|---|
| G01_latencia_turno_distribucion | Histograma de la latencia por turno con p50, p90 y p99 |
| G02_latencia_por_agente | Diagrama de caja por agente (paciente, médico asistente, laboratorio...) |
| G03_latencia_por_escenario | Diagrama de caja por tipo de pregunta (ambigua, dato protegido, otro caso...) |
| G04_latencia_secuencia | Cada turno en orden: muestra el arranque en frío y la estabilidad |
| G05_percentiles_por_operacion | p50, p95 y p99 del inicio de consulta, del turno y de la voz |
| G06_carga_concurrente | Throughput, latencia bajo carga y % de error con IC 95 % (Wilson) |
| G07_voz_primer_trozo | Distribución acumulada del tiempo hasta oír la voz |
| G08 / G09_rag_* | Métricas de recuperación globales y por especialidad (k = 3 y 5) |
| G10_lighthouse_puntajes / G11_core_web_vitals | Puntajes y LCP, TBT y CLS frente a los umbrales de «bueno» |
| G12_axe_violaciones | Incumplimientos WCAG por página e impacto |
| G13_sus | Puntaje SUS por participante, la media con IC 95 % y la escala de adjetivos |

## Notas para interpretar

- **Modo local frente a Groq:** si el servidor arranca sin `GROQ_API_KEYS`, el script 01 avisa. En ese caso la
  latencia mide solo la orquestación (unos 50 ms) y no al modelo. Para el informe usen la corrida con Groq. La
  corrida local sirve como línea base del costo propio del sistema.
- **429/503 bajo carga:** con el plan gratuito de Groq son esperables. Son un resultado (límite del proveedor),
  no una falla del script.
- **Lighthouse** es una medición de laboratorio, con red y CPU simuladas en móvil. Conviene repetirla 3 veces y
  reportar la mediana.
- **Hardware:** cada JSON de `resultados/` guarda en `entorno_cliente` el sistema, el procesador y los núcleos del
  equipo que midió. Úsenlo en la sección de entorno experimental.
