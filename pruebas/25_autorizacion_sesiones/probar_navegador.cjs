// TA-017 en el navegador: el simulador real usa su credencial y otro navegador no puede abrir esa consulta.
//
// 1. Navegador del invitado: abre el simulador, inicia el caso, hace una pregunta y cierra la consulta. Se
//    registran las cabeceras que envía el simulador (credencial enmascarada) y los códigos que recibe.
// 2. Otro navegador: abre la URL de la sesión del invitado (sin credencial) y la pide con una credencial
//    bien formada que no es la suya.
// 3. El mismo invitado abre la URL de su sesión en una pestaña: el navegador no envía la cabecera, así que
//    tampoco ve nada (la credencial no viaja en la URL).
//
// Uso (servidor en BASE_URL, por defecto http://localhost:3000):
//   node pruebas/25_autorizacion_sesiones/probar_navegador.cjs pruebas/25_autorizacion_sesiones/capturas
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const CASO = process.env.CASO || 'MED-007';
// Preview protegido de Vercel: token de «Protection Bypass for Automation» (nunca se imprime).
const BYPASS = process.env.VERCEL_BYPASS
  ? { 'x-vercel-protection-bypass': process.env.VERCEL_BYPASS, 'x-vercel-set-bypass-cookie': 'true' }
  : undefined;
const mask = value => (value && value.length > 12 ? `${value.slice(0, 6)}…${value.slice(-4)}` : value ? '…' : '(ninguna)');

