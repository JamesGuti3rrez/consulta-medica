// UI y endpoints reales del servidor de evidencia; solo dispositivos/Auth/proveedores son controlados.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';

const root = 'pruebas/Sprint2';
const base = 'http://127.0.0.1:3027';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const results = [];
const save = (task, name, data) => {
  mkdirSync(`${root}/${task}/capturas`, { recursive: true });
  writeFileSync(`${root}/${task}/${name}.json`, JSON.stringify(data, null, 2));
};

async function context() {
  const ctx = await browser.newContext({ viewport: { width: 1480, height: 1050 }, colorScheme: 'light' });
  await ctx.route('https://fonts.googleapis.com/**', route => route.fulfill({ contentType: 'text/css', body: '' }));
  await ctx.addInitScript(() => {
    Object.defineProperty(window, 'speechSynthesis', { value: { cancel() {}, speak(u) { setTimeout(() => u.onend?.(), 1); } } });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', { value: class { constructor(text) { this.text = text; } } });
    window.SpeechRecognition = class {
      constructor() { window.__recognition = this; }
      start() {
        this.onstart?.();
        setTimeout(() => {
          const item = [{ transcript: window.__question }]; item.isFinal = true;
          this.onresult?.({ resultIndex: 0, results: [item] }); this.onend?.();
        }, 10);
      }
      stop() {} abort() {}
    };
  });
  return ctx;
}

async function openSimulation(caseId) {
  const ctx = await context();
  const page = await ctx.newPage();
  page.on('pageerror', e => { throw e; });
  await page.goto(base + '/simulacion.html?caso=' + caseId);
  await page.locator('[data-role="start-simulation"]').click();
  await page.locator('[data-role="diagnosis-button"]').waitFor({ state: 'visible' });
  return { ctx, page };
}

async function ask(page, question) {
  const previous = await page.locator('.chat-row').count();
  await page.evaluate(q => { window.__question = q; }, question);
  const pending = page.waitForResponse(r => r.url().endsWith('/message') && r.request().method() === 'POST');
  await page.locator('[aria-label="Micrófono"]').click();
  const response = await pending;
  assert.equal(response.status(), 200);
  const body = await response.json();
  await page.waitForFunction(({ previous, text }) => document.querySelectorAll('.chat-row').length >= previous + 2 &&
    [...document.querySelectorAll('.chat-text')].at(-1)?.textContent === text &&
    document.querySelector('[data-role="conversation-status"]').textContent === 'Tu turno', { previous, text: body.response });
  return body;
}

