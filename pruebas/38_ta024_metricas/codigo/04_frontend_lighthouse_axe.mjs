// TA-024 · Rendimiento y accesibilidad del frontend: Lighthouse (móvil y escritorio) y axe-core (WCAG 2.1 AA).
//
// Requisitos (una sola vez, no modifican package.json):
//   npm install --no-save lighthouse axe-core
//   npx playwright install chromium
//
// Uso (con el servidor corriendo):
//   node pruebas/38_ta024_metricas/codigo/04_frontend_lighthouse_axe.mjs
//   node pruebas/38_ta024_metricas/codigo/04_frontend_lighthouse_axe.mjs --base-url https://<tu-app>.vercel.app --etiqueta vercel
//
// Salida en resultados/: lighthouse/<pagina>_<modo>.json (informe completo; se abre en
// https://googlechrome.github.io/lighthouse/viewer/), lighthouse_resumen.csv, axe_resumen.csv y axe_detalle.json.
import { spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = dirname(fileURLToPath(import.meta.url));
const RESULTADOS = join(aqui, '..', 'resultados');
const arg = (nombre, defecto) => {
  const i = process.argv.indexOf(nombre);
  return i > -1 ? process.argv[i + 1] : defecto;
};
const BASE = arg('--base-url', 'http://localhost:3000').replace(/\/$/, '');
const ETIQUETA = arg('--etiqueta', 'local');
const SUFIJO = ETIQUETA === 'local' ? '' : `_${ETIQUETA}`;
const SOLO = arg('--solo', 'ambos'); // lighthouse | axe | ambos

const PAGINAS = [
  { nombre: 'portada', ruta: '/' },
  { nombre: 'simulacion', ruta: '/simulacion.html?especialidad=emergencias' },
  { nombre: 'docente', ruta: '/docente.html' },
  { nombre: 'grupos', ruta: '/grupos.html' },
  { nombre: 'privacidad', ruta: '/privacidad.html' },
];

let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch {
  console.error('Falta Playwright: ejecute npm install en la raíz del proyecto.');
  process.exit(1);
}
const CHROME = chromium.executablePath();
mkdirSync(join(RESULTADOS, 'lighthouse'), { recursive: true });

const csv = (filas) => {
  const campos = [...new Set(filas.flatMap((f) => Object.keys(f)))];
  const esc = (v) => (v === null || v === undefined ? '' : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v);
  return '﻿' + [campos.join(','), ...filas.map((f) => campos.map((c) => esc(f[c])).join(','))].join('\n') + '\n';
};

// ---------- Lighthouse ----------
const lighthouse = [];
if (SOLO !== 'axe') {
  for (const pagina of PAGINAS) {
    for (const modo of ['movil', 'escritorio']) {
      const salida = join(RESULTADOS, 'lighthouse', `${pagina.nombre}_${modo}${SUFIJO}.json`);
      const args = ['lighthouse', BASE + pagina.ruta, '--output=json', `--output-path=${salida}`, '--quiet',
        '--only-categories=performance,accessibility,best-practices,seo',
        '--chrome-flags=--headless=new --no-sandbox --disable-gpu'];
      if (modo === 'escritorio') args.push('--preset=desktop');
      process.stdout.write(`Lighthouse ${pagina.nombre} (${modo})... `);
      const r = spawnSync('npx', args, { shell: true, encoding: 'utf8', env: { ...process.env, CHROME_PATH: CHROME } });
      let informe;
      try {
        informe = JSON.parse(readFileSync(salida, 'utf8'));
      } catch {
        console.log('FALLÓ', (r.stderr || '').split('\n').slice(-3).join(' '));
        continue;
      }
      const a = informe.audits;
      const cat = informe.categories;
      const fila = {
        etiqueta: ETIQUETA, pagina: pagina.nombre, modo,
        rendimiento: Math.round((cat.performance?.score ?? 0) * 100),
        accesibilidad: Math.round((cat.accessibility?.score ?? 0) * 100),
        buenas_practicas: Math.round((cat['best-practices']?.score ?? 0) * 100),
        seo: Math.round((cat.seo?.score ?? 0) * 100),
        fcp_ms: Math.round(a['first-contentful-paint']?.numericValue ?? 0),
        lcp_ms: Math.round(a['largest-contentful-paint']?.numericValue ?? 0),
        tbt_ms: Math.round(a['total-blocking-time']?.numericValue ?? 0),
        cls: Number((a['cumulative-layout-shift']?.numericValue ?? 0).toFixed(3)),
        speed_index_ms: Math.round(a['speed-index']?.numericValue ?? 0),
        peso_total_kb: Math.round((a['total-byte-weight']?.numericValue ?? 0) / 1024),
      };
      lighthouse.push(fila);
      console.log(`R ${fila.rendimiento} · A ${fila.accesibilidad} · BP ${fila.buenas_practicas} · SEO ${fila.seo} · LCP ${fila.lcp_ms} ms`);
    }
  }
  writeFileSync(join(RESULTADOS, `lighthouse_resumen${SUFIJO}.csv`), csv(lighthouse));
}

// ---------- axe-core ----------
if (SOLO !== 'lighthouse') {
  let axePath;
  try {
    axePath = require.resolve('axe-core/axe.min.js');
  } catch {
    console.error('Falta axe-core: ejecute  npm install --no-save lighthouse axe-core');
    process.exit(1);
  }
  const navegador = await chromium.launch();
  const resumenAxe = [];
  const detalle = {};
  for (const pagina of PAGINAS) {
    for (const [modo, viewport] of [['movil', { width: 390, height: 844 }], ['escritorio', { width: 1440, height: 900 }]]) {
      const contexto = await navegador.newContext({ viewport });
      const p = await contexto.newPage();
      await p.goto(BASE + pagina.ruta, { waitUntil: 'networkidle' });
      await p.waitForTimeout(1500);
      await p.addScriptTag({ path: axePath });
      const r = await p.evaluate(() => window.axe.run(document, {
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] },
      }));
      const porImpacto = { critical: 0, serious: 0, moderate: 0, minor: 0 };
      for (const v of r.violations) porImpacto[v.impact ?? 'minor'] += v.nodes.length;
      resumenAxe.push({
        etiqueta: ETIQUETA, pagina: pagina.nombre, modo,
        reglas_violadas: r.violations.length, reglas_superadas: r.passes.length,
        nodos_critical: porImpacto.critical, nodos_serious: porImpacto.serious,
        nodos_moderate: porImpacto.moderate, nodos_minor: porImpacto.minor,
        reglas: r.violations.map((v) => v.id).join(' '),
      });
      detalle[`${pagina.nombre}_${modo}`] = r.violations.map((v) => ({
        regla: v.id, impacto: v.impact, descripcion: v.help, ayuda: v.helpUrl, wcag: v.tags.filter((t) => t.startsWith('wcag')),
        nodos: v.nodes.map((n) => n.target.join(' ')),
      }));
      console.log(`axe ${pagina.nombre} (${modo}): ${r.violations.length} reglas violadas, ${r.passes.length} superadas`);
      await contexto.close();
    }
  }
  await navegador.close();
  writeFileSync(join(RESULTADOS, `axe_resumen${SUFIJO}.csv`), csv(resumenAxe));
  writeFileSync(join(RESULTADOS, `axe_detalle${SUFIJO}.json`), JSON.stringify(detalle, null, 2));
}
console.log(`Guardado en ${RESULTADOS}`);
