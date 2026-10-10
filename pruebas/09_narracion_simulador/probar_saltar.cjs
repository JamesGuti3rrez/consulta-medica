// Prueba del botón «Saltar»: inicia la simulación y pulsa «Saltar» en cada frase del doctor. Mide cuánto
// tarda la presentación completa saltando y guarda una captura con el botón visible.
// Uso (con el servidor en http://localhost:3000): node pruebas/09_narracion_simulador/probar_saltar.cjs
const { chromium } = require('playwright');
(async () => {
  const out = process.argv[2] || 'pruebas/09_narracion_simulador';
  const browser = await chromium.launch({ args: ['--mute-audio'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://localhost:3000/simulacion.html?especialidad=cirugia_general', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
  console.log('velocidad de la voz:', await page.evaluate(() => fetch('js/simulacion.js').then(r => r.text()).then(t => t.match(/SPEECH_RATE = ([\d.]+)/)[1])));
  const started = Date.now();
  await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
  const skip = page.locator('[data-role="doctor-bubble"] [data-role="skip-speech"]');
  await skip.waitFor({ state: 'visible' });
  await page.screenshot({ path: `${out}/saltar_boton_visible.png` });
  let saltos = 0;
  while (!(await page.locator('[aria-label="Micrófono"]').isVisible())) {
    if (await skip.isVisible()) {
      await skip.click();
      saltos += 1;
    }
    await page.waitForTimeout(100);
  }
  console.log(`presentación completa en ${((Date.now() - started) / 1000).toFixed(1)} s saltando ${saltos} frases`);
  console.log('frases en el chat:', await page.locator('.chat-row').count());
  console.log('errores:', errors);
  await browser.close();
})();
