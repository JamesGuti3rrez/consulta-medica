-- HU-014: nombres únicos por doctor, también con solicitudes simultáneas.
-- Ejecutar completo DESPUÉS de 0005. No borra grupos, alumnos ni resultados.
-- Conserva el nombre del grupo más antiguo; añade (2), (3), etc. a duplicados.
begin;
lock table public.doctor_grupos in share row exclusive mode;

create or replace function public.doctor_normalizar_nombre(p_nombre text) returns text
language sql immutable strict set search_path = '' as $$
  select btrim(regexp_replace(replace(p_nombre,chr(160),' '),'[[:space:]]+',' ','g'));
$$;

do $$
declare g record; base text; candidate text; suffix text; n integer;
begin
  for g in
    select * from (
      select id,doctor_id,nombre,row_number() over (
        partition by doctor_id,lower(coalesce(nullif(public.doctor_normalizar_nombre(nombre),''),'Grupo sin nombre'))
        order by creado_en,id) as position
      from public.doctor_grupos
    ) ranked where position > 1 order by doctor_id,nombre,position
  loop
    base := coalesce(nullif(public.doctor_normalizar_nombre(g.nombre),''),'Grupo sin nombre');
    n := 2;
    loop
      suffix := ' (' || n || ')';
      candidate := left(base,100-length(suffix)) || suffix;
      exit when not exists (
        select 1 from public.doctor_grupos other where other.doctor_id=g.doctor_id and other.id<>g.id
        and lower(coalesce(nullif(public.doctor_normalizar_nombre(other.nombre),''),'Grupo sin nombre'))=lower(candidate)
      );
      n := n+1;
    end loop;
    update public.doctor_grupos set nombre=candidate where id=g.id;
    raise notice 'Grupo %: "%" -> "%"',g.id,g.nombre,candidate;
  end loop;
  update public.doctor_grupos
    set nombre=coalesce(nullif(public.doctor_normalizar_nombre(nombre),''),'Grupo sin nombre')
    where nombre is distinct from coalesce(nullif(public.doctor_normalizar_nombre(nombre),''),'Grupo sin nombre');
end $$;

create or replace function public.doctor_limpiar_nombre_grupo() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  new.nombre := public.doctor_normalizar_nombre(new.nombre);
  return new;
end $$;
drop trigger if exists doctor_grupos_limpiar_nombre on public.doctor_grupos;
create trigger doctor_grupos_limpiar_nombre before insert or update of nombre on public.doctor_grupos
for each row execute function public.doctor_limpiar_nombre_grupo();

create unique index if not exists doctor_grupos_nombre_unico
  on public.doctor_grupos(doctor_id,lower(public.doctor_normalizar_nombre(nombre)));

revoke all on function public.doctor_normalizar_nombre(text),public.doctor_limpiar_nombre_grupo() from public,anon,authenticated;
grant execute on function public.doctor_normalizar_nombre(text),public.doctor_limpiar_nombre_grupo() to service_role;
commit;

-- Comprobación: ya no debe haber nombres repetidos por doctor.
select doctor_id,nombre,count(*) over(partition by doctor_id,lower(public.doctor_normalizar_nombre(nombre))) as coincidencias
from public.doctor_grupos order by doctor_id,creado_en,nombre;
