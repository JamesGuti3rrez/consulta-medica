// HU-006 en el navegador (E2E): un invitado hace una consulta real, el reporte no existe antes de cerrarla, al
// cerrarla la hoja de evaluación muestra cada sección del reporte, un texto con HTML se ve como texto y otro
// navegador no puede pedir ese reporte.
//
// Uso (servidor en BASE_URL, por defecto http://localhost:3000):
//   node pruebas/26_reporte_final/probar_navegador.cjs pruebas/26_reporte_final/capturas
// Sale con código 1 si alguna comprobación falla. Deja navegador_registro.json y las capturas.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const CASO = process.env.CASO || 'EME-101';
const BYPASS = process.env.VERCEL_BYPASS
  ? { 'x-vercel-protection-bypass': process.env.VERCEL_BYPASS, 'x-vercel-set-bypass-cookie': 'true' }
  : undefined;
const FRASES = [
  '¿Cómo es el dolor y hacia dónde se va?',
  'Solicito un electrocardiograma',
  'Solicito una troponina',
  'Le indico aspirina 300 miligramos',
];
const HIPOTESIS = '<b>prueba</b> de texto';
const SECCIONES = {
  'evaluation-reference': 'Diagnóstico de referencia',
  'evaluation-key-ok': 'Preguntas clave obtenidas',
  'evaluation-key-missing': 'Preguntas clave que faltaron',
  'evaluation-tests-ok': 'Exámenes pedidos',
  'evaluation-differentials': 'Diagnósticos diferenciales',
  'evaluation-treatment-proposed': 'Tratamiento propuesto',
  'evaluation-treatment-reference': 'Tratamiento de referencia',
  'evaluation-treatment-actions': 'Acciones clave',
  'evaluation-revealed': 'Datos obtenidos',
};
const mask = value => (value && value.length > 12 ? `${value.slice(0, 6)}…${value.slice(-4)}` : value ? '…' : '(ninguna)');

