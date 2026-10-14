# 21. Cierre del sprint 1

Resumen para la evaluación: qué pedía el sprint, qué se entregó y dónde está la prueba de cada parte. El
detalle de cada fase está en su carpeta de `pruebas/`; aquí solo se enlaza.

## Objetivo del sprint

Según la [decisión 0001](../../docs/decisions/0001-sprint1-decisiones.md): preparar un pipeline que genere
10 casos clínicos a partir de una fuente pública, con validación determinística y trazabilidad, sin que la IA
decida la lógica del caso. Sobre esos casos se integró el simulador completo del equipo.

## Lo entregado, componente por componente

Componentes del diagrama de arquitectura del proyecto (Arquitectura_Paciente_Virtual v1.0):

### Preparación de casos (fuera de línea)

| Componente | Estado | Evidencia |
| --- | --- | --- |
| Adaptador (MedQA) | Fuente oficial con huella SHA-256 verificada | [01](../01_descarga_datasets/README.md), [02](../02_transformacion/README.md) |
| Transformación (IDs y políticas) | 10 casos de MedQA, reproducibles con un comando; cada dato con dueño y regla de revelación | [02](../02_transformacion/README.md), [08](../08_redistribucion_casos/README.md) |
| Quality Gates (esquema y fugas) | Esquema más reglas R01 a R18; R15 exige un dato que descarte cada diferencial | [03](../03_validacion/README.md), [06](../06_correcciones/README.md), [12](../12_familias_sinteticas/README.md), [18](../18_casos_con_un_solo_diagnostico/README.md) |
| Curación | 13 casos curados: 10 de MedQA y 3 sintéticos (familia de dolor torácico). Complementos del equipo con fuente clínica, sin revisión médica (decisión 0002) | [10](../10_mejoras_casos/README.md), [12](../12_familias_sinteticas/README.md), [18](../18_casos_con_un_solo_diagnostico/README.md), [20](../20_sinonimos_diagnostico/README.md) |
| Indexación RAG | Índice LightRAG; si queda desactualizado, los datos autorizados salen del caso | [07](../07_integracion_sma_rag/README.md), [18](../18_casos_con_un_solo_diagnostico/README.md) |

### Servidor (lógica sin IA)

| Componente | Estado | Evidencia |
| --- | --- | --- |
| API REST | `/api` (casos, estado, configuración) y `/api/ai` (sesiones del simulador) | [07](../07_integracion_sma_rag/README.md) |
| Orquestador StateGraph | Topología en estrella con cinco agentes | [07](../07_integracion_sma_rag/README.md) |
| Acceso por rol | Cada agente solo revela los datos de su rol cuando se piden | [07](../07_integracion_sma_rag/README.md), [13](../13_guiones_por_paciente/README.md) |
| Filtro de salida | Bloquea respuestas que nombran el diagnóstico o los diferenciales | [07](../07_integracion_sma_rag/README.md), [13](../13_guiones_por_paciente/README.md) |
| Servicio RAG | Embebido en el servidor; en Vercel, recuperación directa del caso | [07](../07_integracion_sma_rag/README.md) |
| Motor de reglas | Alertas por alergias y contraindicaciones del caso | [14](../14_motor_clinico/README.md), [15](../15_integracion_motor_clinico/README.md) |
| Evaluación | Puntaje por datos clave y omisiones por tipo de error (negligencia, anamnesis, razonamiento) | [14](../14_motor_clinico/README.md), [15](../15_integracion_motor_clinico/README.md) |
| Trazas | Registro por turno | [07](../07_integracion_sma_rag/README.md) |

### Capa de IA

| Componente | Estado | Evidencia |
| --- | --- | --- |
| Agentes por rol | Paciente, médico asistente, laboratorio, radiología y especialista; ninguno ve el diagnóstico | [07](../07_integracion_sma_rag/README.md), [13](../13_guiones_por_paciente/README.md) |
| LLM | Groq con varias claves; sin LLM, el simulador avisa y responde 503 | [09](../09_narracion_simulador/README.md), [13](../13_guiones_por_paciente/README.md) |

### Navegador del estudiante

| Componente | Estado | Evidencia |
| --- | --- | --- |
| Portada | Elige especialidad; inicio de sesión y registro con aviso de privacidad | [09](../09_narracion_simulador/README.md), [19](../19_aviso_privacidad/README.md) |
| Simulación | Ficha del paciente, conversación, hipótesis, alertas de seguridad y «Probar otro caso» | [09](../09_narracion_simulador/README.md), [15](../15_integracion_motor_clinico/README.md), [17](../17_otro_caso/README.md) |
| Reporte | Hoja de evaluación clínica al terminar | [15](../15_integracion_motor_clinico/README.md) |
| Voz | Web Speech API para la narración y el micrófono | [09](../09_narracion_simulador/README.md) |

