# backend/supabase/

Base de datos transaccional del sistema (Supabase / PostgreSQL).

- `migrations/`: migraciones SQL numeradas y en orden (`NNNN_descripcion.sql`). `0001_perfiles_e_intentos.sql` se conserva sin cambios; `0002_sesiones_sma.sql` crea las sesiones y los eventos del simulador (`SESSION_STORE=supabase`).
- Uso actual: cuentas de usuario (`perfiles`), sesiones del simulador (`sma_sesiones`, `sma_eventos`) e intentos.
  `intentos` guarda cada consulta que termina un alumno con la sesión iniciada; solo el servidor la escribe
  (`server/persistence/attempts.py`) y el navegador solo lee los del propio alumno («Mis simulaciones»).
  Evidencia: `pruebas/16_historial_simulaciones/`.
- Pendiente de decisión: si el índice vectorial del RAG vivirá aquí (pgvector, sugerido por el docente) o en otro almacén. Si se adopta, entrará como una migración nueva, no editando la 0001.
- Datos personales de estudiantes: requieren aviso de privacidad y consentimiento (Ley 29733). El aviso está en
  `frontend/public/privacidad.html` y se acepta al crear la cuenta (`privacidad_version` y
  `privacidad_aceptada_en` en los datos del usuario). Evidencia: `pruebas/19_aviso_privacidad/`.
- Qué NO va aquí: casos clínicos ni datos de prueba como semillas.
