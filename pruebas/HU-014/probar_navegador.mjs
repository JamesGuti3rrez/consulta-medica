import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdirSync,writeFileSync } from 'node:fs';
import { IDS } from './sql_fixture.mjs';
// OUT permite repetir la prueba como regresión sin sobrescribir la evidencia original de HU-014.
const base='http://127.0.0.1:3037',out=process.env.OUT||'pruebas/HU-014';mkdirSync(out+'/capturas',{recursive:true});
const browser=await chromium.launch({headless:true,channel:'msedge'});const results=[],errors=[];
const record=(name)=>{results.push({prueba:name,resultado:'PASA'});console.log('[PASA] '+name);};
async function context(token){
 const ctx=await browser.newContext({viewport:{width:1550,height:1100},colorScheme:'light'});
 await ctx.route('https://fonts.googleapis.com/**',r=>r.fulfill({contentType:'text/css',body:''}));
 await ctx.route('**/js/auth.js',r=>r.fulfill({contentType:'text/javascript',body:`
 const fixtureToken=${JSON.stringify(token)}, fixtureUser={id:${JSON.stringify(IDS[token])},email:fixtureToken+'@example.com',user_metadata:{nombres:fixtureToken}};
 const fixtureSession={access_token:fixtureToken,user:fixtureUser};
 const fixtureClient={auth:{getSession:async()=>({data:{session:fixtureSession}}),onAuthStateChange(){},signOut:async()=>({})}};
 window.auth={ready:Promise.resolve(fixtureClient),historyEnabled:Promise.resolve(false),displayName:u=>u.email,errorMessage:()=>'',
 api:async(path,options={})=>{const response=await fetch(path,{...options,headers:{...options.headers,Authorization:'Bearer '+fixtureToken}});if(!response.ok){const body=await response.json();const error=new Error(typeof body.detail==='string'?body.detail:'No se pudo completar');error.status=response.status;throw error;}return response;},
 profile:async()=> (await window.auth.api('/api/docente/sesion')).json()};` }));
 await ctx.addInitScript(()=>{
  Object.defineProperty(window,'speechSynthesis',{value:{cancel(){},speak(u){setTimeout(()=>u.onend?.(),1);}}});
  Object.defineProperty(window,'SpeechSynthesisUtterance',{value:class{constructor(t){this.text=t;}}});
  window.SpeechRecognition=class{start(){this.onstart?.();setTimeout(()=>{const item=[{transcript:window.__question}];item.isFinal=true;this.onresult?.({resultIndex:0,results:[item]});this.onend?.();},10);}stop(){}abort(){}};
 });
 return ctx;
}
async function openStudent(token,aid){
 const ctx=await context(token),page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/grupos.html');await page.getByRole('link',{name:'Resolver caso',exact:true}).first().waitFor();
 assert.match(await page.locator('#student-groups-list').textContent(),/Grupo de semiología/);
 if(token==='alumno-a')await page.screenshot({path:out+'/capturas/alumno-grupos.png',fullPage:true});
 await page.goto(base+'/simulacion.html?actividad='+aid);await page.locator('[data-role="start-simulation"]').click();
 await page.locator('[data-role="diagnosis-button"]').waitFor({state:'visible'});
 assert.equal(await page.locator('[data-role="evaluation-reference"]').textContent(),'');
 return {ctx,page};
}
// HU-006: el alumno escribe su diagnóstico, confirma el cierre y el servidor lo registra antes de cerrar.
async function finish(page,diagnosis){
 await page.locator('[data-role="diagnosis-button"]').click();await page.locator('[data-role="diagnosis-input"]').fill(diagnosis);
 await page.locator('[data-role="save-diagnosis"]').click();await page.locator('[data-role="confirm-diagnosis"]').waitFor({state:'visible'});
 const pending=page.waitForResponse(r=>r.url().endsWith('/finish')&&r.request().method()==='POST');
 await page.locator('[data-role="confirm-diagnosis"]').click();const response=await pending;assert.equal(response.status(),200);
 const body=await response.json();assert.equal(body.registro.guardado,true);
 await page.locator('[data-role="evaluation-student-diagnosis"]').filter({hasText:diagnosis}).waitFor();return body;
}
try{
 const reset=await fetch('http://127.0.0.1:3039/__reset',{method:'POST'});assert.equal(reset.status,200);
 const doctorCtx=await context('doctor-a'),doctor=await doctorCtx.newPage();doctor.on('pageerror',e=>errors.push(e.message));
 await doctor.goto(base+'/docente.html?seccion=grupos');await doctor.locator('#create-group-form').waitFor({state:'visible'});
 await doctor.locator('#group-name').fill('Grupo de semiología · A');await doctor.locator('#group-description').fill('Razonamiento clínico, evidencia y aprendizaje compartido.');
 await doctor.getByRole('button',{name:'Crear grupo',exact:true}).click();await doctor.locator('#member-email').waitFor();
 record('Panel Doctor: creación y selección de grupo');
 for(const token of ['alumno-a','alumno-b','alumno-c']){
  await doctor.locator('#member-email').fill(token+'@example.com');await doctor.getByRole('button',{name:'Añadir alumno',exact:true}).click();
  await doctor.locator('.group-member').filter({hasText:token+'@example.com'}).waitFor();
 }
 record('Tres cuentas registradas incorporadas al grupo');
 await doctor.locator('#assign-case').selectOption('MED-008');await doctor.locator('#assignment-title').fill('Consulta de evaluación inicial');
 const assigned=doctor.waitForResponse(r=>r.url().endsWith('/actividades')&&r.request().method()==='POST');
 await doctor.getByRole('button',{name:'Asignar caso al grupo',exact:true}).click();const assignment=await(await assigned).json();const aid=assignment.actividades[0].id;
 await doctor.locator('#activity-filter').waitFor();await doctor.locator('#group-results tbody tr').nth(2).waitFor();
 await doctor.locator('#groups-workspace').screenshot({path:out+'/capturas/doctor-grupo.png'});
 record('Caso asignado; comparación inicial sin notas ni diagnósticos');

 const a=await openStudent('alumno-a',aid);
 const prev=await a.page.locator('.chat-row').count();await a.page.evaluate(()=>{window.__question='Realizo exploración física';});
 const turn=a.page.waitForResponse(r=>r.url().endsWith('/message'));await a.page.locator('[aria-label="Micrófono"]').click();assert.equal((await turn).status(),200);
 await a.page.waitForFunction(n=>document.querySelectorAll('.chat-row').length>=n+2&&document.querySelector('[data-role="conversation-status"]').textContent==='Tu turno',prev);
 const closed=await finish(a.page,'Basalioma');assert.equal(closed.registro.numero_intento,1);
 assert.equal(typeof closed.evaluation.score,'number');
 await a.page.screenshot({path:out+'/capturas/alumno-resultado.png'});
 record('Alumno confirma y entrega el caso; diagnóstico registrado y proceso calculado por el backend');
 await a.page.reload();await a.page.locator('[data-role="start-simulation"]').click();
 await a.page.locator('[data-role="evaluation-student-diagnosis"]').filter({hasText:'Basalioma'}).waitFor();
 assert.equal(await a.page.locator('[data-role="start-simulation"]').isHidden(),true);await a.ctx.close();
 record('Recarga recupera la entrega finalizada sin abrir otra sesión');

 const b=await openStudent('alumno-b',aid);const second=await finish(b.page,'Amigdalitis');assert.equal(second.registro.numero_intento,1);await b.ctx.close();
 const c=await openStudent('alumno-c',aid);
 await doctor.locator('#refresh-groups').click();await doctor.locator('#group-results').getByText('En curso',{exact:true}).waitFor();
 await doctor.locator('#group-results').screenshot({path:out+'/capturas/comparativa-en-curso.png'});
 const third=await finish(c.page,'Basalioma o dermatitis');assert.equal(third.registro.numero_intento,1);await c.ctx.close();
 await doctor.locator('#refresh-groups').click();
 await doctor.locator('#group-results').getByText('Basalioma o dermatitis',{exact:true}).waitFor();
 // Sin calificación automática (TA-021 pendiente): las tres entregas finalizadas, con su diagnóstico y sin acierto.
 assert.equal(await doctor.locator('#group-results tbody .group-state.finalizada').count(),3);
 assert.equal(await doctor.locator('#group-results tbody .group-state.pendiente_revision').count(),0);
 const comparativa=await doctor.locator('#group-results').textContent();
 for(const texto of ['Basalioma','Amigdalitis','Basalioma o dermatitis'])assert.ok(comparativa.includes(texto),texto);
 assert.equal(await doctor.locator('#group-results tbody tr').count(),3);
 await doctor.locator('#group-results').screenshot({path:out+'/capturas/comparativa-final.png'});
 record('Comparativa de la misma actividad: tres entregas finalizadas con el diagnóstico de cada alumno');

 // El nombre sigue aislado por propietario y las rutas no revelan participantes al otro doctor.
 const groupId=(await doctor.locator('.group-card.is-selected').getAttribute('data-group-id'));
 const denied=await doctorCtx.request.get(base+'/api/grupos/doctor/'+groupId,{headers:{Authorization:'Bearer doctor-b'}});assert.equal(denied.status(),404);
 record('Otro doctor recibe 404 sin resultados del grupo');
 const edit=doctor.getByText('Editar nombre y descripción',{exact:true});await edit.click();await doctor.locator('#edit-group-name').fill('Grupo de semiología · A (revisado)');
 await doctor.getByRole('button',{name:'Guardar cambios',exact:true}).click();await doctor.locator('#group-detail h2').filter({hasText:'revisado'}).waitFor();
 await doctor.reload();await doctor.locator('#show-groups').click();await doctor.locator('.group-card').filter({hasText:'revisado'}).click();await doctor.locator('#group-results').getByText('Amigdalitis',{exact:true}).waitFor();
 record('Grupo y resultados persisten al recargar el panel');
 assert.deepEqual(errors,[]);record('Sin errores JavaScript en los recorridos');
 writeFileSync(out+'/navegador.json',JSON.stringify({resultado:'PASA',api_real:true,sql_real_local:'PostgreSQL PGlite con migraciones 0005, 0006 y 0007',auth:'Identidades de fixture',voz:'Dispositivos simulados',pruebas:results},null,2));
 await doctorCtx.close();
}finally{await browser.close();}
