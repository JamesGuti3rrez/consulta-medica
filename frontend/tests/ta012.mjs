// TA-012: navegador contra la API local REAL. No se simulan las respuestas de /finish.
// Requiere un servidor local sin servicios externos: puerto 3017 por defecto.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';

const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:3017';
const output = 'pruebas/TA-012';
mkdirSync(output + '/capturas', { recursive: true });
const matrix = [
  ['correcto', 'APENDICITIS AGUDA.', 'correct', 100],
  ['incorrecto', 'Meningitis', 'incorrect', 0],
  ['sinonimo', 'APENDICITIS', 'correct', 100],
  ['vacio', '', 'empty', 0],
  ['ambiguo', 'Apendicitis o meningitis', 'ambiguous', 0],
];
const browser = await chromium.launch({ headless: true, channel: process.env.TEST_BROWSER_CHANNEL || 'msedge' });
const results = [];
try {
  for (const [name, input, status, score] of matrix) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, colorScheme: 'light' });
    await context.route('https://fonts.googleapis.com/**', route => route.fulfill({ contentType: 'text/css', body: '' }));
    await context.addInitScript(() => {
      Object.defineProperty(window, 'speechSynthesis', { value: {
        cancel() {}, speak(utterance) { window.setTimeout(() => utterance.onend?.(), 1); },
      } });
      Object.defineProperty(window, 'SpeechSynthesisUtterance', { value: class { constructor(text) { this.text = text; } } });
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/simulacion.html?caso=CIR-101', { waitUntil: 'domcontentloaded' });
    await page.locator('[data-role="start-simulation"]').click();
    await page.locator('[data-role="diagnosis-button"]').waitFor({ state: 'visible', timeout: 20000 });
    assert.equal(await page.locator('[data-role="evaluation-diagnosis-result"]').isHidden(), true);
    assert.equal(await page.locator('[data-role="evaluation-reference"]').textContent(), '');
    await page.locator('[data-role="diagnosis-button"]').click();
    await page.locator('[data-role="diagnosis-input"]').fill(input);
    const finishedResponse = page.waitForResponse(response => response.url().endsWith('/finish') && response.request().method() === 'POST');
    await page.locator('[data-role="save-diagnosis"]').click();
    const response = await finishedResponse;
    assert.equal(response.status(), 200);
    const body = await response.json();
    const grade = body.diagnosis_evaluation;
    assert.equal(grade.status, status);
    assert.equal(grade.score, score);
    await page.locator('[data-role="evaluation-diagnosis-result"]').waitFor({ state: 'visible' });
    assert.match(await page.locator('[data-role="evaluation-diagnosis-score"]').textContent(), new RegExp(score + '/100'));
    assert.equal(await page.locator('[data-role="evaluation-diagnosis-reason"]').textContent(), grade.reason);
    await page.locator('[data-role="evaluation-diagnosis-result"]').screenshot({ path: output + '/capturas/' + name + '.png' });
    assert.deepEqual(errors, []);
    console.log('[PASA] ' + name.padEnd(10) + ' HTTP ' + response.status() + ' | ' + grade.status.padEnd(9) + ' | ' + grade.score + '/100 | interfaz y motivo correctos');
    results.push({ caso: name, entrada: input, http: response.status(), estado: grade.status,
      puntuacion: grade.score, motivo: grade.reason, interfaz: 'PASA', sin_fuga_previa: true });
    await context.close();
  }
  writeFileSync(output + '/navegador.json', JSON.stringify({ api_real_local: true, casos: results }, null, 2));
  console.log('TA-012: 5/5 casos verificados en navegador con /finish real; puntuación, motivo y ausencia de fuga previa correctos.');
} finally {
  await browser.close();
}

