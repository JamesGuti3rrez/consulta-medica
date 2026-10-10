// Prueba de la narración del simulador: elige pediatría, inicia y espera a que el doctor termine de
// presentar el caso. Guarda dos capturas (narrando y presentación terminada) e imprime el historial.
// Uso (con el servidor en http://localhost:3000): node pruebas/09_narracion_simulador/probar_narracion.cjs
const { chromium } = require('playwright');
(async () => {
  const out = process.argv[2] || 'pruebas/09_narracion_simulador/narracion';
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('http://localhost:3000/simulacion.html', { waitUntil: 'networkidle' });
  await page.selectOption('[data-role="specialty-select"]', 'pediatria');
  await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: out + '_1_narrando.png' });
  await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent.includes('terminada'), null, { timeout: 90000 });
  await page.waitForTimeout(800);
  console.log('tabs:', await page.$$eval('[data-tab]', b => b.map(x => x.dataset.tab + '=' + x.className)));
  await page.screenshot({ path: out + '_2_terminada.png' });
  const chat = await page.$$eval('.chat-row .chat-text', els => els.map(e => e.textContent));
  console.log('caso:', await page.textContent('[data-role="record-status"]'));
  console.log(chat.join('\n'));
  console.log('errores:', errors);
  await browser.close();
})();
