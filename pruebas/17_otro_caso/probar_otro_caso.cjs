// Botones de la hoja de evaluación: «Probar otro caso» (misma especialidad, otro paciente, sin recargar)
// y «Cerrar simulador» (vuelve a la portada). El micrófono se sustituye por uno que «dice» una pregunta.
// Uso (servidor en BASE_URL, por defecto http://localhost:3000):
//   node pruebas/17_otro_caso/probar_otro_caso.cjs [carpeta_capturas]
const path = require('path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';

(async () => {
  const outDir = process.argv[2] || 'pruebas/17_otro_caso/resultados';
  const shot = name => path.join(outDir, `${name}.png`);
  const browser = await chromium.launch({ args: ['--mute-audio'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.addInitScript(() => {
    class FakeRecognition {
      start() {
        const result = { resultIndex: 0, results: [Object.assign([{ transcript: '¿Desde cuándo empezó?' }], { isFinal: true })] };
        setTimeout(() => this.onstart?.(), 50);
        setTimeout(() => this.onresult?.(result), 500);
        setTimeout(() => this.onend?.(), 800);
      }
      stop() { setTimeout(() => this.onend?.(), 50); }
      abort() { this.stop(); }
    }
    window.SpeechRecognition = FakeRecognition;
    window.webkitSpeechRecognition = FakeRecognition;
  });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });

  // Espera la presentación (saltando la narración), hace una pregunta y guarda un diagnóstico.
  const consulta = async (casePromise, ronda) => {
    const caso = await (await casePromise).json();
    const mic = page.locator('[aria-label="Micrófono"]');
    while (!(await mic.isVisible())) {
      const skip = page.locator('[data-role="skip-speech"]:visible').first();
      if (await skip.count()) await skip.click().catch(() => null);
      await page.waitForTimeout(300);
    }
    const ficha = await page.locator('[data-role="record-name"]').innerText();
    const chat = await page.locator('.chat-row').count();
    const reply = page.waitForResponse(r => r.url().includes('/message'));
    await mic.click();
    await reply;
    await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent === 'Tu turno', null, { timeout: 60000 });
    await page.click('[data-role="diagnosis-button"]');
    await page.fill('[data-role="diagnosis-input"]', `Diagnóstico ronda ${ronda}`);
    await page.click('[data-role="save-diagnosis"]');
    await page.locator('[data-role="evaluation-panel"]').waitFor({ state: 'visible' });
    console.log(`ronda ${ronda}: ${caso.specialty} | paciente en la ficha: ${ficha} | mensajes del chat al empezar: ${chat} | URL: ${new URL(page.url()).search}`);
    return { especialidad: caso.specialty, paciente: ficha };
  };
  const otroCaso = async () => {
    const casePromise = page.waitForResponse(r => r.url().includes('/api/caso'));
    await page.click('[data-role="another-case"]');
    return casePromise;
  };

  // 1. Pediatría: tres rondas seguidas con «Probar otro caso».
  await page.goto(`${BASE_URL}/simulacion.html?especialidad=pediatria`, { waitUntil: 'networkidle' });
  await page.evaluate(() => sessionStorage.clear());
  await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
  const primera = page.waitForResponse(r => r.url().includes('/api/caso'));
  await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
  const rondas = [await consulta(primera, 1)];
  await page.locator('[data-role="another-case"]').scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await page.screenshot({ path: shot('1_hoja_con_botones') });
  rondas.push(await consulta(await otroCaso(), 2));
  rondas.push(await consulta(await otroCaso(), 3));
  await page.screenshot({ path: shot('2_tercera_ronda') });

  // 2. Desde un caso de prueba (?caso=): sigue con su especialidad y la URL deja de mostrar el código.
  await page.goto(`${BASE_URL}/simulacion.html?caso=MED-008`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
  const deprueba = page.waitForResponse(r => r.url().includes('/api/caso'));
  await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
  const r4 = await consulta(deprueba, 4);
  const r5 = await consulta(await otroCaso(), 5);

  // 3. «Cerrar simulador» vuelve a la portada.
  await Promise.all([page.waitForURL(url => !url.pathname.includes('simulacion')), page.click('[data-role="close-simulator"]')]);
  await page.screenshot({ path: shot('3_portada_tras_cerrar') });

  console.log('\nRESUMEN');
  console.log('pediatría, misma especialidad en las 3 rondas:', rondas.every(r => r.especialidad === 'pediatria'));
  console.log('pediatría, la ronda 2 es otro paciente:', rondas[1].paciente !== rondas[0].paciente);
  console.log('pediatría, la ronda 3 no repite al de la ronda 2:', rondas[2].paciente !== rondas[1].paciente);
  console.log('desde caso de prueba, otro paciente de la misma especialidad:', r5.especialidad === r4.especialidad && r5.paciente !== r4.paciente);
  console.log('«Cerrar simulador» lleva a:', new URL(page.url()).pathname);
  console.log('errores:', errors);
  await browser.close();
})();
