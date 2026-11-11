# TA-024 · Resumen de métricas (local)

Generado 2026-11-10T15:10:58-05:00 por graficar.py.

## Latencia por turno (http://localhost:3000)

Fecha 2026-11-10T14:37:33-05:00. LLM `local-development`, recuperación `deterministic-case-fallback`, sesiones `memoria`. Turnos OK 200 de 200; errores ninguno.

| Medición (ms) | n | Media | DE | p50 | p90 | p95 | p99 | Máx. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Inicio de consulta | 20 | 13 | 3 | 13 | 16 | 17 | 19 | 19 |
| Turno (todos) | 200 | 45 | 10 | 44 | 59 | 62 | 66 | 69 |
| Turno (sin el primero, en caliente) | 199 | 45 | 10 | 44 | 59 | 62 | 66 | 69 |
| Turno · Laboratorio | 14 | 52 | 6 | 54 | 60 | 61 | 61 | 61 |
| Turno · Médico asistente | 100 | 41 | 9 | 39 | 53 | 58 | 65 | 66 |
| Turno · Paciente | 80 | 48 | 10 | 46 | 61 | 62 | 66 | 69 |
| Turno · Radiología | 6 | 39 | 5 | 37 | 45 | 46 | 46 | 46 |

## Carga concurrente (throughput)

| Alumnos simultáneos | Turnos OK / enviados | Duración (s) | Turnos/min | p50 (ms) | p95 (ms) | Error % [IC95] | Status |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 5/5 | 0.52 | 578.84 | 44 | 45 | 0.0 [0.0–43.4] | {"200": 5} |
| 2 | 10/10 | 0.79 | 756.62 | 102 | 110 | 0.0 [0.0–27.8] | {"200": 10} |
| 4 | 20/20 | 1.17 | 1029.54 | 174 | 205 | 0.0 [0.0–16.1] | {"200": 20} |
| 8 | 40/40 | 2.18 | 1098.9 | 359 | 445 | 0.0 [0.0–8.8] | {"200": 40} |

## Recuperación de evidencia (RAG, TA-023)

Corrida `configurado`, recuperador `CaseEvidenceRetriever`, estado `ok`, 100 consultas.

| Especialidad | k | Consultas | P@k (con ref.) | Recall@k | Hit@k | Abstención | Fallos seguridad | RAGAS ctx P | RAGAS ctx R | Faithfulness | Relevancy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | 3 | 100 | 0.460 | 0.950 | 1.000 | 1.000 | 0 | 1.000 | 0.950 | N/A | N/A |
| ALL | 5 | 100 | 0.312 | 0.978 | 1.000 | 1.000 | 0 | 1.000 | 0.978 | N/A | N/A |
| cirugia_general | 3 | 20 | 0.467 | 0.938 | 1.000 | 1.000 | 0 | 1.000 | 0.938 | N/A | N/A |
| cirugia_general | 5 | 20 | 0.320 | 0.963 | 1.000 | 1.000 | 0 | 1.000 | 0.963 | N/A | N/A |
| emergencias | 3 | 20 | 0.367 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 | N/A | N/A |
| emergencias | 5 | 20 | 0.220 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 | N/A | N/A |
| ginecologia_obstetricia | 3 | 20 | 0.500 | 0.975 | 1.000 | 1.000 | 0 | 1.000 | 0.975 | N/A | N/A |
| ginecologia_obstetricia | 5 | 20 | 0.320 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 | N/A | N/A |
| medicina_interna | 3 | 20 | 0.500 | 0.897 | 1.000 | 1.000 | 0 | 1.000 | 0.897 | N/A | N/A |
| medicina_interna | 5 | 20 | 0.380 | 0.963 | 1.000 | 1.000 | 0 | 1.000 | 0.963 | N/A | N/A |
| pediatria | 3 | 20 | 0.467 | 0.938 | 1.000 | 1.000 | 0 | 1.000 | 0.938 | N/A | N/A |
| pediatria | 5 | 20 | 0.320 | 0.963 | 1.000 | 1.000 | 0 | 1.000 | 0.963 | N/A | N/A |

Hit@3 global = 1.000 (n = 50; IC 95 % Wilson 0.929–1.000).  
Hit@5 global = 1.000 (n = 50; IC 95 % Wilson 0.929–1.000).  

## Frontend: Lighthouse

| Página | Modo | Rend. | Acces. | B. prácticas | SEO | FCP (ms) | LCP (ms) | TBT (ms) | CLS | Peso (KB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| portada | movil | 74 | 96 | 100 | 100 | 1637 | 8966 | 0 | 0 | 1474 |
| portada | escritorio | 92 | 96 | 100 | 100 | 547 | 1712 | 0 | 0.002 | 1498 |
| simulacion | movil | 74 | 100 | 100 | 100 | 1640 | 9188 | 0 | 0 | 1536 |
| simulacion | escritorio | 92 | 100 | 100 | 100 | 539 | 1761 | 0 | 0.003 | 1553 |
| docente | movil | 97 | 100 | 100 | 54 | 1640 | 1640 | 0 | 0 | 346 |
| docente | escritorio | 100 | 100 | 100 | 54 | 543 | 543 | 0 | 0 | 346 |
| grupos | movil | 100 | 100 | 100 | 54 | 1212 | 1212 | 0 | 0 | 270 |
| grupos | escritorio | 99 | 100 | 100 | 54 | 293 | 293 | 0 | 0.001 | 270 |
| privacidad | movil | 100 | 100 | 100 | 100 | 1487 | 1487 | 0 | 0 | 29 |
| privacidad | escritorio | 100 | 100 | 100 | 100 | 516 | 516 | 0 | 0 | 29 |

## Frontend: accesibilidad (axe-core, WCAG 2.1 AA)

| Página | Modo | Reglas violadas | Reglas superadas | Crítico | Grave | Moderado | Menor | Reglas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| portada | movil | 1 | 22 | 0 | 1 | 0 | 0 | color-contrast |
| portada | escritorio | 1 | 22 | 0 | 1 | 0 | 0 | color-contrast |
| simulacion | movil | 0 | 23 | 0 | 0 | 0 | 0 | — |
| simulacion | escritorio | 0 | 23 | 0 | 0 | 0 | 0 | — |
| docente | movil | 0 | 18 | 0 | 0 | 0 | 0 | — |
| docente | escritorio | 1 | 18 | 0 | 1 | 0 | 0 | label-content-name-mismatch |
| grupos | movil | 0 | 12 | 0 | 0 | 0 | 0 | — |
| grupos | escritorio | 0 | 12 | 0 | 0 | 0 | 0 | — |
| privacidad | movil | 0 | 12 | 0 | 0 | 0 | 0 | — |
| privacidad | escritorio | 0 | 12 | 0 | 0 | 0 | 0 | — |

## Gráficos

- `graficos/G01_latencia_turno_distribucion.png`
- `graficos/G02_latencia_por_agente.png`
- `graficos/G03_latencia_por_escenario.png`
- `graficos/G04_latencia_secuencia.png`
- `graficos/G05_percentiles_por_operacion.png`
- `graficos/G06_carga_concurrente.png`
- `graficos/G08_rag_metricas_globales.png`
- `graficos/G09_rag_por_especialidad.png`
- `graficos/G10_lighthouse_puntajes.png`
- `graficos/G11_core_web_vitals.png`
- `graficos/G12_axe_violaciones.png`
