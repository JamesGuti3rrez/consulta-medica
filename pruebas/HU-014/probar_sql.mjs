import assert from 'node:assert/strict';
import { mkdirSync,writeFileSync,readFileSync } from 'node:fs';
import { createDatabase,rpc,IDS } from './sql_fixture.mjs';

const db=await createDatabase();
const results=[];
async function test(name,body){await body();results.push({prueba:name,resultado:'PASA'});console.log('[PASA] '+name);}
const call=(name,body)=>rpc(db,name,body);
const rejects=(body,code)=>assert.rejects(body,e=>e.code===code);
const A=IDS['doctor-a'],B=IDS['doctor-b'],student=IDS['alumno-a'];
let group,assignment,state;
try {
await test('Migración ejecutada dos veces; cuatro tablas con RLS',async()=>{
 const r=await db.query("select count(*)::int n from pg_class where relname in ('doctor_grupos','doctor_grupo_miembros','doctor_asignaciones','doctor_participaciones') and relrowsecurity");assert.equal(r.rows[0].n,4);
});
await test('Un alumno no crea grupos',async()=>{await rejects(()=>call('doctor_crear_grupo',{p_actor:student,p_nombre:'Prohibido',p_descripcion:''}),'42501');});
await test('Doctor crea grupo propio; otro doctor no accede',async()=>{
 group=await call('doctor_crear_grupo',{p_actor:A,p_nombre:'Grupo SQL',p_descripcion:'Prueba'});
 await rejects(()=>call('doctor_detalle_grupo',{p_actor:B,p_grupo:group.id}),'P0002');
 assert.equal((await call('doctor_listar_grupos',{p_actor:B})).length,0);
});
await test('Nombres únicos por doctor en creación y edición; espacios y mayúsculas equivalentes',async()=>{
 const create=(owner,name)=>call('doctor_crear_grupo',{p_actor:owner,p_nombre:name,p_descripcion:''});
 const another=await create(A,'Grupo diferente');
 for(const name of ['grupo sql',' GRUPO   SQL ','Grupo\tSQL','Grupo\u00a0SQL']) {
  await rejects(()=>create(A,name),'23505');
  await rejects(()=>call('doctor_actualizar_grupo',{p_actor:A,p_grupo:another.id,p_nombre:name,p_descripcion:''}),'23505');
 }
 assert.equal((await create(B,'Grupo SQL')).nombre,'Grupo SQL');
 const [x,y]=await Promise.allSettled([create(A,'Grupo concurrente'),create(A,' grupo  CONCURRENTE ')]);
 assert.equal([x,y].filter(r=>r.status==='fulfilled').length,1);
 assert.equal([x,y].find(r=>r.status==='rejected').reason.code,'23505');
});
await test('0006 corrige duplicados existentes sin perder integrantes ni actividades y es idempotente',async()=>{
 const legacy=await createDatabase(undefined,{legacyNames:true});
 try {
  const create=name=>rpc(legacy,'doctor_crear_grupo',{p_actor:A,p_nombre:name,p_descripcion:''});
  const original=await create('Grupo 01'),duplicate=await create(' grupo  01 ');
  await create('Grupo 01 (2)');await create('X'.repeat(100));await create('x'.repeat(100));
  await rpc(legacy,'doctor_gestionar_miembro',{p_actor:A,p_grupo:duplicate.id,p_email:'alumno-a@example.com',p_alumno:null,p_activo:true});
  const [activity]=await rpc(legacy,'doctor_asignar_casos',{p_actor:A,p_grupo:duplicate.id,p_casos:[{case_id:'MED-008',titulo:'Se conserva'}]});
  const migration=readFileSync('backend/supabase/migrations/0006_grupos_nombres_unicos.sql','utf8');
  await legacy.exec(migration);
  const rows=(await legacy.query('select * from public.doctor_grupos order by id')).rows;
  assert.equal(rows.length,5);
  assert.equal(rows.find(g=>g.id===original.id).nombre,'Grupo 01');
  assert.equal(rows.find(g=>g.id===duplicate.id).nombre,'grupo 01 (3)');
  assert.ok(rows.every(g=>g.nombre.length<=100));
  const detail=await rpc(legacy,'doctor_detalle_grupo',{p_actor:A,p_grupo:duplicate.id});
  assert.equal(detail.miembros[0].alumno_id,student);assert.equal(detail.actividades[0].id,activity.id);
  await legacy.exec(migration);
  assert.deepEqual((await legacy.query('select * from public.doctor_grupos order by id')).rows,rows);
 } finally {await legacy.close();}
});
await test('Alumno registrado por correo; alta repetida idempotente',async()=>{
 for(let i=0;i<2;i++)await call('doctor_gestionar_miembro',{p_actor:A,p_grupo:group.id,p_email:'ALUMNO-A@example.com',p_alumno:null,p_activo:true});
 const d=await call('doctor_detalle_grupo',{p_actor:A,p_grupo:group.id});assert.equal(d.miembros.length,1);
 await rejects(()=>call('doctor_gestionar_miembro',{p_actor:A,p_grupo:group.id,p_email:'inexistente@example.com',p_alumno:null,p_activo:true}),'P0002');
});
await test('Asignación por grupo y roster; sin acceso de otro alumno',async()=>{
 [assignment]=await call('doctor_asignar_casos',{p_actor:A,p_grupo:group.id,p_casos:[{case_id:'MED-008',titulo:'Actividad SQL'}]});
 assert.equal((await call('alumno_mis_grupos',{p_actor:student}))[0].actividades[0].id,assignment.id);
 assert.deepEqual(await call('alumno_mis_grupos',{p_actor:IDS['alumno-b']}),[]);
 await rejects(()=>call('alumno_actividad',{p_actor:IDS['alumno-b'],p_asignacion:assignment.id}),'P0002');
});
await test('Lote con caso inexistente revierte todas sus escrituras',async()=>{
 await rejects(()=>call('doctor_asignar_casos',{p_actor:A,p_grupo:group.id,p_casos:[{case_id:'CIR-101',titulo:'Temporal'},{case_id:'MED-999',titulo:'No existe'}]}),'22023');
 assert.equal((await call('doctor_detalle_grupo',{p_actor:A,p_grupo:group.id})).actividades.length,1);
});
await test('Inicio concurrente reutiliza una sesión y un único evento',async()=>{
 state={session_id:crypto.randomUUID(),owner_id:student,access_token_hash:null,case_id:'MED-008',phase:'presentacion',group_assignment_id:assignment.id,
 started_at:'2026-10-30T10:00:00Z',finished_at:null,revealed_evidence_ids:[],student_diagnosis:'NO MOSTRAR ANTES DEL CIERRE'};
 const p={p_actor:student,p_asignacion:assignment.id,p_estado:state};
 const [x,y]=await Promise.all([call('alumno_iniciar_actividad',p),call('alumno_iniciar_actividad',{...p,p_estado:{...state,session_id:crypto.randomUUID()}})]);
 assert.equal(x.session_id,y.session_id); assert.equal(y.reutilizada,true);
 assert.equal((await db.query('select count(*)::int n from public.sma_eventos')).rows[0].n,1);
});
await test('Proyección abierta no revela diagnóstico ni notas',async()=>{
 const d=await call('doctor_detalle_grupo',{p_actor:A,p_grupo:group.id});
 assert.equal(d.participaciones[0].diagnostico,null);assert.equal(d.participaciones[0].calificacion,null);
});
await test('Cierre conserva nota diagnóstica y proceso por separado',async()=>{
 const closed={...state,phase:'finalizada',finished_at:'2026-10-30T10:12:00Z',student_diagnosis:'Respuesta entregada',diagnosis_evaluation:{status:'correct',score:100,reason:'Referencia'},evaluation:{score:80}};
 await db.query("update public.sma_sesiones set phase='finalizada',state=$1 where session_id=$2",[JSON.stringify(closed),state.session_id]);
 const d=await call('doctor_detalle_grupo',{p_actor:A,p_grupo:group.id});
 assert.equal(d.participaciones[0].calificacion.score,100);assert.equal(d.participaciones[0].puntaje_proceso,80);
});
await test('Cerrar actividad bloquea nuevos inicios y conserva entregas',async()=>{
 await call('doctor_cerrar_actividad',{p_actor:A,p_asignacion:assignment.id,p_activa:false});
 const reopened=await call('alumno_iniciar_actividad',{p_actor:student,p_asignacion:assignment.id,p_estado:state});assert.equal(reopened.session_id,state.session_id);
});
await test('Retirar alumno revoca acceso; su resultado permanece',async()=>{
 await call('doctor_gestionar_miembro',{p_actor:A,p_grupo:group.id,p_email:null,p_alumno:student,p_activo:false});
 assert.equal(await call('alumno_acceso_sesion_grupo',{p_actor:student,p_asignacion:assignment.id,p_sesion:state.session_id}),false);
 await rejects(()=>call('alumno_actividad',{p_actor:student,p_asignacion:assignment.id}),'P0002');
 assert.equal((await call('doctor_detalle_grupo',{p_actor:A,p_grupo:group.id})).participaciones.length,1);
});
await test('Claves de navegador sin acceso directo a tablas ni RPC',async()=>{
 for(const role of ['anon','authenticated']) {
  await db.exec('set role '+role);
  try {
   for(const table of ['doctor_grupos','doctor_grupo_miembros','doctor_asignaciones','doctor_participaciones'])await rejects(()=>db.query('select * from public.'+table),'42501');
   await rejects(()=>db.query('select public.doctor_listar_grupos($1)',[A]),'42501');
  } finally {await db.exec('reset role');}
 }
});
mkdirSync('pruebas/HU-014',{recursive:true});writeFileSync('pruebas/HU-014/sql.json',JSON.stringify({motor:'PostgreSQL PGlite, migración SQL real',resultado:'PASA',casos:results},null,2));
console.log(`Resultado: ${results.length}/${results.length} pruebas SQL aprobadas.`);
} finally {await db.close();}
