// API FastAPI y PostgreSQL locales reales; identidad y dispositivos de voz controlados.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdirSync,writeFileSync } from 'node:fs';
import { IDS } from '../HU-014/sql_fixture.mjs';
const base='http://127.0.0.1:3037',out='pruebas/TA-017_Dialogo',results=[],errors=[];
mkdirSync(out+'/capturas',{recursive:true});
const record=prueba=>{results.push({prueba,resultado:'PASA'});console.log('[PASA] '+prueba);};
const request=async(path,body)=>{
 const r=await fetch(base+'/api/grupos'+path,{method:'POST',headers:{Authorization:'Bearer doctor-a','Content-Type':'application/json'},body:JSON.stringify(body)});
 assert.ok(r.ok,'Preparación HTTP '+r.status);return r.json();
};
const browser=await chromium.launch({headless:true,channel:'msedge'});
try {
 assert.equal((await fetch('http://127.0.0.1:3039/__clear_groups',{method:'POST'})).status,200);
 const group=await request('/doctor',{nombre:'Diálogo directo · prueba local'});
 await request('/doctor/'+group.id+'/miembros',{email:'alumno-a@example.com'});
 const assigned=await request('/doctor/'+group.id+'/actividades',{casos:[{case_id:'MED-008',titulo:'Entrevista y exploración'}]});
 const aid=assigned.actividades[0].id;
 const ctx=await browser.newContext({viewport:{width:1480,height:1100},colorScheme:'light'});
 await ctx.route('https://fonts.googleapis.com/**',r=>r.fulfill({contentType:'text/css',body:''}));
 await ctx.route('**/js/auth.js',r=>r.fulfill({contentType:'text/javascript',body:`
 const user={id:${JSON.stringify(IDS['alumno-a'])},email:'alumno-a@example.com'},session={access_token:'alumno-a',user};
 window.auth={ready:Promise.resolve({auth:{getSession:async()=>({data:{session}}),onAuthStateChange(){}}}),historyEnabled:Promise.resolve(false),displayName:u=>u.email,
 api:async(path,options={})=>{const r=await fetch(path,{...options,headers:{...options.headers,Authorization:'Bearer alumno-a'}});if(!r.ok)throw Error('HTTP '+r.status);return r;},
 profile:async()=>(await window.auth.api('/api/docente/sesion')).json()};`}));
 await ctx.addInitScript(()=>{
  window.__spoken=[];
  Object.defineProperty(window,'speechSynthesis',{value:{cancel(){},speak(u){window.__spoken.push(u.text);setTimeout(()=>u.onend?.(),1)}}});
  Object.defineProperty(window,'SpeechSynthesisUtterance',{value:class{constructor(text){this.text=text}}});
  window.SpeechRecognition=class{start(){this.onstart?.();setTimeout(()=>{const item=[{transcript:window.__question}];item.isFinal=true;this.onresult?.({resultIndex:0,results:[item]});this.onend?.();},10)}stop(){}abort(){}};
 });
 const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/simulacion.html?actividad='+aid);await page.locator('[data-role="start-simulation"]').click();
 await page.locator('[data-role="diagnosis-button"]').waitFor({state:'visible'});
 assert.ok((await page.locator('.chat-name strong').allTextContents()).includes('Doctor'));
 record('El doctor presenta el caso al inicio');
 const questions=[
  ['¿Desde cuándo tiene la molestia?','paciente','Paciente'],
  ['¿Tiene alergias?','paciente','Paciente'],
  ['¿Qué medicamentos toma?','paciente','Paciente'],
  ['Realizo exploración física','medico_asistente','Doctor'],
  ['¿Le dificulta esa lesión realizar sus actividades diarias?','paciente','Paciente'],
  ['Solicito exámenes','medico_asistente','Doctor'],
  ['Solicito hemograma','laboratorio','Laboratorio'],
  ['Solicito radiografía','radiologia','Radiología'],
  ['Solicito interconsulta con cardiología','especialista','Especialista'],
  ['¿Cómo se siente?','paciente','Paciente'],
 ];
 let sid;
 for(let index=0;index<questions.length;index++) {
  const [question,agent,label]=questions[index],before=await page.locator('.chat-row').count(),spoken=await page.evaluate(()=>window.__spoken.length);
  await page.evaluate(q=>{window.__question=q},question);
  const pending=page.waitForResponse(r=>r.url().endsWith('/message')&&r.request().method()==='POST');
  await page.locator('[aria-label="Micrófono"]').click();const response=await pending;assert.equal(response.status(),200);
  const body=await response.json();sid=body.session.session_id;
  assert.equal(body.agent,agent);assert.equal(body.doctor_question,null);
  await page.waitForFunction(({before,text})=>document.querySelectorAll('.chat-row').length>=before+2&&[...document.querySelectorAll('.chat-text')].at(-1)?.textContent===text&&document.querySelector('[data-role="conversation-status"]').textContent==='Tu turno',{before,text:body.response});
  assert.equal(await page.locator('.chat-row').count(),before+2);
  assert.deepEqual((await page.locator('.chat-name strong').allTextContents()).slice(-2),['Tú',label]);
  assert.equal(await page.evaluate(()=>window.__spoken.length),spoken+1);
  record(`Turno ${index+1}: estudiante → ${label}; dos mensajes y una respuesta por voz`);
  if(index===0)await page.locator('[data-role="conversation-history"]').screenshot({path:out+'/capturas/pregunta-directa.png'});
  if(index===5)await page.locator('[data-role="conversation-history"]').screenshot({path:out+'/capturas/hallazgos-aclaracion.png'});
 }
 const legacy={type:'turn',student_message:'¿Cómo se encuentra ahora?',response_text:'Sigo con mis actividades habituales.',agent:'paciente',doctor_question:'REFORMULACION_ANTIGUA_NO_MOSTRAR'};
 const inserted=await fetch('http://127.0.0.1:3039/rest/v1/sma_eventos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sid,payload:legacy})});assert.equal(inserted.status,201);
 await page.reload();await page.locator('[data-role="start-simulation"]').click();
 await page.locator('.chat-text').filter({hasText:legacy.response_text}).waitFor();
 assert.ok(!(await page.locator('[data-role="conversation-history"]').textContent()).includes(legacy.doctor_question));
 assert.ok(!(await page.evaluate(()=>window.__spoken)).includes(legacy.doctor_question));
 await page.locator('[data-role="conversation-history"]').screenshot({path:out+'/capturas/conversacion-recuperada.png'});
 record('Al recuperar una actividad, los eventos antiguos no muestran ni leen la pregunta duplicada del doctor');
 assert.deepEqual(errors,[]);record('Sin errores JavaScript');
 writeFileSync(out+'/navegador.json',JSON.stringify({resultado:'PASA',entorno:'API real y PostgreSQL local PGlite; Auth y voz controlados; evento histórico sintético de prueba',pruebas:results},null,2));
 await ctx.close();
}finally{await browser.close()}
