// «Mis simulaciones» de punta a punta: una consulta como invitado (no se guarda), inicio de sesión con el
// alumno de prueba, dos consultas guardadas y el historial abierto desde el simulador y desde la portada.
// El micrófono se sustituye por uno que «dice» las frases del guion, como en las pruebas anteriores.
// Uso (servidor en BASE_URL, por defecto http://localhost:3000; credenciales creadas con usuario_prueba.py):
//   CREDENCIALES=<archivo> node pruebas/16_historial_simulaciones/probar_historial.cjs [carpeta_capturas]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const CASO = 'MED-007';
const COMPLETO = [
  '¿Puede contarme sobre inicio y evolucion?',
  '¿Puede contarme sobre medicacion?',
  '¿Puede contarme sobre antecedentes personales?',
  '¿Puede contarme sobre alergias?',
  '¿Puede contarme sobre habitos?',
  'Voy a realizar la exploración física para revisar exploracion fisica.',
];
const PARCIAL = ['¿Puede contarme sobre inicio y evolucion?', 'Mi tratamiento es administrar doxiciclina.'];

(async () => {
  const outDir = process.argv[2] || 'pruebas/16_historial_simulaciones/resultados';
  fs.mkdirSync(outDir, { recursive: true });
  const shot = name => path.join(outDir, `${name}.png`);
  const credenciales = JSON.parse(fs.readFileSync(process.env.CREDENCIALES, 'utf-8'));

  const browser = await chromium.launch({ args: ['--mute-audio'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.addInitScript(() => {
    class FakeRecognition {
      start() {
        const phrases = window.__frases || [''];
        const phrase = phrases[(window.__siguiente = (window.__siguiente || 0) + 1) - 1] || phrases[0];
        const result = (text, isFinal) => ({ resultIndex: 0, results: [Object.assign([{ transcript: text }], { isFinal })] });
        setTimeout(() => this.onstart?.(), 50);
        setTimeout(() => this.onresult?.(result(phrase, true)), 600);
        setTimeout(() => this.onend?.(), 900);
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

  const consulta = async (frases, diagnostico, nombre) => {
    await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
    await page.evaluate(f => { window.__frases = f; window.__siguiente = 0; }, frases);
    await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
    const startPromise = page.waitForResponse(r => r.url().endsWith('/api/ai/sessions') && r.request().method() === 'POST');
    await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
    const conToken = Boolean((await startPromise).request().headers().authorization);
    const mic = page.locator('[aria-label="Micrófono"]');
    while (!(await mic.isVisible())) {
      const skip = page.locator('[data-role="skip-speech"]:visible').first();
      if (await skip.count()) await skip.click().catch(() => null);
      await page.waitForTimeout(300);
    }
    for (let turno = 1; turno <= frases.length; turno += 1) {
      const reply = page.waitForResponse(r => r.url().includes('/message'));
      await mic.click();
      await reply;
      await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent === 'Tu turno', null, { timeout: 60000 });
    }
    await page.getByRole('tab', { name: /Hipótesis/ }).click();
    await page.fill('[data-role="hypothesis-input"]', `Hipótesis de ${nombre}`);
    await page.click('[data-role="add-hypothesis"]');
    await page.click('[data-role="diagnosis-button"]');
    await page.fill('[data-role="diagnosis-input"]', diagnostico);
    const finishPromise = page.waitForResponse(r => r.url().includes('/finish'));
    await page.click('[data-role="save-diagnosis"]');
    const finish = await (await finishPromise).json();
    await page.locator('[data-role="evaluation-panel"]').waitFor({ state: 'visible' });
    await page.waitForTimeout(300);
    await page.screenshot({ path: shot(`${nombre}_hoja`) });
    const aviso = await page.locator('[data-role="evaluation-saved"]').innerText();
    console.log(`${nombre}: inicio con sesión=${conToken} | puntaje ${finish.evaluation.score}% | attempt ${JSON.stringify(finish.attempt)}`);
    console.log(`  aviso en la hoja: ${aviso}`);
    await page.click('[data-role="close-evaluation"]');
    return finish.attempt;
  };

  const abrirHistorial = async nombre => {
    await page.click('[data-role="profile-toggle"]');
    await page.click('[data-role="open-history"]');
    const dialog = page.locator('[data-role="history-dialog"]');
    await page.waitForFunction(() => {
      const status = document.querySelector('[data-role="history-dialog"] .history-status');
      return status && !status.textContent.startsWith('Cargando');
    });
    await page.waitForTimeout(300);
    await page.screenshot({ path: shot(nombre) });
    const items = await dialog.locator('.history-item').allInnerTexts();
    console.log(`${nombre}: ${await dialog.locator('.history-status').innerText()}`);
    items.forEach((text, i) => console.log(`  ${i + 1}. ${text.replace(/\s*\n+\s*/g, ' | ')}`));
    const visibleCode = (await page.locator('body').innerText()).includes(CASO);
    await page.keyboard.press('Escape');
    return { items, visibleCode };
  };

  // 1. Invitado: la consulta se evalúa, pero no se guarda.
  const invitado = await consulta(PARCIAL, 'Diagnóstico del invitado', '1_invitado');

  // 2. Inicio de sesión con el alumno de prueba (mismo cliente de Supabase que usa la página).
  const login = await page.evaluate(async ({ email, password }) => {
    const client = await window.auth.ready;
    const { error } = await client.auth.signInWithPassword({ email, password });
    return error ? error.message : 'ok';
  }, credenciales);
  console.log('inicio de sesión del alumno de prueba:', login);

  // 3. Dos consultas con la sesión iniciada: se guardan.
  const primera = await consulta(COMPLETO, 'Reacción a tetraciclinas en estudio', '2_con_sesion_completa');
  const segunda = await consulta(PARCIAL, 'Diagnóstico parcial', '3_con_sesion_parcial');

  // 4. Historial desde el simulador y desde la portada.
  const enSimulador = await abrirHistorial('4_historial_simulador');
  await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });
  await page.locator('[data-role="auth-user"]').waitFor({ state: 'visible' });
  const enPortada = await abrirHistorial('5_historial_portada');

  console.log('\nRESUMEN');
  console.log('invitado guardado:', invitado?.saved, '| motivo:', invitado?.reason);
  console.log('consultas con sesión guardadas:', [primera, segunda].filter(a => a?.saved).length, 'de 2');
  console.log('consultas en el historial (simulador / portada):', enSimulador.items.length, '/', enPortada.items.length);
  console.log('código del caso visible en el historial:', enSimulador.visibleCode || enPortada.visibleCode);
  console.log('errores:', errors);
  await browser.close();
})();
