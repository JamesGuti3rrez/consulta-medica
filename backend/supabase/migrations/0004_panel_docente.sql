-- Ejecutar en el SQL Editor del proyecto configurado en .env.
-- Requiere 0003 y la tabla rag_evidencias de la integración pgvector existente.
-- No cambia usuarios ni concede permisos docentes automáticamente.
begin;

create table if not exists public.importaciones_casos (
    id uuid primary key default gen_random_uuid(),
    docente_id uuid references auth.users(id) on delete set null,
    archivo text not null,
    case_ids text[] not null,
    casos_insertados integer not null,
    evidencias_indexadas integer not null,
    created_at timestamptz not null default now()
);
alter table public.importaciones_casos enable row level security;
revoke all on public.importaciones_casos from public, anon, authenticated;
grant select, insert on public.importaciones_casos to service_role;

-- Una transacción incorpora documentos y su evidencia; si falla cualquier paso,
-- no se publica un caso incompleto ni se altera el índice existente.
create or replace function public.importar_casos_docente(
    p_casos jsonb, p_evidencias jsonb, p_docente_id uuid, p_archivo text
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_case jsonb;
    v_evidence jsonb;
    v_row public.rag_evidencias%rowtype;
    v_existing jsonb;
    v_ids text[];
    v_inserted integer := 0;
    v_evidence_count integer := 0;
    v_added integer;
    v_audit uuid;
begin
    if jsonb_typeof(p_casos) <> 'array' or jsonb_array_length(p_casos) not between 1 and 100
       or jsonb_typeof(p_evidencias) <> 'array' then
        raise exception 'Lote de casos no válido' using errcode = '22023';
    end if;
    if not exists (
        select 1 from auth.users
        where id = p_docente_id and raw_app_meta_data ->> 'rol' in ('profesor', 'administrativo')
    ) then
        raise exception 'El usuario no tiene permiso docente' using errcode = '42501';
    end if;
    select array_agg(item ->> 'case_id') into v_ids from jsonb_array_elements(p_casos) item;
    if cardinality(v_ids) <> (select count(distinct id) from unnest(v_ids) id) then
        raise exception 'Identificadores repetidos' using errcode = '22023';
    end if;
    -- Serializa importaciones con otros cambios sobre los casos para comprobar identidad.
    lock table public.casos_curados in share row exclusive mode;
    for v_case in select value from jsonb_array_elements(p_casos) loop
        select documento into v_existing from public.casos_curados where case_id = v_case ->> 'case_id';
        if found and v_existing <> v_case then
            raise exception 'Ya existe otro contenido con este identificador' using errcode = '23505';
        end if;
        insert into public.casos_curados(case_id, documento)
        values (v_case ->> 'case_id', v_case)
        on conflict (case_id) do nothing;
        get diagnostics v_added = row_count;
        v_inserted := v_inserted + v_added;
        if not exists (
            select 1 from jsonb_array_elements(p_evidencias) item
            where item ->> 'case_id' = v_case ->> 'case_id'
        ) then
            raise exception 'Faltan evidencias para un caso' using errcode = '22023';
        end if;
    end loop;
    if exists (
        select 1 from jsonb_array_elements(p_evidencias) item
        where not ((item ->> 'case_id') = any(v_ids))
           or coalesce(item ->> 'owner', '') not in ('public', 'paciente', 'medico_asistente', 'laboratorio', 'radiologia', 'especialista')
    ) then
        raise exception 'Evidencia ajena al lote o propietario no autorizado' using errcode = '22023';
    end if;
    -- Solo se sustituyen las evidencias de los casos verificados del lote.
    delete from public.rag_evidencias where case_id = any(v_ids);
    for v_evidence in select value from jsonb_array_elements(p_evidencias) loop
        v_row := jsonb_populate_record(null::public.rag_evidencias, v_evidence);
        insert into public.rag_evidencias(
            case_id, evidence_id, owner, category, requires, content,
            embedding, embedding_model, source_hash
        ) values (
            v_row.case_id, v_row.evidence_id, v_row.owner, v_row.category, v_row.requires,
            v_row.content, v_row.embedding, v_row.embedding_model, v_row.source_hash
        );
        v_evidence_count := v_evidence_count + 1;
    end loop;
    insert into public.importaciones_casos(docente_id, archivo, case_ids, casos_insertados, evidencias_indexadas)
    values (p_docente_id, left(p_archivo, 200), v_ids, v_inserted, v_evidence_count)
    returning id into v_audit;
    return jsonb_build_object('casos_insertados', v_inserted,
        'casos_existentes', cardinality(v_ids) - v_inserted,
        'evidencias_indexadas', v_evidence_count, 'importacion_id', v_audit);
end;
$$;

revoke all on function public.importar_casos_docente(jsonb, jsonb, uuid, text) from public, anon, authenticated;
grant execute on function public.importar_casos_docente(jsonb, jsonb, uuid, text) to service_role;
notify pgrst, 'reload schema';
commit;