(async () => {
  const outDir = path.resolve(process.argv[2] || 'pruebas/26_reporte_final/capturas');
  fs.mkdirSync(outDir, { recursive: true });
  const shot = name => path.join(outDir, `${name}.png`);
  const registro = { base_url: BASE_URL, caso: CASO, fecha: new Date().toISOString(), comprobaciones: [], peticiones: [], otro_navegador: [] };
  const comprobar = (descripcion, ok, detalle = '') => registro.comprobaciones.push({ descripcion, resultado: ok ? 'PASA' : 'FALLA', detalle });
  const browser = await chromium.launch({ args: ['--mute-audio'] });
  let sessionId = null;
  let sessionToken = null;

  // ---- 1. El invitado conversa: cada pulsación del micrófono dice la siguiente frase
  const guest = await browser.newContext({ viewport: { width: 1440, height: 1000 }, extraHTTPHeaders: BYPASS });
  const page = await guest.newPage();
  await page.addInitScript(frases => {
    window.__frases = [...frases];
    class FakeRecognition {
      start() {
        const transcript = window.__frases.shift() || '¿Algo más que quiera contarme?';
        const result = { resultIndex: 0, results: [Object.assign([{ transcript }], { isFinal: true })] };
        setTimeout(() => this.onstart?.(), 50);
        setTimeout(() => this.onresult?.(result), 500);
        setTimeout(() => this.onend?.(), 800);
      }
      stop() { setTimeout(() => this.onend?.(), 50); }
      abort() { this.stop(); }
    }
    window.SpeechRecognition = FakeRecognition;
    window.webkitSpeechRecognition = FakeRecognition;
  }, FRASES);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', async response => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith('/api/ai/sessions')) return;
    let body = null;
    try { body = await response.json(); } catch { body = null; }
    if (url.pathname === '/api/ai/sessions' && body?.session_id) {
      sessionId = body.session_id;
      sessionToken = body.session_token || null;
    }
    registro.peticiones.push({
      metodo: response.request().method(), ruta: url.pathname, codigo: response.status(),
      cabecera_x_session_token: mask(response.request().headers()['x-session-token']),
      trae_reporte: Boolean(body?.report),
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
  for (const frase of FRASES) {
    const reply = page.waitForResponse(r => r.url().includes('/message'), { timeout: 120000 });
    await mic.click();
    await reply;
    await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent === 'Tu turno', null, { timeout: 120000 });
    registro.peticiones.at(-1).frase = frase;
  }
  await page.screenshot({ path: shot('navegador_01_consulta') });

  // ---- 2. Antes de cerrar, el reporte no existe (409), aunque lo pida el propio invitado con su credencial
  const antes = await page.evaluate(async ({ id, token }) => {
    const response = await fetch(`/api/ai/sessions/${id}/report`, { headers: { 'X-Session-Token': token } });
    return { status: response.status, body: await response.text() };
  }, { id: sessionId, token: sessionToken });
  registro.reporte_antes_de_cerrar = antes;
  comprobar('antes de cerrar: 409', antes.status === 409, `${antes.status} ${antes.body}`);

  // ---- 3. Hipótesis con HTML y cierre
  await page.click('[data-tab="hipotesis"]');
  await page.fill('[data-role="hypothesis-input"]', HIPOTESIS);
  await page.click('[data-role="add-hypothesis"]');
  await page.click('[data-role="diagnosis-button"]');
  await page.fill('[data-role="diagnosis-input"]', 'Infarto agudo de miocardio');
  const finish = page.waitForResponse(r => r.url().includes('/finish'), { timeout: 120000 });
  await page.click('[data-role="save-diagnosis"]');
  const finished = await finish;
  const finishedBody = await finished.json();
  comprobar('el cierre trae el reporte', Boolean(finishedBody.report), `claves: ${Object.keys(finishedBody.report || {}).join(', ')}`);
  await page.locator('[data-role="evaluation-panel"]').waitFor({ state: 'visible' });
  await page.waitForTimeout(800);

  // ---- 4. Cada sección del reporte tiene contenido en la hoja
  for (const [role, nombre] of Object.entries(SECCIONES)) {
    const texto = ((await page.locator(`[data-role="${role}"]`).textContent().catch(() => '')) || '').trim();
    comprobar(`sección «${nombre}» con contenido`, texto.length > 0, texto.slice(0, 160));
  }
  const reference = (await page.locator('[data-role="evaluation-reference"]').innerText().catch(() => '')).trim();
  comprobar('diagnóstico de referencia igual al del reporte', reference.includes(finishedBody.report?.diagnosis?.reference || '#'), reference);
  const missingCount = await page.locator('[data-role="evaluation-key-missing"] li').count();
  comprobar('una fila por pregunta que faltó', missingCount === (finishedBody.report?.key_questions?.missing?.length ?? -1),
    `${missingCount} filas, ${finishedBody.report?.key_questions?.missing?.length} en el reporte`);
  const okCount = await page.locator('[data-role="evaluation-key-ok"] li').count();
  comprobar('una fila por pregunta obtenida', okCount === (finishedBody.report?.key_questions?.obtained?.length ?? -1),
    `${okCount} filas, ${finishedBody.report?.key_questions?.obtained?.length} en el reporte`);
  const sheet = await page.locator('[data-role="evaluation-panel"]').innerText();
  comprobar('la hipótesis con HTML se ve como texto', sheet.includes(HIPOTESIS), '');
  const inyectado = await page.locator('[data-role="evaluation-panel"] b').count();
  comprobar('no se creó ningún elemento <b> desde los datos', inyectado === 0, `elementos <b>: ${inyectado}`);
  comprobar('sin errores de JavaScript en la página', errors.length === 0, errors.join(' | '));
  const revelados = await page.locator('[data-role="evaluation-revealed"] li').allTextContents();
  const repetidos = revelados.filter(texto => { const [etiqueta, resto] = texto.split(/:\s(.*)/s); return resto?.startsWith(etiqueta); });
  comprobar('ningún dato revelado repite su etiqueta', repetidos.length === 0, repetidos.join(' | ').slice(0, 160));

  // Fotos: la hoja completa (con los pliegues abiertos) y cada sección.
  await page.evaluate(() => document.querySelectorAll('[data-role="evaluation-panel"] details').forEach(d => { d.open = true; }));
  await page.addStyleTag({ content: '[data-role="evaluation-panel"]{position:static!important;display:block!important}.clipboard-paper,.clipboard.report-card{max-height:none!important;height:auto!important;overflow:visible!important}' });
  await page.waitForTimeout(300);
  await page.locator('.clipboard.report-card').screenshot({ path: shot('navegador_02_hoja_completa') });
  let n = 3;
  for (const role of Object.keys(SECCIONES)) {
    const section = page.locator(`[data-role="${role}"]`).locator('xpath=ancestor::div[contains(@class,"sheet-section")][1]');
    if (await section.count()) {
      await section.screenshot({ path: shot(`navegador_${String(n).padStart(2, '0')}_${role.replace('evaluation-', '')}`) });
      n += 1;
    }
  }

  // ---- 5. Otro navegador no obtiene el reporte
  const other = await browser.newContext({ viewport: { width: 1440, height: 900 }, extraHTTPHeaders: BYPASS });
  const intruder = await other.newPage();
  await intruder.goto(`${BASE_URL}/simulacion.html`, { waitUntil: 'domcontentloaded' });
  const forged = 'A'.repeat(21) + 'b'.repeat(22);
  const results = await intruder.evaluate(async ({ id, forged }) => {
    const out = [];
    for (const [label, headers] of [['sin credencial', {}], ['con una credencial bien formada que no es la suya', { 'X-Session-Token': forged }]]) {
      const response = await fetch(`/api/ai/sessions/${id}/report`, { headers });
      out.push({ label, status: response.status, body: await response.text() });
    }
    return out;
  }, { id: sessionId, forged });
  registro.otro_navegador = results.map(r => ({ prueba: `GET /report ${r.label}`, codigo: r.status, cuerpo: r.body }));
  comprobar('otro navegador sin credencial: 401', results[0].status === 401, results[0].body);
  comprobar('otro navegador con credencial ajena: 404', results[1].status === 404, results[1].body);
  comprobar('ninguna respuesta del otro navegador trae el reporte', results.every(r => !r.body.includes('key_questions')));
  await intruder.setContent(`<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
    body{font:16px/1.5 "Segoe UI",Arial,sans-serif;margin:32px;color:#202124}
    h1{font-size:24px;margin:0 0 6px} p{color:#5f6368;margin:0 0 18px}
    table{border-collapse:collapse;width:100%} th,td{border:1px solid #dadce0;padding:9px 12px;text-align:left;vertical-align:top}
    th{background:#f8f9fa} code{font-family:Consolas,monospace} .c{font:700 18px Consolas,monospace;color:#b3261e}
  </style></head><body>
  <h1>Reporte final: quién puede pedirlo</h1>
  <p>Consulta <code>${sessionId}</code> del invitado (credencial <code>${mask(sessionToken)}</code>). Resultados reales con fetch desde ${BASE_URL}.</p>
  <table><tr><th>Quién lo pide</th><th>Código</th><th>Cuerpo</th></tr>
  <tr><td>El propio invitado, antes de cerrar la consulta</td><td class="c">${antes.status}</td><td><code>${antes.body.replace(/</g, '&lt;')}</code></td></tr>
  ${results.map(r => `<tr><td>Otro navegador, ${r.label}</td><td class="c">${r.status}</td><td><code>${r.body.replace(/</g, '&lt;')}</code></td></tr>`).join('')}
  </table></body></html>`);
  await intruder.screenshot({ path: shot(`navegador_${String(n).padStart(2, '0')}_quien_puede_pedirlo`), fullPage: true });

  registro.session_id = sessionId;
  registro.errores_de_la_pagina = errors;
  fs.writeFileSync(path.join(outDir, 'navegador_registro.json'), JSON.stringify(registro, null, 2));
  await browser.close();
  const fallos = registro.comprobaciones.filter(c => c.resultado !== 'PASA');
  for (const c of registro.comprobaciones) console.log(`${c.resultado}  ${c.descripcion}${c.detalle ? `  (${c.detalle.slice(0, 100)})` : ''}`);
  console.log(`\n${registro.comprobaciones.length - fallos.length} de ${registro.comprobaciones.length} comprobaciones pasan · sesión ${sessionId}`);
  process.exit(fallos.length ? 1 : 0);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