(async () => {
  const outDir = path.resolve(process.argv[2] || 'pruebas/25_autorizacion_sesiones/capturas');
  fs.mkdirSync(outDir, { recursive: true });
  const shot = name => path.join(outDir, `${name}.png`);
  const browser = await chromium.launch({ args: ['--mute-audio'] });
  const registro = { base_url: BASE_URL, caso: CASO, fecha: new Date().toISOString(), peticiones: [], otro_navegador: [] };
  let sessionId = null;
  let sessionToken = null;

  // ---- 1. Navegador del invitado
  const guest = await browser.newContext({ viewport: { width: 1440, height: 1000 }, extraHTTPHeaders: BYPASS });
  const page = await guest.newPage();
  await page.addInitScript(() => {
    class FakeRecognition {
      start() {
        const result = { resultIndex: 0, results: [Object.assign([{ transcript: '¿Desde cuándo empezaron las molestias?' }], { isFinal: true })] };
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
  page.on('response', async response => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith('/api/ai/sessions')) return;
    const headers = response.request().headers();
    let body = null;
    try { body = await response.json(); } catch { body = null; }
    if (url.pathname === '/api/ai/sessions' && body?.session_id) {
      sessionId = body.session_id;
      sessionToken = body.session_token || null;
    }
    registro.peticiones.push({
      metodo: response.request().method(),
      ruta: url.pathname,
      codigo: response.status(),
      cabecera_x_session_token: mask(headers['x-session-token']),
      cabecera_authorization: headers.authorization ? mask(headers.authorization) : '(ninguna)',
      session_token_recibido: body?.session_token ? mask(body.session_token) : undefined,
    });
  });

  await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
  await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
  const mic = page.locator('[aria-label="Micrófono"]');
  while (!(await mic.isVisible())) {
    const skip = page.locator('[data-role="skip-speech"]:visible').first();
    if (await skip.count()) await skip.click().catch(() => null);
    await page.waitForTimeout(300);
  }
  const reply = page.waitForResponse(r => r.url().includes('/message'));
  await mic.click();
  await reply;
  await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent === 'Tu turno', null, { timeout: 90000 });
  await page.screenshot({ path: shot('navegador_01_invitado_conversa') });

  await page.click('[data-role="diagnosis-button"]');
  await page.fill('[data-role="diagnosis-input"]', 'Diagnóstico del invitado (TA-017)');
  const finish = page.waitForResponse(r => r.url().includes('/finish'));
  await page.click('[data-role="save-diagnosis"]');
  await finish;
  await page.locator('[data-role="evaluation-panel"]').waitFor({ state: 'visible' });
  await page.waitForTimeout(500);
  await page.screenshot({ path: shot('navegador_02_invitado_cierra') });

  // ---- 2. Otro navegador (sin las cookies ni la memoria del invitado)
  const other = await browser.newContext({ viewport: { width: 1440, height: 900 }, extraHTTPHeaders: BYPASS });
  const intruder = await other.newPage();
  const sessionUrl = `${BASE_URL}/api/ai/sessions/${sessionId}`;
  const direct = await intruder.goto(sessionUrl);
  registro.otro_navegador.push({ prueba: 'abrir la URL de la sesión', codigo: direct.status(), cuerpo: await direct.text() });
  await intruder.goto(`${BASE_URL}/simulacion.html`, { waitUntil: 'domcontentloaded' });
  const forged = 'A'.repeat(21) + 'b'.repeat(22);
  const results = await intruder.evaluate(async ({ id, forged }) => {
    const out = [];
    for (const [label, headers, suffix] of [
      ['GET sin credencial', {}, ''],
      ['GET con una credencial bien formada que no es la suya', { 'X-Session-Token': forged }, ''],
      ['GET /events con esa credencial', { 'X-Session-Token': forged }, '/events'],
      ['POST /message con esa credencial', { 'X-Session-Token': forged, 'Content-Type': 'application/json' }, '/message'],
    ]) {
      const init = { headers, method: suffix === '/message' ? 'POST' : 'GET' };
      if (init.method === 'POST') init.body = JSON.stringify({ message: '¿Tiene alergias?' });
      const response = await fetch(`/api/ai/sessions/${id}${suffix}`, init);
      out.push({ label, status: response.status, body: await response.text() });
    }
    return out;
  }, { id: sessionId, forged });
  registro.otro_navegador.push(...results.map(r => ({ prueba: r.label, codigo: r.status, cuerpo: r.body })));
  const rows = [{ label: 'Abrir la URL de la sesión en la barra de direcciones', status: direct.status(), body: registro.otro_navegador[0].cuerpo }, ...results];
  await intruder.setContent(`<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
    body{font:16px/1.5 "Segoe UI",Arial,sans-serif;margin:32px;color:#202124}
    h1{font-size:24px;margin:0 0 6px} p{color:#5f6368;margin:0 0 18px}
    table{border-collapse:collapse;width:100%} th,td{border:1px solid #dadce0;padding:9px 12px;text-align:left;vertical-align:top}
    th{background:#f8f9fa} code{font-family:Consolas,monospace}
    .c{font:700 18px Consolas,monospace;color:#b3261e} .ok{color:#137333}
  </style></head><body>
  <h1>Otro navegador intenta abrir la consulta del invitado</h1>
  <p>Sesión <code>${sessionId}</code>. El otro navegador no tiene la credencial del invitado
  (<code>${mask(sessionToken)}</code>). Resultados reales, obtenidos con fetch desde ${BASE_URL}.</p>
  <table><tr><th>Intento</th><th>Código</th><th>Cuerpo de la respuesta</th></tr>
  ${rows.map(r => `<tr><td>${r.label}</td><td class="c ${r.status < 300 ? 'ok' : ''}">${r.status}</td><td><code>${r.body.replace(/</g, '&lt;')}</code></td></tr>`).join('')}
  </table></body></html>`);
  await intruder.screenshot({ path: shot('navegador_03_otro_navegador_denegado'), fullPage: true });

  // ---- 3. El invitado abre la URL de su propia sesión en una pestaña nueva
  const tab = await guest.newPage();
  const own = await tab.goto(sessionUrl);
  registro.url_propia_en_pestana = { codigo: own.status(), cuerpo: await own.text() };
  await tab.screenshot({ path: shot('navegador_04_url_de_la_sesion_sin_cabecera') });

  registro.errores_de_la_pagina = errors;
  fs.writeFileSync(path.join(outDir, 'navegador_registro.json'), JSON.stringify(registro, null, 2));
  console.log(JSON.stringify(registro, null, 2));
  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
