import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
const browser=await chromium.launch({headless:true,channel:'msedge'});
try{
 const ctx=await browser.newContext({viewport:{width:1450,height:1050}});
 await ctx.route('https://fonts.googleapis.com/**',r=>r.fulfill({contentType:'text/css',body:''}));
 await ctx.route('**/js/auth.js',r=>r.fulfill({contentType:'text/javascript',body:`
 window.__authCallbacks=[];window.auth={ready:Promise.resolve({auth:{onAuthStateChange(cb){window.__authCallbacks.push(cb)}}}),
 api:async(path,options={})=>{const r=await fetch(path,{...options,headers:{...options.headers,Authorization:'Bearer doctor-a'}});if(!r.ok)throw Error('HTTP '+r.status);return r},
 profile:async()=> (await window.auth.api('/api/docente/sesion')).json()};`}));
 const page=await ctx.newPage();await page.goto('http://127.0.0.1:3037/docente.html?seccion=grupos');
 await page.locator('.group-card').first().click();await page.locator('.group-member-list').waitFor();
 await page.locator('#create-group-form').screenshot({path:'pruebas/HU-014/capturas/crear-grupo.png'});
 await page.locator('#group-detail > section').nth(1).screenshot({path:'pruebas/HU-014/capturas/miembros.png'});
 await page.locator('#assign-case').selectOption('MED-008');await page.locator('#assignment-title').fill('Nueva actividad de razonamiento');
 await page.locator('#group-detail > section').nth(2).screenshot({path:'pruebas/HU-014/capturas/asignar.png'});
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
 await page.evaluate(()=>window.__authCallbacks.forEach(cb=>cb('SIGNED_IN',{user:{id:'10000000-0000-4000-8000-000000000002'}})));
 await page.waitForURL('**/index.html?cuenta=login');await page.waitForLoadState('domcontentloaded');
 assert.equal(await page.locator('#group-detail').count(),0);
 writeFileSync('pruebas/HU-014/ui_adicional.json',JSON.stringify({resultado:'PASA',responsive_390:true,cambio_identidad_cierra_panel:true,capturas:['crear-grupo.png','miembros.png','asignar.png']},null,2));
 console.log('[PASA] Capturas de creación, integrantes y asignación; interfaz a 390 px; cambio de identidad cierra el panel.');
 await ctx.close();
}finally{await browser.close();}
