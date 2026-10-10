#!/usr/bin/env node
// Prueba de la fase 4: carga varios casos curados en /simulacion.html, guarda capturas en vista
// de escritorio/PC (1440 px) y comprueba que la pantalla no muestre información protegida.
//
// Uso (con el servidor en marcha):
//   node pruebas/_herramientas/capturar_frontend.cjs <carpeta_salida>
// Carga casos hasta haber mostrado el primero de cada especialidad (EME-001, GOB-003, CIR-005,
// PED-007, MED-008). Así cada ejecución captura los mismos casos y con los mismos nombres de archivo.
// Variables: BASE_URL (por defecto http://localhost:3000). Usa `playwright`, dependencia de desarrollo
// del proyecto (`npm install`); el navegador se instala una vez con `npx playwright install chromium`.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const CURATED_DIR = path.join(REPO_ROOT, 'data', 'cases', 'curated');
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const outDir = path.resolve(process.argv[2] || 'pruebas/04_frontend');

// Primer caso (por número) de cada especialidad, en el orden del lote.
function targetCases() {
  const first = new Map();
  fs.readdirSync(CURATED_DIR).filter(f => f.endsWith('.json')).sort((a, b) => a.slice(-8).localeCompare(b.slice(-8)))
    .forEach(f => {
      const record = JSON.parse(fs.readFileSync(path.join(CURATED_DIR, f), 'utf8'));
      if (!first.has(record.specialty)) first.set(record.specialty, record.case_id);
    });
  return [...first.values()];
}
const targets = targetCases();
const VIEWPORT = { width: 1440, height: 1100 };

function protectedTexts(caseId) {
  const record = JSON.parse(fs.readFileSync(path.join(CURATED_DIR, `${caseId}.json`), 'utf8'));
  const p = record.protected;
  return [
    p.diagnosis.name,
    ...(p.diagnosis.synonyms || []),
    ...(p.differentials || []).map(d => d.name),
    p.treatment_reference?.summary,
    ...(p.treatment_reference?.key_actions || []),
  ].filter(text => text && text.length >= 4);
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  const log = [];
  const say = line => { console.log(line); log.push(line); };
  let failures = 0;

  say(`URL: ${BASE_URL}/simulacion.html · ventana ${VIEWPORT.width}x${VIEWPORT.height} (escritorio)`);
  await page.goto(`${BASE_URL}/simulacion.html`, { waitUntil: 'networkidle' });
  const start = page.locator('[data-role="start-simulation"]');
  await start.waitFor({ state: 'visible' });
  await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
  const status = await page.evaluate(() => fetch('/api/status').then(r => r.json()));
  say(`GET /api/status → ${JSON.stringify(status)}`);
  await page.screenshot({ path: path.join(outDir, '01_simulador_catalogo_disponible.png') });

  say(`Casos a mostrar (primero de cada especialidad): ${targets.join(', ')}`);
  const seen = new Map();
  for (let attempt = 1; attempt <= 200 && seen.size < targets.length; attempt += 1) {
    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().endsWith('/api/caso')),
      start.click(),
    ]);
    const body = await response.json();
    await page.waitForFunction(alias => document.querySelector('[data-role="record-name"]').textContent === alias, body.patient.alias);
    if (!targets.includes(body.case_id) || seen.has(body.case_id)) continue;

    const screenText = await page.locator('body').innerText();
    const shown = await page.locator('[data-role="record-name"]').innerText();
    // Ni los textos protegidos ni el código del caso se muestran al estudiante.
    const leaks = [...protectedTexts(body.case_id), body.case_id].filter(t => screenText.toLowerCase().includes(t.toLowerCase()));
    const apiKeys = Object.keys(body).sort();
    const forbiddenKeys = apiKeys.filter(k => ['protected', 'on_request', 'source', 'provenance'].includes(k));
    const ok = leaks.length === 0 && forbiddenKeys.length === 0 && shown === body.patient.alias;
    if (!ok) failures += 1;
    const index = String(targets.indexOf(body.case_id) + 2).padStart(2, '0');
    const file = `${index}_ficha_${body.case_id}.png`;
    await page.screenshot({ path: path.join(outDir, file) });
    seen.set(body.case_id, file);
    say(`[${ok ? 'OK' : 'FALLA'}] intento ${attempt}: ${body.case_id} (${body.specialty}) · ficha "${shown}", `
      + `${body.patient.age_years} años · claves API ${JSON.stringify(apiKeys)} · `
      + `textos protegidos visibles: ${leaks.length} · captura ${file}`);
    leaks.forEach(t => say(`      visible: ${t}`));
  }

  // Caso por especialidad: la especialidad viaja en la URL del simulador.
  const specialtyPage = await browser.newPage({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  await specialtyPage.goto(`${BASE_URL}/simulacion.html?especialidad=pediatria`, { waitUntil: 'networkidle' });
  const specialtyStart = specialtyPage.locator('[data-role="start-simulation"]');
  await specialtyPage.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    const [response] = await Promise.all([
      specialtyPage.waitForResponse(r => r.url().includes('/api/caso')),
      specialtyStart.click(),
    ]);
    const body = await response.json();
    await specialtyPage.waitForFunction(alias => document.querySelector('[data-role="record-name"]').textContent === alias, body.patient.alias);
    const ok = body.specialty === 'pediatria' && response.url().endsWith('?especialidad=pediatria');
    if (!ok) failures += 1;
    say(`[${ok ? 'OK' : 'FALLA'}] ?especialidad=pediatria, carga ${attempt}: ${body.case_id} (${body.specialty})`);
  }
  await specialtyPage.screenshot({ path: path.join(outDir, `${String(targets.length + 2).padStart(2, '0')}_ficha_por_especialidad.png`) });

  const apiPage = await browser.newPage({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  await apiPage.goto(`${BASE_URL}/api/caso`);
  // Visor JSON de Chromium: activa "Pretty-print" si está disponible.
  await apiPage.locator('input[type="checkbox"]').first().check({ timeout: 2000 }).catch(() => {});
  const apiFile = `${String(targets.length + 3).padStart(2, '0')}_respuesta_api_caso.png`;
  await apiPage.screenshot({ path: path.join(outDir, apiFile), fullPage: true });
  say(`Respuesta cruda de GET /api/caso guardada en ${apiFile}`);

  await browser.close();
  if (seen.size < targets.length) {
    failures += 1;
    say(`[FALLA] faltaron casos: ${targets.filter(id => !seen.has(id)).join(', ')}`);
  }
  say(failures ? `RESULTADO: ${failures} comprobaciones fallaron.` : `RESULTADO: ${seen.size} casos, uno por especialidad, cargados sin información protegida.`);
  fs.writeFileSync(path.join(outDir, 'resultado_frontend.txt'), `${log.join('\n')}\n`, 'utf8');
  process.exit(failures ? 1 : 0);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
