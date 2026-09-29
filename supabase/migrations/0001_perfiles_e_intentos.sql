-- Consulta Médica Virtual: perfiles de alumnos e intentos de consulta.
-- Cómo aplicarlo: Supabase > SQL Editor > New query > pegar este archivo > Run.
--
-- Supabase Auth ya guarda los usuarios (correo, contraseña cifrada, Google) en auth.users.
-- Aquí solo se agregan los datos propios del simulador.

-- ============================================================================
-- Perfiles: un registro por usuario con sus nombres
-- ============================================================================
create table public.perfiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  nombres     text not null default '',
  apellidos   text not null default '',
  universidad text,
  creado_en   timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);

comment on table public.perfiles is 'Datos del alumno. Se crea solo al registrarse (ver crear_perfil_nuevo_usuario).';

-- Al registrarse, se crea el perfil con los datos que envía la página (correo y contraseña)
-- o con el nombre que entrega Google.
create function public.crear_perfil_nuevo_usuario()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.perfiles (id, nombres, apellidos)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'nombres', new.raw_user_meta_data ->> 'given_name',
             split_part(coalesce(new.raw_user_meta_data ->> 'full_name', ''), ' ', 1), ''),
    coalesce(new.raw_user_meta_data ->> 'apellidos', new.raw_user_meta_data ->> 'family_name', '')
  );
  return new;
end;
$$;

create trigger al_crear_usuario
  after insert on auth.users
  for each row execute function public.crear_perfil_nuevo_usuario();

-- ============================================================================
-- Intentos: cada consulta terminada por un alumno con sesión iniciada
-- ============================================================================
create table public.intentos (
  id                uuid primary key default gen_random_uuid(),
  usuario_id        uuid not null references auth.users (id) on delete cascade,
  caso_id           text not null,
  especialidad      text,
  puntaje           smallint not null check (puntaje between 0 and 100),
  diagnostico       text,
  hipotesis         jsonb not null default '[]'::jsonb,
  reporte           jsonb not null default '{}'::jsonb,
  duracion_segundos integer check (duracion_segundos >= 0),
  creado_en         timestamptz not null default now()
);

comment on table public.intentos is 'Resultados de cada consulta. Solo el backend los inserta, para que nadie pueda inventar un puntaje.';

create index intentos_usuario_fecha on public.intentos (usuario_id, creado_en desc);

-- ============================================================================
-- Seguridad por filas (RLS): cada alumno solo ve y edita lo suyo
-- ============================================================================
alter table public.perfiles enable row level security;
alter table public.intentos enable row level security;

create policy "El alumno ve su perfil"
  on public.perfiles for select
  to authenticated
  using ((select auth.uid()) = id);

create policy "El alumno edita su perfil"
  on public.perfiles for update
  to authenticated
  using ((select auth.uid()) = id)
  with check ((select auth.uid()) = id);

create policy "El alumno ve sus intentos"
  on public.intentos for select
  to authenticated
  using ((select auth.uid()) = usuario_id);

-- Sin política de insert para intentos: desde el navegador no se pueden crear.
-- El backend los guarda con la clave secreta, que no pasa por RLS.
