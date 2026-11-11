# Informe de ejecución TA-023

Fecha: 2026-11-10T15:01:00.529633-05:00.

Estado: `ok`. Los promedios corresponden únicamente a las consultas completas exportadas.

Perfil: `configured`. Recuperador efectivo: `CaseEvidenceRetriever`.

100 consultas, 10 casos y 5 especialidades. k=[3, 5].

| Especialidad | k | P@k (con referencia) | Recall@k | Hit@k | Abstención | Fallos seguridad |
|---|---:|---:|---:|---:|---:|---:|
| ALL | 3 | 0.4600 | 0.9495 | 1.0000 | 1.0000 | 0 |
| ALL | 5 | 0.3120 | 0.9775 | 1.0000 | 1.0000 | 0 |
| cirugia_general | 3 | 0.4667 | 0.9375 | 1.0000 | 1.0000 | 0 |
| cirugia_general | 5 | 0.3200 | 0.9625 | 1.0000 | 1.0000 | 0 |
| emergencias | 3 | 0.3667 | 1.0000 | 1.0000 | 1.0000 | 0 |
| emergencias | 5 | 0.2200 | 1.0000 | 1.0000 | 1.0000 | 0 |
| ginecologia_obstetricia | 3 | 0.5000 | 0.9750 | 1.0000 | 1.0000 | 0 |
| ginecologia_obstetricia | 5 | 0.3200 | 1.0000 | 1.0000 | 1.0000 | 0 |
| medicina_interna | 3 | 0.5000 | 0.8975 | 1.0000 | 1.0000 | 0 |
| medicina_interna | 5 | 0.3800 | 0.9625 | 1.0000 | 1.0000 | 0 |
| pediatria | 3 | 0.4667 | 0.9375 | 1.0000 | 1.0000 | 0 |
| pediatria | 5 | 0.3200 | 0.9625 | 1.0000 | 1.0000 | 0 |

Errores por consulta a k máximo: `{"missing_expected": 3}`.

Estados RAGAS por IDs: `{"ok": 100, "not_applicable_no_reference": 100}`.

Estados de respuesta RAGAS (una evaluación por consulta, repetida en filas k): `{"disabled": 100}`.

La precisión usa k como denominador; retornar menos de k evidencias reduce P@k aunque todas sean relevantes. Recall y Hit excluyen consultas sin referencia; abstención solo usa esas consultas. summary.csv también incluye P@k de todas las consultas y los tamaños de cada denominador.

Los fallos de seguridad invalidan la corrida aunque los promedios sean altos. Los errores de servicio no se convierten en recuperaciones vacías exitosas ni en ceros de calidad.

Las métricas de respuestas usan el contexto de k máximo y el contexto público inicial. Fidelidad no demuestra corrección médica. Sin juez no se afirma ausencia de alucinaciones. No se generan ni contabilizan hechos sintéticos de agentes.

Los contextos y respuestas permanecen en memoria: las trazas exportan IDs y hashes. La configuración, versiones, hashes del código y dataset están en run.json. El arnés no crea sesiones ni escribe casos o datos en Supabase.

Esta corrida mide el fallback real de JSON: orden de origen y score constante 1. No demuestra calidad de embeddings, LightRAG ni pgvector. Ejecutar el perfil configurado con el índice/servicios del despliegue para medir esas rutas.
