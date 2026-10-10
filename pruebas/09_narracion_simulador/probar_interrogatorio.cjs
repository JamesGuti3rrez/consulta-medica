// Recorrido completo del simulador: entra con una especialidad, «Iniciar simulación», presentación del
// doctor, preguntas por micrófono, una hipótesis y el diagnóstico. El navegador automático no tiene
// micrófono: se sustituye SpeechRecognition por uno que «dice» las frases de PREGUNTAS en orden, con
// resultados parciales y finales como el real. Guarda capturas de cada paso.
// Uso (con el servidor en http://localhost:3000):
//   node pruebas/09_narracion_simulador/probar_interrogatorio.cjs [carpeta] [especialidad] [prefijo]
const path = require('path');
const { chromium } = require('playwright');

const PREGUNTAS = {
  medicina_interna: ['¿Desde cuándo tiene la lesión?', '¿Es alérgica a algún medicamento?', 'Exploro la espalda'],
  emergencias: ['Pregúntale qué medicamentos toma', 'Pregúntale si tiene alergias', 'Voy a examinar al paciente'],
  cirugia_general: ['¿Hay alguna enfermedad en su familia?', 'Pido pruebas de coagulación'],
};

(async () => {
  const outDir = process.argv[2] || 'pruebas/09_narracion_simulador';
  const specialty = process.argv[3] || 'emergencias';
  const prefix = process.argv[4] || 'interrogatorio';
  const shot = name => path.join(outDir, `${prefix}_${name}.png`);
  const browser = await chromium.launch({ args: ['--mute-audio'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.addInitScript(phrases => {
    let next = 0;
    class FakeRecognition {
      start() {
        const phrase = phrases[next++ % phrases.length];
        const result = (text, isFinal) => ({ resultIndex: 0, results: [Object.assign([{ transcript: text }], { isFinal })] });
        setTimeout(() => this.onstart?.(), 50);
        setTimeout(() => this.onresult?.(result(phrase.slice(0, Math.ceil(phrase.length / 2)), false)), 400);
        setTimeout(() => this.onresult?.(result(phrase, true)), 900);
        setTimeout(() => this.onend?.(), 1200);
      }
      stop() { setTimeout(() => this.onend?.(), 50); }
      abort() { this.stop(); }
    }
    window.SpeechRecognition = FakeRecognition;
    window.webkitSpeechRecognition = FakeRecognition;
  }, PREGUNTAS[specialty]);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });

  await page.goto(`http://localhost:3000/simulacion.html?especialidad=${specialty}`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
  const [caseResponse] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/api/caso')),
    page.getByRole('button', { name: /Iniciar simulaci/ }).click(),
  ]);
  const caseId = (await caseResponse.json()).case_id;
  const mic = page.locator('[aria-label="Micrófono"]');
  await mic.waitFor({ state: 'visible', timeout: 90000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: shot('1_listo_para_preguntar') });
  console.log('botón de inicio visible tras la presentación:', await page.locator('[data-role="start-simulation"]').isVisible());

  const turnos = PREGUNTAS[specialty].length;
  for (let turno = 1; turno <= turnos; turno += 1) {
    await mic.click();
    if (turno === 1) {
      await page.waitForSelector('.chat-preview');
      await page.waitForTimeout(500);
      await page.screenshot({ path: shot('2_transcribiendo') });
    }
    await page.waitForFunction(n => document.querySelectorAll('.chat-student').length >= n, turno);
    await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent === 'Tu turno', null, { timeout: 60000 });
  }
  await page.screenshot({ path: shot('3_respuestas') });

  await page.getByRole('tab', { name: /Hipótesis/ }).click();
  await page.fill('[data-role="hypothesis-input"]', 'Hipótesis de prueba');
  await page.click('[data-role="add-hypothesis"]');
  await page.click('[data-role="diagnosis-button"]');
  await page.fill('[data-role="diagnosis-input"]', 'Diagnóstico de prueba');
  await page.click('[data-role="save-diagnosis"]');
  await page.waitForFunction(() => document.querySelector('[data-role="diagnosis-feedback"]').textContent.includes('finalizada'));
  await page.screenshot({ path: shot('4_diagnostico') });

  const chat = await page.$$eval('.chat-row', rows => rows.map(r => `${r.querySelector('.chat-name strong').textContent}: ${r.querySelector('.chat-text').textContent}`));
  console.log(chat.join('\n'));
  console.log('código del caso visible en pantalla:', (await page.locator('body').innerText()).includes(caseId));
  console.log('errores:', errors);
  await browser.close();
})();
