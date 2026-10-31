// Tarjeta PNG de cada caso de la suite HU-006, armada con su JSON real (resultados/<fase>/logs/HU006-XX.json):
// identidad, petición, código esperado y recibido, extracto de la respuesta y cada comprobación.
//
// Uso, desde la raíz del repositorio:
//   node pruebas/28_diagnostico_final/generar_tarjetas.cjs local_antes local_despues
// Deja resultados/<fase>/capturas/HU006-XX.png.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const BASE = path.resolve(__dirname, 'resultados');
const esc = text => String(text ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const corto = (text, n) => (String(text ?? '').length > n ? `${String(text).slice(0, n)}…` : String(text ?? ''));

function tarjeta(caso) {
  const pasos = (caso.pasos || []).map(p => {
    const ruta = (() => { try { return new URL(p.url).pathname; } catch { return p.url; } })();
    const ok = p.resultado === 'PASA';
    return `<tr><td>${esc(p.identidad)}</td><td><code>${esc(p.metodo)} ${esc(corto(ruta, 60))}</code><div class="d">${esc(p.descripcion)}</div>
      ${p.cuerpo_enviado ? `<div class="b">envía: <code>${esc(corto(JSON.stringify(p.cuerpo_enviado), 160))}</code></div>` : ''}</td>
      <td class="c">${esc((p.codigo_esperado || []).join(' o '))}</td><td class="c ${ok ? 'ok' : 'ko'}">${esc(p.codigo_recibido)}</td>
      <td><code class="r">${esc(corto(p.cuerpo_recibido, 220))}</code></td></tr>`;
  }).join('');
  const comprobaciones = (caso.comprobaciones || []).map(c =>
    `<li class="${c.resultado === 'PASA' ? 'ok' : 'ko'}"><b>${esc(c.resultado)}</b> ${esc(c.descripcion)}${c.detalle ? ` <span class="d">(${esc(corto(c.detalle, 120))})</span>` : ''}</li>`).join('');
  const pasa = caso.resultado === 'PASA';
  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
    body{font:14px/1.45 "Segoe UI",Arial,sans-serif;margin:0;padding:24px;background:#fff;color:#202124;width:1240px}
    .card{border:1px solid #dadce0;border-radius:10px;overflow:hidden}
    .head{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;background:${pasa ? '#e6f4ea' : '#fce8e6'}}
    .head h1{font-size:18px;margin:0} .head .m{color:#5f6368;font-size:13px}
    .res{font:700 18px Consolas,monospace;color:${pasa ? '#137333' : '#b3261e'}}
    .body{padding:14px 18px} table{border-collapse:collapse;width:100%;margin:8px 0}
    th,td{border:1px solid #e0e0e0;padding:6px 8px;text-align:left;vertical-align:top;font-size:13px}
    th{background:#f8f9fa} .c{text-align:center;font:700 14px Consolas,monospace} .ok{color:#137333} .ko{color:#b3261e}
    code{font:12px Consolas,monospace;word-break:break-all} .r{color:#3c4043} .d{color:#5f6368;font-size:12px} .b{margin-top:3px}
    ul{margin:6px 0 0;padding-left:18px;columns:2;column-gap:28px} li{margin:2px 0;break-inside:avoid;font-size:13px}
  </style></head><body><div class="card">
    <div class="head"><div><h1>${esc(caso.id)} · ${esc(caso.titulo)}</h1>
      <div class="m">Criterio ${esc(caso.criterio)} · esperado: ${esc(caso.resultado_esperado)}</div>
      <div class="m">Fase ${esc(caso.fase)} · ${esc(caso.servidor)} · commit ${esc(caso.commit)} · ${esc(caso.fecha)}</div></div>
      <div class="res">${esc(caso.resultado)}</div></div>
    <div class="body">
      <table><tr><th style="width:150px">Quién</th><th>Petición</th><th style="width:70px">Espera</th><th style="width:70px">Recibe</th><th style="width:360px">Respuesta (extracto)</th></tr>${pasos}</table>
      <b>Comprobaciones</b><ul>${comprobaciones}</ul>
      ${caso.error ? `<div class="d" style="margin-top:8px">Error: ${esc(corto(caso.error, 400))}</div>` : ''}
    </div></div></body></html>`;
}

(async () => {
  const fases = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1290, height: 800 } });
  for (const fase of fases) {
    const logs = path.join(BASE, fase, 'logs');
    const salida = path.join(BASE, fase, 'capturas');
    fs.mkdirSync(salida, { recursive: true });
    const archivos = fs.readdirSync(logs).filter(f => f.endsWith('.json')).sort();
    for (const archivo of archivos) {
      const caso = JSON.parse(fs.readFileSync(path.join(logs, archivo), 'utf8'));
      await page.setContent(tarjeta(caso));
      await page.locator('.card').screenshot({ path: path.join(salida, archivo.replace('.json', '.png')) });
    }
    console.log(`${fase}: ${archivos.length} tarjetas en ${salida}`);
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
