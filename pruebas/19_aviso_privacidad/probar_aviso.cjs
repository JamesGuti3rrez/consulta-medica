// Aviso de privacidad (Ley 29733): la página existe y se enlaza desde la portada; crear una cuenta exige
// aceptarlo y la cuenta guarda la versión y la fecha de aceptación. Para no crear cuentas reales, la prueba
// intercepta el pedido de registro a Supabase, lee lo que se enviaría y lo corta.
// Uso (servidor en BASE_URL, por defecto http://localhost:3000):
//   node pruebas/19_aviso_privacidad/probar_aviso.cjs [carpeta_capturas]
const path = require('path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';

(async () => {
  const outDir = process.argv[2] || 'pruebas/19_aviso_privacidad/resultados';
  const shot = name => path.join(outDir, `${name}.png`);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));

  let signupBody = null;
  await page.route('**/auth/v1/signup**', route => {
    signupBody = JSON.parse(route.request().postData() || '{}');
    return route.abort();
  });

  await page.goto(`${BASE_URL}/index.html`, { waitUntil: 'networkidle' });
  const footerLink = await page.locator('footer a[href="privacidad.html"]').count();
  console.log('enlace al aviso en el pie de la portada:', footerLink === 1);

  await page.locator('[data-role="signup"]').first().click();
  const form = page.locator('[data-role="signup-form"]');
  await form.locator('[name="nombres"]').fill('Alumno');
  await form.locator('[name="apellidos"]').fill('De Prueba');
  await form.locator('[name="correo"]').fill('alumno.prueba@example.com');
  await form.locator('[name="clave"]').fill('ClaveDePrueba123');

  // 1. Sin aceptar el aviso: no se envía nada.
  await form.locator('button[type="submit"]').click();
  await page.waitForTimeout(400);
  const feedback = await form.locator('[data-role="auth-feedback"]').innerText();
  console.log('sin aceptar, mensaje:', feedback, '| se envió a Supabase:', signupBody !== null);
  await page.screenshot({ path: shot('1_registro_sin_aceptar') });

  // 2. Aceptando el aviso: se envía con la versión y la fecha de aceptación.
  await form.locator('[name="privacidad"]').check();
  console.log('al marcar la casilla, el aviso de error desaparece:', await form.locator('[data-role="auth-feedback"]').isHidden());
  await page.screenshot({ path: shot('2_registro_aceptando') });
  await form.locator('button[type="submit"]').click();
  await page.waitForTimeout(800);
  const data = signupBody?.data || {};
  console.log('aceptando, se envió a Supabase:', signupBody !== null);
  console.log('  datos de la cuenta:', JSON.stringify({ ...data, privacidad_aceptada_en: data.privacidad_aceptada_en ? '(fecha ISO)' : null }));
  console.log('  fecha válida:', !Number.isNaN(Date.parse(data.privacidad_aceptada_en)));

  // 3. La página del aviso se abre y describe lo que se guarda.
  await page.goto(`${BASE_URL}/privacidad.html`, { waitUntil: 'networkidle' });
  const text = await page.locator('main').innerText();
  console.log('página del aviso:', await page.title());
  for (const term of ['Ley N.º 29733', 'Supabase', 'Groq', 'Mis simulaciones', 'ARCO']) {
    console.log(`  menciona ${term}:`, text.includes(term));
  }
  await page.screenshot({ path: shot('3_pagina_aviso'), fullPage: true });

  console.log('errores:', errors);
  await browser.close();
})();
