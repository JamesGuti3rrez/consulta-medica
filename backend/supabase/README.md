# backend/supabase/

Base de datos transaccional del sistema (Supabase / PostgreSQL).

- `migrations/`: migraciones SQL numeradas y en orden (`NNNN_descripcion.sql`). `0001_perfiles_e_intentos.sql` se conserva sin cambios.
- Uso actual según la documentación: cuentas de usuario. La tabla de intentos existe pero aún no se escribe.
- Pendiente de decisión: si el índice vectorial del RAG vivirá aquí (pgvector, sugerido por el docente) o en otro almacén. Si se adopta, entrará como una migración nueva, no editando la 0001.
- Datos personales de estudiantes: requieren aviso de privacidad y consentimiento (Ley 29733).
- Qué NO va aquí: casos clínicos ni datos de prueba como semillas.
