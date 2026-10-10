// Recorrido desde la portada: «Probar la simulación» → ventana «Elige tu caso» (nombres y especialidad)
// → «Generar caso aleatorio» → simulador con la especialidad elegida → «Iniciar simulación» → el doctor
// presenta el caso. Guarda capturas de cada paso.
// Uso (con el servidor en http://localhost:3000): node pruebas/09_narracion_simulador/probar_portada.cjs
const path = require('path');
const { chromium } = require('playwright');
(async () => {
  const outDir = process.argv[2] || 'pruebas/09_narracion_simulador';
  const shot = name => path.join(outDir, name);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('http://localhost:3000/', { waitUntil: 'networkidle' });
  await page.screenshot({ path: shot('portada_1_inicio.png') });
  await page.locator('[data-role="open-case-picker"]').first().click();
  await page.locator('[data-role="case-picker-panel"]').waitFor({ state: 'visible' });
  await page.fill('[data-role="case-picker"] input[name="nombres"]', 'Bryam');
  await page.fill('[data-role="case-picker"] input[name="apellidos"]', 'Gutiérrez');
  await page.locator('label.specialty', { hasText: 'Emergencias' }).click();
  await page.screenshot({ path: shot('portada_2_elige_tu_caso.png') });
  await Promise.all([page.waitForURL(/simulacion\.html\?especialidad=emergencias/), page.getByRole('button', { name: /Generar caso aleatorio/ }).click()]);
  await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
  console.log('URL:', page.url());
  console.log('especialidad elegida en el simulador:', await page.inputValue('[data-role="specialty-select"]'));
  await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
  await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent.includes('terminada'), null, { timeout: 90000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: shot('portada_3_caso_presentado.png') });
  console.log('caso:', await page.textContent('[data-role="record-status"]'));
  console.log((await page.$$eval('.chat-row .chat-text', els => els.map(e => e.textContent))).join('\n'));
  console.log('errores:', errors);
  await browser.close();
})();
