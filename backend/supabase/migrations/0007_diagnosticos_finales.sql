-- HU-006: diagnóstico final de cada consulta, por alumno, caso, sesión e intento.
-- Cómo aplicarlo: Supabase > SQL Editor > New query > pegar este archivo > Run.
-- Debe ejecutarse ANTES de publicar el servidor de HU-006: sin la tabla, el cierre de un alumno con sesión
-- responde 503 y su consulta sigue abierta.
--
-- Solo el servidor la usa, con SUPABASE_SECRET_KEY: RLS activado y ninguna política, como sma_sesiones.
-- No guarda nada de la parte protegida del caso, solo lo que propuso el alumno.

create table if not exists public.diagnosticos_finales (
    id             uuid primary key default gen_random_uuid(),
    session_id     uuid        not null unique references public.sma_sesiones (session_id) on delete cascade,
    usuario_id     uuid        not null references auth.users (id) on delete cascade,
    case_id        text        not null,
    numero_intento integer     not null check (numero_intento >= 1),
    diagnostico    text        not null check (char_length(diagnostico) between 3 and 2000),
    hipotesis      jsonb       not null default '[]'::jsonb check (jsonb_typeof(hipotesis) = 'array'),
    creado_en      timestamptz not null default now(),
    -- Dos consultas distintas del mismo alumno y caso no pueden tener el mismo número de intento.
    unique (usuario_id, case_id, numero_intento)
);

comment on table public.diagnosticos_finales is
    'HU-006: diagnóstico final propuesto por el alumno al cerrar cada consulta. Uno por sesión; solo lo escribe el servidor.';

create index if not exists diagnosticos_finales_alumno_caso_idx
    on public.diagnosticos_finales (usuario_id, case_id, numero_intento desc);

alter table public.diagnosticos_finales enable row level security;
revoke all on public.diagnosticos_finales from anon, authenticated;
