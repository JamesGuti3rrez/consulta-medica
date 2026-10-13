-- Sesiones del simulador (SMA) y sus eventos.
-- Se ejecuta una vez en Supabase > SQL Editor. Solo el servidor las usa, con SUPABASE_SECRET_KEY:
-- tienen RLS activado y ninguna política, así que el navegador (clave publicable) no puede leerlas.

create table if not exists public.sma_sesiones (
    session_id uuid primary key,
    case_id    text        not null,
    phase      text        not null,
    state      jsonb       not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.sma_eventos (
    id         bigint generated always as identity primary key,
    session_id uuid        not null references public.sma_sesiones (session_id) on delete cascade,
    payload    jsonb       not null,
    created_at timestamptz not null default now()
);

create index if not exists sma_eventos_sesion_idx on public.sma_eventos (session_id, id);
create index if not exists sma_sesiones_caso_idx on public.sma_sesiones (case_id, created_at);

alter table public.sma_sesiones enable row level security;
alter table public.sma_eventos enable row level security;

revoke all on public.sma_sesiones from anon, authenticated;
revoke all on public.sma_eventos from anon, authenticated;
