// Diagnóstico de acceso: cuenta temporal suministrada solo por variables del proceso padre.
import { chromium } from 'playwright';
const browser=await chromium.launch({headless:true,channel:'msedge'});
try{
 const context=await browser.newContext();
 await context.route('https://fonts.googleapis.com/**',r=>r.fulfill({contentType:'text/css',body:''}));
 const page=await context.newPage();
 await page.goto('http://localhost:3000/index.html?cuenta=login',{waitUntil:'domcontentloaded'});
 const form=page.locator('[data-role="login-form"]');await form.waitFor({state:'visible'});
 await form.locator('[name="correo"]').fill(process.env.LOGIN_TEST_EMAIL);
 await form.locator('[name="clave"]').fill(process.env.LOGIN_TEST_PASSWORD);
 const pending=page.waitForResponse(r=>r.url().includes('/auth/v1/token')&&r.request().method()==='POST',{timeout:30000});
 await form.locator('button[type="submit"]').click();const response=await pending;
 const result={login_http:response.status(),panel_visible:false};
 if(response.ok()){
  await page.waitForURL('**/docente.html',{timeout:20000});
  await page.locator('#workspace').waitFor({state:'visible',timeout:20000});result.panel_visible=true;
 }else{
  const body=await response.json();result.codigo=body.error_code||body.code||'auth_error';
 }
 console.log(JSON.stringify(result));
 await context.close();
 if(!result.panel_visible)process.exitCode=1;
}finally{await browser.close();}
