// Recorrido del simulador con el motor clínico integrado: el estudiante pregunta por micrófono,
// propone un tratamiento contraindicado (debe aparecer la alerta de seguridad), guarda el diagnóstico
// y el simulador muestra la hoja de evaluación que devuelve /finish. El navegador automático no tiene
// micrófono: SpeechRecognition se sustituye por uno que «dice» las frases del guion en orden.
// Uso (con el servidor en http://localhost:3000):
//   node pruebas/15_integracion_motor_clinico/probar_evaluacion.cjs [completo|parcial] [carpeta]
// «completo» pide todos los datos clave de MED-008; «parcial» omite varios para ver errores en la hoja.
const path = require('path');
const { chromium } = require('playwright');

const CASO = 'MED-008';
const GUIONES = {
  completo: [
    '¿Puede contarme sobre inicio y evolucion?',
    '¿Puede contarme sobre medicacion?',
    '¿Puede contarme sobre antecedentes personales?',
    '¿Puede contarme sobre alergias?',
    '¿Puede contarme sobre habitos?',
    'Voy a realizar la exploración física para revisar exploracion fisica.',
    'Mi tratamiento es administrar doxiciclina.',
  ],
  parcial: [
    '¿Puede contarme sobre inicio y evolucion?',
    'Mi tratamiento es administrar doxiciclina.',
  ],
};

(async () => {
  const modo = process.argv[2] || 'completo';
  const outDir = process.argv[3] || 'pruebas/15_integracion_motor_clinico/resultados';
  const frases = GUIONES[modo];
  if (!frases) throw new Error(`Modo desconocido: ${modo}`);
  const shot = name => path.join(outDir, `${modo}_${name}.png`);

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
  }, frases);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });

  await page.goto(`http://localhost:3000/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
  await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
  // Se salta la narración de la presentación para no esperar la lectura completa.
  const mic = page.locator('[aria-label="Micrófono"]');
  while (!(await mic.isVisible())) {
    const skip = page.locator('[data-role="skip-speech"]:visible').first();
    if (await skip.count()) await skip.click().catch(() => null);
    await page.waitForTimeout(300);
  }

  let alerta = '';
  for (let turno = 1; turno <= frases.length; turno += 1) {
    const replyPromise = page.waitForResponse(r => r.url().includes('/message'));
    await mic.click();
    const reply = await (await replyPromise).json();
    await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent === 'Tu turno', null, { timeout: 60000 });
    console.log(`turno ${turno}: ${frases[turno - 1]} -> ${reply.agent}; evidencia ${JSON.stringify(reply.evidence_ids)}; alertas ${JSON.stringify((reply.safety_alerts || []).map(a => a.code))}`);
    if ((reply.safety_alerts || []).length) {
      alerta = await page.locator('[data-role="case-status"]').innerText();
      await page.screenshot({ path: shot('1_alerta_seguridad') });
    }
  }
  console.log('alerta en pantalla:', alerta || '(ninguna)');

  await page.getByRole('tab', { name: /Hipótesis/ }).click();
  await page.fill('[data-role="hypothesis-input"]', 'Hipótesis de prueba');
  await page.click('[data-role="add-hypothesis"]');
  await page.click('[data-role="diagnosis-button"]');
  await page.fill('[data-role="diagnosis-input"]', 'Diagnóstico de prueba');
  const finishPromise = page.waitForResponse(r => r.url().includes('/finish'));
  await page.click('[data-role="save-diagnosis"]');
  const finish = await (await finishPromise).json();
  const hoja = page.locator('[data-role="evaluation-panel"]');
  await hoja.waitFor({ state: 'visible' });
  await page.waitForTimeout(300);
  await page.screenshot({ path: shot('2_hoja_evaluacion') });

  console.log('evaluación devuelta por /finish:', JSON.stringify(finish.evaluation));
  console.log('hoja en pantalla:\n' + await hoja.innerText());

  await page.click('[data-role="close-evaluation"]');
  const cerrada = await hoja.isHidden();
  await page.click('[data-role="diagnosis-button"]');
  const reabierta = await hoja.isVisible();
  console.log('la hoja se cierra:', cerrada, '| se reabre con «Ver hoja de evaluación»:', reabierta);
  console.log('código del caso visible en pantalla:', (await page.locator('body').innerText()).includes(CASO));
  console.log('errores:', errors);
  await browser.close();
})();