try {
  // TA-017: mismas rutas, usuario A positivo y B/sin credencial negativos.
  {
    const ctx = await context();
    const page = await ctx.newPage();
    const start = await ctx.request.post(base + '/api/ai/sessions', { headers: { Authorization: 'Bearer alumno-a' }, data: { case_id: 'MED-008' } });
    const sid = (await start.json()).session_id;
    const matrix = [];
    for (const [label, headers, expected] of [['Propietario A', { Authorization: 'Bearer alumno-a' }, 200],
      ['Otro alumno B', { Authorization: 'Bearer alumno-b' }, 404], ['Sin credenciales', {}, 401]]) {
      const r = await ctx.request.get(base + `/api/ai/sessions/${sid}`, { headers });
      assert.equal(r.status(), expected);
      matrix.push({ escenario: label, http: r.status(), resultado: 'PASA' });
    }
    save('TA-017', 'navegador', { tipo: 'HTTP real local, identidades controladas', casos: matrix, resultado: 'PASA' });
    await page.goto(base + '/evidencia-sprint2/ver_resultados.html?tarea=TA-017');
    await page.locator('[data-ready="true"]').waitFor();
    await page.screenshot({ path: `${root}/TA-017/capturas/http.png`, fullPage: true });
    results.push({ tarea: 'TA-017', resultado: 'PASA' });
    await ctx.close();
  }
  {
    const { ctx, page } = await openSimulation('MED-008');
    const reply = await ask(page, 'Dame un resumen con respuesta protegida de prueba');
    assert.equal(reply.blocked, true);
    assert.doesNotMatch(reply.response, /carcinoma/i);
    assert.match(await page.locator('[data-role="conversation-history"]').textContent(), /Eso no lo puedo responder/);
    save('TA-007', 'navegador', { resultado: 'PASA', bloqueo: true, respuesta: reply.response, tipo: 'Proveedor adversarial controlado, filtro y UI reales' });
    await page.locator('[data-role="conversation-history"]').screenshot({ path: `${root}/TA-007/capturas/bloqueo.png` });
    results.push({ tarea: 'TA-007', resultado: 'PASA' });
    await ctx.close();
  }
  {
    const ctx = await context();
    await ctx.route('**/js/auth.js', route => route.fulfill({ contentType: 'text/javascript', body: `
      window.auth={ready:Promise.resolve(null),api:async(p,o={})=>{const r=await fetch(p,{...o,headers:{...o.headers,Authorization:'Bearer docente-evidencia'}});if(!r.ok)throw Error('HTTP '+r.status);return r;},
      profile:async()=>({email:'evidencia@example.com',rol:'profesor',panel_docente:true})};` }));
    const page = await ctx.newPage();
    await page.goto(base + '/docente.html');
    await page.locator('#case-search').fill('MED-008');
    await page.locator('#case-list button').first().click();
    await page.getByText('Revisión automática de consistencia', { exact: true }).waitFor();
    save('TA-027', 'navegador', { resultado: 'PASA', tipo: 'UI y API docentes reales, Auth controlado', revision_visible: true });
    await page.locator('#case-dialog').screenshot({ path: `${root}/TA-027/capturas/consistencia.png` });
    results.push({ tarea: 'TA-027', resultado: 'PASA' });
    await ctx.close();
  }
  {
    const { ctx, page } = await openSimulation('MED-900');
    const turns = [];
    for (const question of ['Solicito hemograma', 'Solicito una tomografía cerebral', 'Solicito interconsulta con neurología', 'Solicito hemograma']) {
      const reply = await ask(page, question);
      turns.push({ agente: reply.agent, evidencias: reply.evidence_ids, resultado: 'PASA' });
      assert.equal(reply.clinical_evidence.length, 1);
    }
    assert.equal(await page.locator('[data-evidence-id="MED-900.laboratorio.hemograma"]').count(), 1);
    assert.equal(await page.locator('[data-evidence-id]').count(), 3);
    save('HU-004', 'navegador', { resultado: 'PASA', casos: turns, tablilla_sin_duplicados: true, tipo: 'Caso fixture, UI y API reales' });
    await page.locator('[data-role="conversation-history"]').screenshot({ path: `${root}/HU-004/capturas/agentes.png` });
    await page.locator('[data-tab="ficha"]').click();
    await page.locator('[data-role="record-history"]').screenshot({ path: `${root}/HU-004/capturas/tablilla.png` });
    results.push({ tarea: 'HU-004', resultado: 'PASA' });
    await ctx.close();
  }
  {
    const { ctx, page } = await openSimulation('MED-008');
    const first = await ask(page, 'Solicito hemograma');
    const second = await ask(page, 'Quiero los resultados del hemograma');
    assert.equal(first.data_source, 'sintetico_examen');
    assert.equal(first.response, second.response);
    assert.equal(second.synthetic_reused_ids.length, 1);
    assert.match(await page.locator('[data-role="conversation-history"]').textContent(), /sintético educativo/);
    save('EN-013', 'navegador', { resultado: 'PASA', tipo: 'Generador estructurado controlado, validador/API/UI reales',
      generacion: first.clinical_evidence, reuso: second.synthetic_reused_ids, validacion: first.exam_validation });
    await page.locator('[data-role="conversation-history"]').screenshot({ path: `${root}/EN-013/capturas/sintetico.png` });
    await page.locator('[data-tab="ficha"]').click();
    await page.locator('.synthetic-exam-badge').waitFor();
    await page.locator('[data-role="record-history"]').screenshot({ path: `${root}/EN-013/capturas/procedencia.png` });
    await page.locator('[data-role="diagnosis-button"]').click();
    const finish = page.waitForResponse(r => r.url().endsWith('/finish') && r.request().method() === 'POST');
    await page.locator('[data-role="save-diagnosis"]').click();
    const reportResponse = await finish;
    assert.equal(reportResponse.status(), 200);
    assert.equal((await reportResponse.json()).report.synthetic_exams.length, 1);
    await page.locator('[data-role="evaluation-revealed-summary"]').click();
    await page.locator('[data-role="evaluation-revealed"]').waitFor({ state: 'visible' });
    assert.match(await page.locator('[data-role="evaluation-revealed"]').textContent(), /Sintético · Revisión clínica pendiente/);
    await page.locator('[data-role="evaluation-revealed"]').screenshot({ path: `${root}/EN-013/capturas/reporte.png` });
    results.push({ tarea: 'EN-013', resultado: 'PASA' });
    await ctx.close();
  }
  writeFileSync(`${root}/navegador.json`, JSON.stringify(results, null, 2));
  for (const row of results) console.log(`[PASA] ${row.tarea}: navegador y HTTP real local, proveedor controlado.`);
} finally { await browser.close(); }
