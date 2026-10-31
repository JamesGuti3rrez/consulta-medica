// PostgreSQL real en WASM para ejecutar la migración; identidades exclusivamente sintéticas de prueba.
import { PGlite } from '@electric-sql/pglite';
import { readFileSync } from 'node:fs';
export const IDS = {
  'doctor-a': '10000000-0000-4000-8000-000000000001', 'doctor-b': '10000000-0000-4000-8000-000000000002',
  admin: '10000000-0000-4000-8000-000000000003', 'alumno-a': '10000000-0000-4000-8000-000000000011',
  'alumno-b': '10000000-0000-4000-8000-000000000012', 'alumno-c': '10000000-0000-4000-8000-000000000013',
};
export async function createDatabase(location, { legacyNames = false } = {}) {
  const db = new PGlite(location);
  await db.exec(`create schema auth; create role anon; create role authenticated; create role service_role bypassrls;
    create table auth.users(id uuid primary key,email text unique,raw_app_meta_data jsonb not null default '{}',raw_user_meta_data jsonb not null default '{}');
    create table public.casos_curados(case_id text primary key,documento jsonb not null);`);
  await db.exec(readFileSync('backend/supabase/migrations/0002_sesiones_sma.sql','utf8'));
  const migration = readFileSync('backend/supabase/migrations/0005_grupos_doctor.sql','utf8');
  await db.exec(migration);
  await db.exec(migration); // Se puede volver a ejecutar sin borrar información.
  if (!legacyNames) {
    const uniqueNames = readFileSync('backend/supabase/migrations/0006_grupos_nombres_unicos.sql','utf8');
    await db.exec(uniqueNames);
    await db.exec(uniqueNames);
  }
  // HU-006: el cierre de un alumno con sesión registra su diagnóstico en diagnosticos_finales.
  await db.exec(readFileSync('backend/supabase/migrations/0007_diagnosticos_finales.sql','utf8'));
  for (const [token,id] of Object.entries(IDS)) {
    const role = token.startsWith('doctor') ? 'profesor' : token === 'admin' ? 'administrativo' : 'alumno';
    await db.query('insert into auth.users values($1,$2,$3,$4)',[id,token+'@example.com',JSON.stringify({rol:role}),JSON.stringify({nombres:token.replace('-',' '),apellidos:'Prueba'})]);
  }
  for (const id of ['MED-008','CIR-101','CIR-005']) {
    const document = JSON.parse(readFileSync('data/cases/curated/'+id+'.json','utf8'));
    await db.query('insert into public.casos_curados values($1,$2)',[id,JSON.stringify(document)]);
  }
  return db;
}
export const FUNCTIONS = {
  doctor_crear_grupo:['p_actor','p_nombre','p_descripcion'], doctor_listar_grupos:['p_actor'],
  doctor_actualizar_grupo:['p_actor','p_grupo','p_nombre','p_descripcion'],
  doctor_detalle_grupo:['p_actor','p_grupo'], doctor_gestionar_miembro:['p_actor','p_grupo','p_email','p_alumno','p_activo'],
  doctor_asignar_casos:['p_actor','p_grupo','p_casos'], doctor_cerrar_actividad:['p_actor','p_asignacion','p_activa'],
  alumno_mis_grupos:['p_actor'], alumno_actividad:['p_actor','p_asignacion'],
  alumno_iniciar_actividad:['p_actor','p_asignacion','p_estado'],
  alumno_acceso_sesion_grupo:['p_actor','p_asignacion','p_sesion'],
};
export async function rpc(db,name,payload) {
  const args=FUNCTIONS[name]; if(!args) throw Error('RPC no permitida');
  const values=args.map(k => typeof payload[k] === 'object' && payload[k] !== null ? JSON.stringify(payload[k]) : payload[k]);
  const result=await db.query(`select public.${name}(${args.map((_,i)=>'$'+(i+1)).join(',')}) as result`,values);
  return result.rows[0].result;
}
