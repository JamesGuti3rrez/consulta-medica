-- HU-014: Panel Doctor, grupos, asignaciones y seguimiento.
-- Ejecutar completo en SQL Editor de Supabase. Requiere 0002 y 0003; no depende de perfiles/intentos.
-- Las tablas y RPC se usan solo desde el backend con service_role; cada RPC valida el actor verificado.
begin;

create table if not exists public.doctor_grupos (
  id uuid primary key default gen_random_uuid(),
  doctor_id uuid not null references auth.users(id) on delete cascade,
  nombre text not null check (length(btrim(nombre)) between 1 and 100),
  descripcion text not null default '' check (length(descripcion) <= 1000),
  creado_en timestamptz not null default now()
);
create index if not exists doctor_grupos_propietario on public.doctor_grupos(doctor_id, creado_en);

create table if not exists public.doctor_grupo_miembros (
  grupo_id uuid not null references public.doctor_grupos(id) on delete cascade,
  alumno_id uuid not null references auth.users(id) on delete cascade,
  activo boolean not null default true,
  incorporado_en timestamptz not null default now(),
  primary key(grupo_id, alumno_id)
);
create index if not exists doctor_miembros_alumno on public.doctor_grupo_miembros(alumno_id, grupo_id);

create table if not exists public.doctor_asignaciones (
  id uuid primary key default gen_random_uuid(),
  grupo_id uuid not null references public.doctor_grupos(id) on delete cascade,
  case_id text not null references public.casos_curados(case_id),
  titulo text not null check(length(btrim(titulo)) between 1 and 150),
  activa boolean not null default true,
  creado_en timestamptz not null default now(),
  unique(id, grupo_id)
);
create index if not exists doctor_asignaciones_grupo on public.doctor_asignaciones(grupo_id, creado_en);

create table if not exists public.doctor_participaciones (
  asignacion_id uuid not null,
  grupo_id uuid not null,
  alumno_id uuid not null,
  session_id uuid unique references public.sma_sesiones(session_id) on delete set null,
  creado_en timestamptz not null default now(),
  primary key(asignacion_id, alumno_id),
  foreign key(asignacion_id, grupo_id) references public.doctor_asignaciones(id, grupo_id) on delete cascade,
  foreign key(grupo_id, alumno_id) references public.doctor_grupo_miembros(grupo_id, alumno_id) on delete cascade
);

alter table public.doctor_grupos enable row level security;
alter table public.doctor_grupo_miembros enable row level security;
alter table public.doctor_asignaciones enable row level security;
alter table public.doctor_participaciones enable row level security;
revoke all on public.doctor_grupos, public.doctor_grupo_miembros, public.doctor_asignaciones, public.doctor_participaciones from public, anon, authenticated;
grant all on public.doctor_grupos, public.doctor_grupo_miembros, public.doctor_asignaciones, public.doctor_participaciones to service_role;