### Datos y cuentas

| Componente | Estado | Evidencia |
| --- | --- | --- |
| Casos canónicos | 13 casos, cada uno llega a un solo diagnóstico | [18](../18_casos_con_un_solo_diagnostico/README.md) |
| Supabase | Cuentas, sesiones del simulador e historial «Mis simulaciones»; cada alumno solo ve lo suyo | [11](../11_sesiones_supabase/README.md), [16](../16_historial_simulaciones/README.md) |
| Privacidad | Aviso según la Ley 29733, aceptado al crear la cuenta | [19](../19_aviso_privacidad/README.md) |

## Cifras al cierre

| Medida | Valor |
| --- | --- |
| Casos curados | 13 (10 de MedQA y 3 sintéticos), en 5 especialidades |
| Diagnósticos diferenciales con un dato que los descarta | 48 de 48 |
| Formas aceptadas de nombrar el diagnóstico | 52 |
| Pruebas automáticas del backend | 171, todas aprobadas |
| Fases documentadas con evidencia | 21 |
| Sitio publicado | https://consulta-medica-three.vercel.app |

## Cómo comprobarlo

Un solo comando repite el flujo de datos (fases 1 a 4) y las comprobaciones del simulador (fases 14, 15,
17, 18, 19 y 20), sin Groq y sin crear cuentas. Desde la raíz:

```powershell
backend\.venv\Scripts\python.exe pruebas\_herramientas\recorrido_completo.py
```

## Recorrido de cierre

Corrida del 2026-10-14, 11:26 UTC: **14 de 14 comprobaciones sin errores.** Se repitió a las 12:18 UTC, tras renumerar los casos ([fase 23](../23_numeracion_casos/README.md)), con el mismo resultado; los `.txt` de `recorrido/` son de esa última corrida.

| Fase | Comprobación | Resultado |
| --- | --- | --- |
| 1 | Descarga y verificación SHA-256 de MedQA; listado de archivos y huellas | OK |
| 2 | Extracción, conversión y curación de los 10 casos; `data/cases/` idéntico a lo versionado | OK |
| 3 | Esquema, lote curado y vista pública; pruebas automáticas del backend | OK |
| 14 | Motor clínico con los 13 casos (API, roles, alertas y evaluación) | OK |
| 18 | Cada caso llega a un solo diagnóstico (modo local) | OK |
| 20 | Sinónimos del diagnóstico por caso | OK |
| 4 | Un caso por especialidad en el simulador, sin información protegida | OK |
| 15 | Hoja de evaluación y alerta de seguridad en el navegador | OK |
| 17 | Probar otro caso y cerrar el simulador | OK |
| 19 | Aviso de privacidad y aceptación al crear cuenta | OK |

Evidencia: `recorrido/00_recorrido_completo_terminal.png` (foto real de la terminal),
`recorrido/01_*.txt` a `06_*.txt`, `recorrido/capturas/` y `../05_recorrido_completo/resumen_recorrido.txt`. Las
fases 1 a 4 regeneraron su `.txt` en su propia carpeta. Las fotos (`.png`) se guardan en el equipo y no se
suben a GitHub.

## Intento fallido

La primera corrida (`intentos/01_captura_frontend_desactualizada/`) pasó las fases 1 a 3, 14, 18 y 20, pero
falló en la fase 4. El script de captura del frontend pulsaba «Iniciar simulación» varias veces en la misma
página para recorrer especialidades. El recorrido se corrió por última vez el 9 de octubre a las 07:12, y la
presentación narrada (fase 9) llegó ese mismo día a las 23:33. Desde entonces el botón queda ocupado y luego
se oculta tras el primer caso, así que el script esperaba un segundo caso que nunca llegaba.

Corrección:

- `8622fa2`: el script abre cada caso de nuevo con `?caso=` y recarga la página para cada carga por
  especialidad.
- `af6b94d`: las capturas del navegador se guardan dentro de `pruebas/` (en la segunda corrida quedaron en la
  raíz y se movieron a `recorrido/capturas/`).

En esa primera corrida, la salida también traía decenas de avisos «LangSmith rate limit», del servicio de
trazas configurado en el `.env`. No afectaban el resultado; el recorrido ahora corre sin trazas a LangSmith.

## Lo que queda para el sprint 2

- Calificar el diagnóstico escrito: los sinónimos ya están (fase 20); falta compararlos en la evaluación.
- Más casos por especialidad: hoy la mayoría tiene 2, por eso «Probar otro caso» alterna entre los mismos.
- Avatar animado según el estado de la consulta.
- Complicaciones en el motor de reglas (hoy solo alergias y contraindicaciones).
- Que `/message` y `/events` comprueben al dueño de la consulta, como ya lo hace el guardado del historial.
