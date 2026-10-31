// API y SQL reales de fixture; sesión controlada para reproducir carreras de carga.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
import { IDS } from './sql_fixture.mjs';
const base='http://127.0.0.1:3037',out='pruebas/HU-014',results=[],errors=[];
const browser=await chromium.launch({headless:true,channel:'msedge'});
const record=prueba=>{results.push({prueba,resultado:'PASA'});console.log('[PASA] '+prueba);};
const authScript=`window.__authCallbacks=[];
const user={id:${JSON.stringify(IDS['doctor-a'])},email:'doctor-a@example.com'};
const client={auth:{onAuthStateChange(cb){window.__authCallbacks.push(cb)},getSession:async()=>({data:{session:{user,access_token:'doctor-a'}}}),
signOut:async()=>{window.__authCallbacks.forEach(cb=>cb('SIGNED_OUT',null));return {}}}};
window.auth={ready:Promise.resolve(client),historyEnabled:Promise.resolve(false),displayName:u=>u.email,errorMessage:()=>'',api:async(path,options={})=>{
 const r=await fetch(path,{...options,headers:{...options.headers,Authorization:'Bearer doctor-a'}});
 if(!r.ok){const body=await r.json();throw new Error(typeof body.detail==='string'?body.detail:'Solicitud no disponible')};return r;
},profile:async()=>(await window.auth.api('/api/docente/sesion')).json()};`;
async function context(){
 const ctx=await browser.newContext({viewport:{width:1450,height:1050}});
 await ctx.route('https://fonts.googleapis.com/**',r=>r.fulfill({contentType:'text/css',body:''}));
 await ctx.route('**/js/auth.js',r=>r.fulfill({contentType:'text/javascript',body:authScript}));
 return ctx;
}
const api=async(path,options={})=>{
 const r=await fetch(base+'/api/grupos'+path,{...options,headers:{Authorization:'Bearer doctor-a','Content-Type':'application/json'}});
 assert.ok(r.ok,'Preparación HTTP '+r.status);return r.json();
};
try {
 assert.equal((await fetch('http://127.0.0.1:3039/__reset',{method:'POST'})).status,200);
 for(const nombre of ['Grupo 01','Grupo 02'])await api('/doctor',{method:'POST',body:JSON.stringify({nombre})});
 const ctx=await context(),page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));
 // El perfil se verifica antes de terminar de descargar el módulo de grupos.
 await ctx.route('**/js/grupos-doctor.js',async route=>{await new Promise(resolve=>setTimeout(resolve,700));await route.continue();});
 await page.goto(base+'/docente.html?seccion=grupos');
 await page.locator('.group-card').nth(1).waitFor();
 assert.equal(await page.locator('.group-card').count(),2);
 assert.equal(await page.locator('.group-card small').first().textContent(),'0 alumnos · 0 actividades');
 record('Perfil verificado antes de cargar el módulo: aparecen los dos grupos vacíos sin crear otro');
 await page.locator('#groups-workspace').screenshot({path:out+'/capturas/grupos-vacios.png'});
 await ctx.unroute('**/js/grupos-doctor.js');
 await page.locator('#logout').click();await page.waitForURL('**/index.html*');
 await page.goto(base+'/docente.html?seccion=grupos');await page.locator('.group-card').nth(1).waitFor();
 assert.equal(await page.locator('.group-card').count(),2);
 record('Cerrar sesión y volver con la misma identidad recupera los grupos sin escrituras (Auth controlado)');
 await page.locator('#group-name').fill(' GRUPO   01 ');
 const duplicate=page.waitForResponse(r=>r.url().endsWith('/api/grupos/doctor')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Crear grupo',exact:true}).click();assert.equal((await duplicate).status(),409);
 await page.getByText('Ya tienes un grupo con ese nombre. Elige otro nombre.',{exact:true}).waitFor();
 assert.equal(await page.locator('.group-card').count(),2);
 await page.locator('#groups-workspace').screenshot({path:out+'/capturas/grupo-duplicado.png'});
 record('Crear un nombre repetido devuelve 409 y un mensaje claro sin añadir tarjetas');
 await page.locator('.group-card').filter({hasText:'Grupo 02'}).click();await page.locator('#group-detail h2').waitFor();
 await page.getByText('Editar nombre y descripción',{exact:true}).click();await page.locator('#edit-group-name').fill('grupo 01');
 const edit=page.waitForResponse(r=>r.url().includes('/api/grupos/doctor/')&&r.request().method()==='PATCH');
 await page.getByRole('button',{name:'Guardar cambios',exact:true}).click();assert.equal((await edit).status(),409);
 await page.getByText('Ya tienes un grupo con ese nombre. Elige otro nombre.',{exact:true}).waitFor();
 assert.equal(await page.locator('#group-detail h2').textContent(),'Grupo 02');
 record('Editar hacia un nombre existente también se rechaza y conserva el grupo original');
 await ctx.close();

 const earlyCtx=await context(),early=await earlyCtx.newPage();early.on('pageerror',e=>errors.push(e.message));
 let releaseProfile;const profileGate=new Promise(resolve=>{releaseProfile=resolve;});
 await earlyCtx.route('**/api/docente/sesion',async route=>{await profileGate;await route.continue();});
 // Un fallo del catálogo no debe bloquear las consultas independientes a grupos.
 await earlyCtx.route('**/api/docente/casos',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Catálogo temporalmente no disponible'})}));
 await early.goto(base+'/docente.html');await early.evaluate(()=>document.getElementById('show-groups').click());
 releaseProfile();await early.locator('.group-card').nth(1).waitFor();
 assert.equal(await early.locator('.group-card').count(),2);
 assert.equal(await early.locator('#groups-workspace').isVisible(),true);
 record('Apertura anterior a la verificación se reanuda automáticamente al recibir el perfil');
 await early.getByText('Catálogo temporalmente no disponible',{exact:true}).first().waitFor();
 assert.equal(await early.locator('.group-card').count(),2);
 record('Un error del catálogo no oculta ni impide cargar los grupos');
 await earlyCtx.close();

 const slowCtx=await context(),slow=await slowCtx.newPage();slow.on('pageerror',e=>errors.push(e.message));
 let releaseCatalog;const catalogGate=new Promise(resolve=>{releaseCatalog=resolve;});
 await slowCtx.route('**/api/docente/casos',async route=>{await catalogGate;await route.continue();});
 await slow.goto(base+'/docente.html?seccion=grupos');await slow.locator('.group-card').nth(1).waitFor();
 await slow.locator('.group-card').first().click();await slow.locator('#assign-case').waitFor();
 assert.equal(await slow.locator('#assign-case option').count(),1);
 releaseCatalog();await slow.locator('#assign-case option[value="MED-008"]').waitFor({state:'attached'});
 record('Catálogo lento: los grupos se consultan primero y el selector se completa cuando llegan los casos');
 await slowCtx.close();assert.deepEqual(errors,[]);
 record('Sin errores JavaScript durante las pruebas de carga');
 writeFileSync(out+'/carga_grupos.json',JSON.stringify({resultado:'PASA',auth:'Fixture; API FastAPI y PostgreSQL reales locales',pruebas:results},null,2));
 console.log(`Resultado: ${results.length}/${results.length} verificaciones aprobadas.`);
} finally {await browser.close();}