create or replace function public.doctor_exigir_rol(p_actor uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not exists(select 1 from auth.users u where u.id=p_actor and u.raw_app_meta_data->>'rol' in ('profesor','administrativo')) then
    raise exception using errcode='42501', message='rol_no_permitido';
  end if;
end $$;

create or replace function public.doctor_exigir_grupo(p_actor uuid,p_grupo uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform public.doctor_exigir_rol(p_actor);
  if not exists(select 1 from public.doctor_grupos g where g.id=p_grupo and g.doctor_id=p_actor) then
    raise exception using errcode='P0002',message='grupo_no_encontrado';
  end if;
end $$;

create or replace function public.doctor_crear_grupo(p_actor uuid,p_nombre text,p_descripcion text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare result public.doctor_grupos;
begin
  perform public.doctor_exigir_rol(p_actor);
  insert into public.doctor_grupos(doctor_id,nombre,descripcion) values(p_actor,btrim(p_nombre),btrim(p_descripcion)) returning * into result;
  return to_jsonb(result);
end $$;

create or replace function public.doctor_listar_grupos(p_actor uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  perform public.doctor_exigir_rol(p_actor);
  return coalesce((select jsonb_agg(t order by t.creado_en desc) from (
    select g.*, (select count(*) from public.doctor_grupo_miembros m where m.grupo_id=g.id and m.activo) alumnos,
      (select count(*) from public.doctor_asignaciones a where a.grupo_id=g.id) actividades
    from public.doctor_grupos g where g.doctor_id=p_actor) t),'[]'::jsonb);
end $$;

create or replace function public.doctor_actualizar_grupo(p_actor uuid,p_grupo uuid,p_nombre text,p_descripcion text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare result public.doctor_grupos;
begin
  perform public.doctor_exigir_grupo(p_actor,p_grupo);
  update public.doctor_grupos set nombre=btrim(p_nombre),descripcion=btrim(p_descripcion) where id=p_grupo returning * into result;
  return to_jsonb(result);
end $$;

create or replace function public.doctor_gestionar_miembro(p_actor uuid,p_grupo uuid,p_email text,p_alumno uuid,p_activo boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare student uuid;
begin
  perform public.doctor_exigir_grupo(p_actor,p_grupo);
  -- Mismo bloqueo que crear/asignar/iniciar: roster e inicio son atómicos respecto al grupo.
  perform 1 from public.doctor_grupos where id=p_grupo for update;
  if p_activo then
    select u.id into student from auth.users u where lower(u.email)=lower(btrim(p_email))
      and coalesce(u.raw_app_meta_data->>'rol','alumno') not in ('profesor','administrativo') limit 1;
    if student is null then raise exception using errcode='P0002',message='alumno_registrado_no_encontrado'; end if;
    insert into public.doctor_grupo_miembros(grupo_id,alumno_id,activo) values(p_grupo,student,true)
      on conflict(grupo_id,alumno_id) do update set activo=true;
    insert into public.doctor_participaciones(asignacion_id,grupo_id,alumno_id)
      select a.id,p_grupo,student from public.doctor_asignaciones a where a.grupo_id=p_grupo and a.activa
      on conflict do nothing;
  else
    student:=p_alumno;
    update public.doctor_grupo_miembros set activo=false where grupo_id=p_grupo and alumno_id=student;
    if not found then raise exception using errcode='P0002',message='miembro_no_encontrado'; end if;
  end if;
  return jsonb_build_object('alumno_id',student,'activo',p_activo);
end $$;

create or replace function public.doctor_asignar_casos(p_actor uuid,p_grupo uuid,p_casos jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare item jsonb; assignment public.doctor_asignaciones; result jsonb:='[]'::jsonb;
begin
  perform public.doctor_exigir_grupo(p_actor,p_grupo);
  perform 1 from public.doctor_grupos where id=p_grupo for update;
  if jsonb_typeof(p_casos)<>'array' or jsonb_array_length(p_casos) not between 1 and 20 then
    raise exception using errcode='22023',message='lote_invalido';
  end if;
  for item in select * from jsonb_array_elements(p_casos) loop
    if not exists(select 1 from public.casos_curados c where c.case_id=item->>'case_id' and c.documento->>'status'='curado') then
      raise exception using errcode='22023',message='caso_no_disponible';
    end if;
    insert into public.doctor_asignaciones(grupo_id,case_id,titulo) values(p_grupo,item->>'case_id',item->>'titulo') returning * into assignment;
    insert into public.doctor_participaciones(asignacion_id,grupo_id,alumno_id)
      select assignment.id,p_grupo,m.alumno_id from public.doctor_grupo_miembros m where m.grupo_id=p_grupo and m.activo;
    result:=result||jsonb_build_array(to_jsonb(assignment));
  end loop;
  return result;
end $$;

create or replace function public.doctor_cerrar_actividad(p_actor uuid,p_asignacion uuid,p_activa boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare assignment public.doctor_asignaciones;
begin
  select * into assignment from public.doctor_asignaciones where id=p_asignacion;
  if not found then raise exception using errcode='P0002',message='actividad_no_encontrada'; end if;
  perform public.doctor_exigir_grupo(p_actor,assignment.grupo_id);
  perform 1 from public.doctor_grupos where id=assignment.grupo_id for update;
  update public.doctor_asignaciones set activa=p_activa where id=p_asignacion returning * into assignment;
  return to_jsonb(assignment);
end $$;

create or replace function public.doctor_detalle_grupo(p_actor uuid,p_grupo uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  perform public.doctor_exigir_grupo(p_actor,p_grupo);
  return jsonb_build_object(
    'grupo',(select to_jsonb(g) from public.doctor_grupos g where g.id=p_grupo),
    'miembros',coalesce((select jsonb_agg(jsonb_build_object('alumno_id',m.alumno_id,'activo',m.activo,
      'email',u.email,'nombre',btrim(concat(u.raw_user_meta_data->>'nombres',' ',u.raw_user_meta_data->>'apellidos')),
      'incorporado_en',m.incorporado_en) order by lower(u.email))
      from public.doctor_grupo_miembros m join auth.users u on u.id=m.alumno_id where m.grupo_id=p_grupo),'[]'::jsonb),
    'actividades',coalesce((select jsonb_agg(to_jsonb(a) order by a.creado_en desc) from public.doctor_asignaciones a where a.grupo_id=p_grupo),'[]'::jsonb),
    'participaciones',coalesce((select jsonb_agg(jsonb_build_object('asignacion_id',p.asignacion_id,'alumno_id',p.alumno_id,
      'session_id',p.session_id,'phase',s.phase,'iniciado_en',s.state->>'started_at',
      'finalizado_en',case when s.phase='finalizada' then s.state->>'finished_at' else null end,
      'diagnostico',case when s.phase='finalizada' and s.state->>'finished_at' is not null then s.state->>'student_diagnosis' else null end,
      'calificacion',case when s.phase='finalizada' and s.state->>'finished_at' is not null then s.state->'diagnosis_evaluation' else null end,
      'puntaje_proceso',case when s.phase='finalizada' and s.state->>'finished_at' is not null then s.state->'evaluation'->'score' else null end))
      from public.doctor_participaciones p left join public.sma_sesiones s on s.session_id=p.session_id where p.grupo_id=p_grupo),'[]'::jsonb));
end $$;

create or replace function public.alumno_mis_grupos(p_actor uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  return coalesce((select jsonb_agg(jsonb_build_object('grupo_id',g.id,'nombre',g.nombre,'descripcion',g.descripcion,
    'actividades',coalesce((select jsonb_agg(jsonb_build_object('id',a.id,'titulo',a.titulo,'activa',a.activa,
      'session_id',p.session_id,'estado',case when s.phase='finalizada' then 'finalizada' when p.session_id is not null then 'en_curso' else 'sin_iniciar' end)
      order by a.creado_en desc) from public.doctor_participaciones p join public.doctor_asignaciones a on a.id=p.asignacion_id
      left join public.sma_sesiones s on s.session_id=p.session_id
      where p.grupo_id=g.id and p.alumno_id=p_actor and (a.activa or p.session_id is not null)),'[]'::jsonb)) order by g.creado_en desc)
    from public.doctor_grupos g join public.doctor_grupo_miembros m on m.grupo_id=g.id
    where m.alumno_id=p_actor and m.activo),'[]'::jsonb);
end $$;

create or replace function public.alumno_actividad(p_actor uuid,p_asignacion uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare result jsonb;
begin
  select jsonb_build_object('id',a.id,'grupo_id',g.id,'grupo',g.nombre,'case_id',a.case_id,'titulo',a.titulo,
    'activa',a.activa,'session_id',p.session_id) into result
    from public.doctor_asignaciones a join public.doctor_grupos g on g.id=a.grupo_id
    join public.doctor_grupo_miembros m on m.grupo_id=g.id and m.alumno_id=p_actor and m.activo
    join public.doctor_participaciones p on p.asignacion_id=a.id and p.alumno_id=p_actor
    where a.id=p_asignacion and (a.activa or p.session_id is not null);
  if result is null then raise exception using errcode='P0002',message='actividad_no_encontrada'; end if;
  return result;
end $$;

create or replace function public.alumno_iniciar_actividad(p_actor uuid,p_asignacion uuid,p_estado jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare activity jsonb; sid uuid; gid uuid;
begin
  select grupo_id into gid from public.doctor_asignaciones where id=p_asignacion;
  if gid is null then raise exception using errcode='P0002',message='actividad_no_encontrada'; end if;
  perform 1 from public.doctor_grupos where id=gid for update;
  activity:=public.alumno_actividad(p_actor,p_asignacion);
  sid:=(activity->>'session_id')::uuid;
  if sid is not null then return jsonb_build_object('session_id',sid,'reutilizada',true); end if;
  if not (activity->>'activa')::boolean then raise exception using errcode='22023',message='actividad_cerrada'; end if;
  if p_estado->>'owner_id' is distinct from p_actor::text or p_estado->>'case_id' is distinct from activity->>'case_id'
    or p_estado->>'phase' is distinct from 'presentacion' or p_estado->>'group_assignment_id' is distinct from p_asignacion::text
    or p_estado->>'finished_at' is not null or p_estado->'access_token_hash' is distinct from 'null'::jsonb then
    raise exception using errcode='22023',message='estado_inicial_invalido';
  end if;
  sid:=(p_estado->>'session_id')::uuid;
  insert into public.sma_sesiones(session_id,case_id,phase,state) values(sid,activity->>'case_id','presentacion',p_estado);
  insert into public.sma_eventos(session_id,payload) values(sid,jsonb_build_object('type','session_started','case_id',activity->>'case_id',
    'phase','presentacion','evidence_ids',p_estado->'revealed_evidence_ids','group_assignment_id',p_asignacion));
  update public.doctor_participaciones set session_id=sid where asignacion_id=p_asignacion and alumno_id=p_actor;
  return jsonb_build_object('session_id',sid,'reutilizada',false);
end $$;

create or replace function public.alumno_acceso_sesion_grupo(p_actor uuid,p_asignacion uuid,p_sesion uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists(select 1 from public.doctor_participaciones p join public.doctor_grupo_miembros m
    on m.grupo_id=p.grupo_id and m.alumno_id=p.alumno_id
    where p.asignacion_id=p_asignacion and p.alumno_id=p_actor and p.session_id=p_sesion and m.activo);
$$;

-- No RPC queda ejecutable desde claves de navegador. Su actor siempre lo fija el backend tras verificar Auth.
do $$ declare f record; begin
  for f in select p.oid::regprocedure signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public' and p.proname in ('doctor_exigir_rol','doctor_exigir_grupo','doctor_crear_grupo',
      'doctor_listar_grupos','doctor_actualizar_grupo','doctor_gestionar_miembro','doctor_asignar_casos',
      'doctor_cerrar_actividad','doctor_detalle_grupo','alumno_mis_grupos','alumno_actividad',
      'alumno_iniciar_actividad','alumno_acceso_sesion_grupo')
  loop
    execute format('revoke all on function %s from public, anon, authenticated',f.signature);
    execute format('grant execute on function %s to service_role',f.signature);
  end loop;
end $$;
commit;
