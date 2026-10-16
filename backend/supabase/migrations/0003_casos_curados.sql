-- Ejecutar en el SQL Editor del NUEVO proyecto de Supabase.
-- No requiere las migraciones de perfiles ni de sesiones.
-- Los documentos completos contienen informacion protegida: solo accede el backend.
begin;

create table public.casos_curados (
    case_id text primary key,
    documento jsonb not null,
    title text generated always as (documento ->> 'title') stored,
    specialty text generated always as (documento ->> 'specialty') stored,
    schema_version text generated always as (documento ->> 'schema_version') stored,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint caso_id_valido check (case_id ~ '^[A-Z]{3,5}-[0-9]{3}$'),
    constraint documento_objeto check (jsonb_typeof(documento) = 'object'),
    constraint documento_campos check (
        documento ?& array['schema_version', 'case_id', 'title', 'specialty',
            'language', 'status', 'source', 'public', 'on_request', 'protected', 'provenance']
    ),
    constraint documento_identidad check (
        jsonb_typeof(documento -> 'case_id') = 'string'
        and (documento ->> 'case_id') = case_id
    ),
    constraint documento_curado check (
        jsonb_typeof(documento -> 'status') = 'string'
        and (documento ->> 'status') = 'curado'
    ),
    constraint documento_titulo check (
        jsonb_typeof(documento -> 'title') = 'string'
        and char_length(documento ->> 'title') between 5 and 80
    ),
    constraint documento_version check (
        jsonb_typeof(documento -> 'schema_version') = 'string'
        and (documento ->> 'schema_version') ~ '^1\.[0-9]+\.[0-9]+$'
    ),
    constraint documento_especialidad check (
        jsonb_typeof(documento -> 'specialty') = 'string'
        and (documento ->> 'specialty') in (
            'medicina_interna', 'pediatria', 'ginecologia_obstetricia',
            'cirugia_general', 'emergencias'
        )
    ),
    constraint documento_idioma check (
        jsonb_typeof(documento -> 'language') = 'string'
        and (documento ->> 'language') = 'es'
    ),
    constraint documento_secciones check (
        jsonb_typeof(documento -> 'source') = 'object'
        and jsonb_typeof(documento -> 'public') = 'object'
        and jsonb_typeof(documento -> 'on_request') = 'array'
        and jsonb_typeof(documento -> 'protected') = 'object'
        and jsonb_typeof(documento -> 'provenance') = 'object'
    )
);

comment on table public.casos_curados is
    'Fuente de casos curados. Documento original completo; incluye public, on_request y protected. Solo backend.';
comment on column public.casos_curados.documento is
    'JSON canonico sin mezclar datos sinteticos. El importador debe validar ademas schemas/caso.schema.json y las reglas cruzadas.';

create index casos_curados_especialidad_idx on public.casos_curados (specialty);

-- Un dato adicional por tema y caso; no se guarda toda la conversacion en una columna.
create table public.caso_datos_adicionales (
    id uuid primary key default gen_random_uuid(),
    case_id text not null references public.casos_curados (case_id) on delete restrict,
    clave text not null,
    pregunta_origen text not null,
    contenido jsonb not null,
    estado_revision text not null default 'pendiente'
        check (estado_revision in ('pendiente', 'aprobado', 'rechazado')),
    modelo text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint dato_clave_valida check (clave ~ '^[a-z][a-z0-9_]{0,127}$'),
    constraint dato_pregunta_valida check (char_length(btrim(pregunta_origen)) > 0),
    constraint dato_modelo_valido check (char_length(btrim(modelo)) > 0),
    constraint dato_contenido_valido check (
        jsonb_typeof(contenido) = 'object'
        and contenido ? 'respuesta'
        and jsonb_typeof(contenido -> 'respuesta') = 'string'
        and char_length(btrim(contenido ->> 'respuesta')) > 0
    ),
    constraint dato_unico_por_caso unique (case_id, clave)
);

comment on table public.caso_datos_adicionales is
    'Datos sinteticos compartidos del caso, separados del contenido curado. Pendiente no equivale a validado por un docente.';
comment on column public.caso_datos_adicionales.clave is
    'Tema normalizado, por ejemplo vasos_agua_diarios. Evita duplicados concurrentes del mismo tema; no hace busqueda semantica.';
comment on column public.caso_datos_adicionales.contenido is
    'Contenido adicional generado: objeto JSON con respuesta obligatoria y otros metadatos. No modifica el documento curado.';

create function public.actualizar_fecha_contenido_caso()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger casos_curados_actualizar_fecha
before update on public.casos_curados
for each row execute function public.actualizar_fecha_contenido_caso();

create trigger caso_datos_adicionales_actualizar_fecha
before update on public.caso_datos_adicionales
for each row execute function public.actualizar_fecha_contenido_caso();

alter table public.casos_curados enable row level security;
alter table public.caso_datos_adicionales enable row level security;

revoke all on public.casos_curados from public, anon, authenticated;
revoke all on public.caso_datos_adicionales from public, anon, authenticated;
revoke all on function public.actualizar_fecha_contenido_caso() from public, anon, authenticated;
grant select, insert, update, delete on public.casos_curados to service_role;
grant select, insert, update, delete on public.caso_datos_adicionales to service_role;

notify pgrst, 'reload schema';
commit;
