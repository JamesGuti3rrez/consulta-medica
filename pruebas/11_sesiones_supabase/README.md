# Fase 11 · Sesiones del simulador en Supabase (2026-10-11)

## Problema

En el sitio publicado (https://consulta-medica-three.vercel.app) cada pregunta del estudiante mostraba
«No pude procesar tu pregunta». Los registros de Vercel (`vercel logs --environment production`)
mostraban HTTP 404 en todas las llamadas a `POST /api/ai/sessions/{id}/message`:

```
POST /api/ai/sessions/5af956e6-7820-461c-9d96-31bda9373aa6/message   404
```

La causa: la sesión se guardaba en la memoria del proceso (`InMemorySessionStore`). En Vercel cada
petición puede atenderla una instancia distinta, y las instancias se apagan solas; la sesión creada en
una no existe en otra. En local funcionaba porque hay un solo proceso.

## Solución

Se eligió guardar las sesiones en Supabase, que el proyecto ya usa para el inicio de sesión, porque
deja un registro permanente de cada consulta para la evaluación futura.

| Pieza | Archivo | Commit |
| --- | --- | --- |
| Almacén en Supabase (misma interfaz que el de memoria) | `backend/server/orchestration/supabase_store.py` | `76c6ab3` |
| Tablas `sma_sesiones` y `sma_eventos`, con RLS y sin acceso para el navegador | `supabase/migrations/20261011_sesiones_sma.sql` (desde el 2026-10-12, `backend/supabase/migrations/0002_sesiones_sma.sql`) | `76c6ab3` |
| Elección con `SESSION_STORE` (`memoria` por defecto, `supabase` en Vercel); error 503 si Supabase falla | `backend/server/config.py`, `backend/server/api/ai.py`, `.env.example` | `2df6ce7` |
| 9 pruebas con una imitación de la API de Supabase (sin red) | `backend/tests/unit/test_supabase_store.py`, `backend/tests/integration/test_api_sma.py` | `1bb3d19` |
| Carpeta temporal de la CLI de Supabase fuera del repositorio | `.gitignore` | `34fd32c` |

La sesión guarda el caso, la fase, los datos ya revelados y la conversación. La solución del caso
(`protected`) nunca se guarda en esas tablas.

## Pasos en Supabase

1. El proyecto estaba **pausado** por inactividad (plan gratuito): por eso su dirección no resolvía.
   Se reactivó desde el panel.
2. Las tablas se crearon con la CLI de Supabase (`supabase db query --linked -f
   supabase/migrations/20261011_sesiones_sma.sql`). Comprobación en la base:

   | Tabla | RLS | El navegador (anon) lee | El servidor (service_role) escribe |
   | --- | --- | --- | --- |
   | sma_eventos | sí | no | sí |
   | sma_sesiones | sí | no | sí |

3. La clave secreta del `.env` ya no estaba registrada (HTTP 401 «Unregistered API key»); se puso una
   nueva en el `.env` y en Vercel. Ninguna clave aparece en el repositorio ni en estas evidencias.

## Evidencia

1. **Tablas reales** ([01_almacen_real/probar_supabase.py](01_almacen_real/probar_supabase.py)):
   recorre una consulta de MED-008 creando una instancia nueva del servidor en cada petición, como en
   Vercel. La instancia A crea la consulta, B y C responden preguntas, D ve lo revelado y la cierra, E
   lee los eventos en orden. También comprueba que el navegador no puede leer las sesiones, que una
   sesión inexistente responde 404 y que la fila no guarda la solución. Al final borra la sesión de
   prueba. Resultado: todas las comprobaciones pasan.
   Foto: [01_almacen_real/probar_supabase_terminal.png](01_almacen_real/probar_supabase_terminal.png).
2. **Pruebas automáticas** del almacén y de la API:
   [02_pruebas_automaticas/pytest_almacen_terminal.png](02_pruebas_automaticas/pytest_almacen_terminal.png).
   La suite completa pasa: 121 de 121 (112 antes de este cambio).
3. **Producción:** `GET /api/ai/status` en el sitio publicado responde `"session_store": "supabase"`
   con el modelo de Groq activo.

## Pendiente

- El plan gratuito pausa el proyecto tras unos 7 días sin actividad. Si eso pasa, fallan las consultas
  y el inicio de sesión hasta reactivarlo desde el panel.
