#!/usr/bin/env node
// Toma la captura PNG (página completa, 1440 px de ancho) de cada HTML de un manifiesto.
// Lo llama generar_capturas.py; usa el Chromium que ya instaló Playwright (no descarga navegadores).
//
// Uso: node pruebas/25_autorizacion_sesiones/fotografiar.cjs <manifiesto.json>
// El manifiesto es una lista de {"html": "<ruta>", "png": "<ruta>"}.
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');

(async () => {
  const items = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  let done = 0;
  for (const item of items) {
    await page.goto(pathToFileURL(item.html).href, { waitUntil: 'load' });
    await page.screenshot({ path: item.png, fullPage: true });
    done += 1;
  }
  await browser.close();
  console.log(`Capturas generadas: ${done}`);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
