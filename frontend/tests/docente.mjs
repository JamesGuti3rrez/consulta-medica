// Ejecutar con el servidor local: node frontend/tests/docente.mjs
// Supabase Auth y las respuestas de la API se simulan; no escribe en la base real.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:3017';
const cases = readdirSync('data/cases/curated').filter(name => name.endsWith('.json'))
  .map(name => JSON.parse(readFileSync('data/cases/curated/' + name, 'utf8')));
const initial = cases.length;
const selectedCase = cases.find(item => item.case_id === 'MED-101');
const example = JSON.parse(JSON.stringify(selectedCase).replaceAll('MED-101', 'MED-107'));
const userId = '1de2cbce-c52a-4c19-a9a0-ddfa89c2391e';
const metadata = () => ({
  total: cases.length, por_especialidad: Object.fromEntries([...new Set(cases.map(item => item.specialty))]
    .map(specialty => [specialty, cases.filter(item => item.specialty === specialty).length])),
  case_store: 'supabase', rag_backend: 'local',
  casos: cases.map(item => ({ case_id: item.case_id, titulo: item.title, especialidad: item.specialty,
    paciente: item.public.patient, diagnostico: item.protected.diagnosis.name,
    evidencias: item.on_request.length, fuente: item.source.dataset })),
});
const errors = [];
const browser = await chromium.launch({ headless: true, ...(process.env.TEST_BROWSER_CHANNEL ? { channel: process.env.TEST_BROWSER_CHANNEL } : {}) });
try {
  async function context(role, signedIn = true, viewport = { width: 1440, height: 1000 }, firstCatalogFailure = 0, syncFailure = false) {
    let catalogRequests = 0;
    let syncRequests = 0;
    const ctx = await browser.newContext({ viewport, colorScheme: 'light' });
    const user = { id: userId, email: 'docente@example.edu', user_metadata: { nombres: 'Docente', apellidos: 'Prueba' } };
    await ctx.route('**/vendor/supabase.js', route => route.fulfill({ contentType: 'text/javascript',
      body: 'let testSession=' + (signedIn ? JSON.stringify({ access_token: 'test-token', user }) : "JSON.parse(sessionStorage.getItem('test-auth-session') || 'null')") + ';' +
        'window.supabase={createClient:()=>({auth:{getSession:async()=>({data:{session:testSession}}),' +
        'onAuthStateChange:()=>({data:{subscription:{unsubscribe(){}}}}),signOut:async()=>({error:null}),' +
        'signInWithPassword:async()=>{testSession=' + JSON.stringify({ access_token: 'test-token', user }) + ';sessionStorage.setItem("test-auth-session",JSON.stringify(testSession));return {error:null};}}})};' }));
    await ctx.route('**/api/config', route => route.fulfill({ json: { auth: true, supabaseUrl: 'https://example.supabase.co', supabaseKey: 'public-test', history: false } }));
    await ctx.route('**/api/docente/**', async route => {
      assert.equal(route.request().headers().authorization, 'Bearer test-token');
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (path === '/api/docente/sesion') return route.fulfill({ json: { id: userId, email: user.email, rol: role, panel_docente: role !== 'alumno' } });
      if (role === 'alumno') return route.fulfill({ status: 403, json: { detail: 'Solo docentes' } });
      if (path === '/api/docente/rag/sincronizar') {
        syncRequests++;
        assert.deepEqual(route.request().postDataJSON(), {});
        if (syncFailure) return route.fulfill({ status: 503, json: { detail: 'No se pudieron actualizar las evidencias.' } });
        return route.fulfill({ json: { casos_sincronizados: cases.length, evidencias_indexadas: 500,
          lotes: 1, rag_backend: 'supabase_pgvector' } });
      }
      if (path === '/api/docente/casos') {
        catalogRequests++;
        if (catalogRequests === 1 && firstCatalogFailure) return route.fulfill({
          status: firstCatalogFailure, json: { detail: 'Fallo de carga simulado' },
        });
        return route.fulfill({ json: metadata() });
      }
      if (path.endsWith('/probar-rag')) return route.fulfill({ json: { agente: 'laboratorio', intencion: 'request_lab',
        temas: ['funcion_tiroidea'], evidencias_autorizadas: ['MED-101.lab.funcion_tiroidea'],
        resultados: [{ evidence_id: 'MED-101.lab.funcion_tiroidea', texto: 'TSH 24 mUI/L.', puntaje: 0.8 }],
        backend_simulador: 'local', backend_prueba: 'supabase_pgvector' } });
      if (path.startsWith('/api/docente/casos/')) {
        const caseData = cases.find(item => item.case_id === path.split('/').pop());
        const item = caseData.on_request.find(item => item.reveal_policy.owner === 'laboratorio') || caseData.on_request[0];
        return route.fulfill({ json: { caso: caseData, datos_adicionales: [{
          clave: 'vasos_agua_diarios', estado_revision: 'pendiente', contenido: { respuesta: 'Tomo seis vasos de agua al día.' },
          pregunta_origen: '¿Cuánta agua bebe?', modelo: 'modelo de prueba',
        }], evidencias_rag: [{ case_id: caseData.case_id, evidence_id: item.evidence_id, owner: item.reveal_policy.owner,
          category: item.category, requires: item.reveal_policy.requires, content: item.text,
          embedding_model: 'sha256-token-hash', updated_at: '2026-10-17T12:00:00Z' }],
        rag: { tabla: 'rag_evidencias', indexadas: 1, esperadas: caseData.on_request.length + 1,
          faltantes: ['MED-101.anamnesis.inicio_evolucion'], desactualizadas: [],
          por_categoria: { laboratorio: 1 }, por_propietario: { laboratorio: 1 } } } });
      }
      if (path === '/api/docente/importaciones/validar') return route.fulfill({ json: {
        valido: true, casos: [example], errores: [], avisos: [], archivo: 'ejemplo.json',
      } });
      if (path === '/api/docente/importaciones') {
        const payload = route.request().postDataJSON();
        if (!cases.some(item => item.case_id === payload.casos[0].case_id)) cases.push(payload.casos[0]);
        return route.fulfill({ json: { casos_insertados: 1, casos_existentes: 0, evidencias_indexadas: 14 } });
      }
      if (path === '/api/docente/plantilla') return route.fulfill({ contentType: 'application/json',
        headers: { 'Content-Disposition': 'attachment; filename="plantilla_casos.json"' }, body: JSON.stringify(example) });
      throw new Error('Petición inesperada: ' + path);
    });
    const page = await ctx.newPage();
    page.on('pageerror', error => errors.push(error.message));
    return { ctx, page, catalogRequests: () => catalogRequests, syncRequests: () => syncRequests };
  }
  const { ctx, page } = await context('profesor');
  await page.goto(base + '/docente.html');
  await page.locator('#total-cases').filter({ hasText: String(initial) }).waitFor();
  assert.equal(await page.locator('#case-list tr').count(), initial);
  await page.getByRole('button', { name: 'Pediatría 8' }).click();
  assert.equal(await page.locator('#case-list tr').count(), 8);
  await page.getByRole('button', { name: 'Actualizar todas las evidencias' }).click();
  await page.locator('#sync-all-status').filter({ hasText: initial + ' casos sincronizados' }).waitFor();
  assert.equal(await page.locator('#case-list tr').count(), 8);
  assert.equal(await page.getByRole('button', { name: 'Actualizar todas las evidencias' }).isEnabled(), true);
  mkdirSync('pruebas/27_panel_docente', { recursive: true });
  await page.screenshot({ path: 'pruebas/27_panel_docente/escritorio.png', fullPage: true });
  await page.getByRole('button', { name: 'Todos los casos ' + initial }).click();
  await page.locator('#case-search').fill('MED-101');
  assert.equal(await page.locator('#case-list tr').count(), 1);
  await page.getByRole('button', { name: 'Ver caso de Lucía Robles' }).click();
  await page.locator('#detail-content:not([hidden])').waitFor();
  await page.getByRole('tab', { name: 'Evidencias RAG' }).click();
  assert.match(await page.locator('#evidence-health').textContent(), /faltantes/);
  await page.locator('#probe-question').fill('Solicito función tiroidea');
  await page.getByRole('button', { name: 'Probar RAG' }).click();
  await page.locator('#probe-result').filter({ hasText: 'TSH 24' }).waitFor();
  await page.locator('#case-dialog').screenshot({ path: 'pruebas/27_panel_docente/evidencias.png' });
  await page.getByRole('tab', { name: 'Datos adicionales' }).click();
  assert.match(await page.locator('#additional-list').textContent(), /seis vasos/);
  await page.getByRole('button', { name: 'Cerrar detalle' }).click();
  await page.getByRole('button', { name: 'Importar casos' }).click();
  await page.locator('.dropzone').evaluate((element, content) => {
    const transfer = new DataTransfer();
    transfer.items.add(new File([content], 'ejemplo.json', { type: 'application/json' }));
    element.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: transfer }));
  }, JSON.stringify(example));
  assert.equal(await page.locator('#case-file').evaluate(input => input.files[0].name), 'ejemplo.json');
  await page.locator('#upload-section').screenshot({ path: 'pruebas/27_panel_docente/importacion.png' });
  await page.getByRole('button', { name: 'Leer y validar archivo' }).click();
  await page.locator('#preview:not([hidden])').waitFor();
  await page.getByRole('button', { name: 'Publicar en Supabase' }).click();
  await page.locator('#upload-status').filter({ hasText: '1 casos publicados' }).waitFor();
  await page.locator('#total-cases').filter({ hasText: String(initial + 1) }).waitFor();
  await ctx.close();

  const mobile = await context('administrativo', true, { width: 390, height: 844 });
  await mobile.page.goto(base + '/docente.html');
  await mobile.page.locator('#workspace:not([hidden])').waitFor();
  await mobile.page.screenshot({ path: 'pruebas/27_panel_docente/movil.png', fullPage: false });
  assert.equal(await mobile.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await mobile.ctx.close();
  const dark = await context('profesor');
  await dark.page.addInitScript(() => localStorage.setItem('tema', 'dark'));
  await dark.page.goto(base + '/docente.html');
  await dark.page.locator('#total-cases').filter({ hasText: String(cases.length) }).waitFor();
  assert.equal(await dark.page.locator('html').getAttribute('data-theme'), 'light');
  await dark.page.getByRole('button', { name: 'Cambiar a vista oscura' }).click();
  assert.equal(await dark.page.locator('html').getAttribute('data-theme'), 'dark');
  await dark.page.getByRole('button', { name: 'Cambiar a vista clara' }).click();
  assert.equal(await dark.page.evaluate(() => localStorage.getItem('tema')), 'dark');
  await dark.page.getByRole('button', { name: 'Cambiar a vista oscura' }).click();
  await dark.page.reload();
  await dark.page.locator('#total-cases').filter({ hasText: String(cases.length) }).waitFor();
  assert.equal(await dark.page.locator('html').getAttribute('data-theme'), 'dark');
  await dark.page.getByRole('button', { name: 'Pediatría 8' }).click();
  await dark.page.screenshot({ path: 'pruebas/27_panel_docente/oscuro.png', fullPage: true });
  await dark.ctx.close();
  const student = await context('alumno');
  await student.page.goto(base + '/docente.html');
  await student.page.getByRole('heading', { name: 'Acceso al Panel Doctor' }).waitFor();
  assert.equal(await student.page.locator('#workspace').isHidden(), true);
  await student.ctx.close();
  const guest = await context('alumno', false);
  await guest.page.goto(base + '/docente.html');
  await guest.page.getByRole('link', { name: 'Iniciar sesión' }).waitFor();
  assert.equal(await guest.page.locator('#workspace').isHidden(), true);
  await guest.ctx.close();
  const login = await context('profesor', false);
  await login.page.goto(base + '/index.html?cuenta=login');
  const loginForm = login.page.locator('[data-role="login-form"]');
  await loginForm.locator('[name="correo"]').fill('docente@example.edu');
  await loginForm.locator('[name="clave"]').fill('clave-simulada');
  await loginForm.locator('button[type="submit"]').click();
  await login.page.waitForURL('**/docente.html');
  await login.page.locator('#workspace:not([hidden])').waitFor();
  await login.page.goto(base + '/index.html');
  await login.page.locator('[data-role="profile-toggle"]').click();
  await login.page.getByRole('link', { name: 'Panel Doctor' }).click();
  await login.page.waitForURL('**/docente.html');
  await login.ctx.close();
  const recovery = await context('profesor', true, undefined, 503);
  await recovery.page.goto(base + '/docente.html');
  await recovery.page.locator('#total-cases').filter({ hasText: String(cases.length) }).waitFor({ timeout: 5000 });
  assert.equal(recovery.catalogRequests(), 2);
  assert.equal(await recovery.page.locator('#case-list tr').count(), cases.length);
  assert.equal(await recovery.page.locator('#catalog-panel').getAttribute('aria-busy'), 'false');
  assert.equal(await recovery.page.locator('#refresh').isEnabled(), true);
  await recovery.ctx.close();
  const forbidden = await context('profesor', true, undefined, 403);
  await forbidden.page.goto(base + '/docente.html');
  await forbidden.page.locator('#notice').filter({ hasText: 'Fallo de carga simulado' }).waitFor();
  assert.equal(forbidden.catalogRequests(), 1);
  assert.equal(await forbidden.page.locator('#case-list tr').count(), 0);
  await forbidden.ctx.close();
  const failedSync = await context('profesor', true, undefined, 0, true);
  await failedSync.page.goto(base + '/docente.html');
  await failedSync.page.locator('#total-cases').filter({ hasText: String(cases.length) }).waitFor();
  await failedSync.page.getByRole('button', { name: 'Actualizar todas las evidencias' }).click();
  await failedSync.page.locator('#sync-all-status').filter({ hasText: 'No se pudieron actualizar' }).waitFor();
  assert.equal(failedSync.syncRequests(), 1);
  assert.equal(await failedSync.page.getByRole('button', { name: 'Actualizar todas las evidencias' }).isEnabled(), true);
  await failedSync.ctx.close();
  assert.deepEqual(errors, []);
  console.log('Panel docente: login, menú, catálogo, filtros, detalle, RAG, carga, publicación, móvil y acceso verificados.');
} finally {
  await browser.close();
}

