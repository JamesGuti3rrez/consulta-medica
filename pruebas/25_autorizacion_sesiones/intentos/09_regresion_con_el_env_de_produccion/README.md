# Intento 9: la regresión tomó el buscador de Supabase del `.env` nuevo

**Qué pasó.** Regresión completa después de corregir el caso 40 (2026-10-28 06:33 UTC), con
`SESSION_STORE=memoria`, `CASE_STORE=local` y `LANGSMITH_TRACING=false`: **459 pasan y 2 fallan**, ambas en
`tests/integration/test_api_sma.py` (`test_five_agents_in_one_star_session_with_traceable_evidence` y
`test_session_survives_across_instances_with_supabase_store`). En las dos, la primera respuesta no revela la
evidencia `MED-900.anamnesis.inicio_dolor`.

**Causa.** El `.env` se actualizó al proyecto de producción y ahora incluye `RAG_BACKEND` apuntando al buscador
de Supabase y `SYNTHETIC_CASE_DATA=true`. Esas pruebas fijan el almacén de sesiones, pero no el buscador: con el
de Supabase no recuperan el dato del caso de prueba `MED-900`, que solo existe en los fixtures locales. Con
`RAG_BACKEND=local` (el valor por defecto, que es el que había en las regresiones anteriores) las dos pasan. No
es un problema de TA-011.

**Corrección.** La regresión se repitió fijando también `RAG_BACKEND=local` y `SYNTHETIC_CASE_DATA=false`, es
decir, las mismas condiciones de las regresiones anteriores. Que las pruebas dependan del `.env` de quien las
corre queda como hallazgo (D-10 del informe).

Archivos conservados sin modificar: la salida completa y la foto de la terminal (solo en el equipo).
