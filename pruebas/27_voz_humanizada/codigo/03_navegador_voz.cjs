// Voz humanizada en el navegador: un invitado inicia la simulación y escucha la presentación del caso y
// dos respuestas del paciente sin saltar nada. Se registra, frase por frase, si habló la voz neuronal
// (/api/voz) o la del navegador, cuánto tardó el audio en llegar y el silencio entre una frase y la siguiente.
//
// Uso (servidor con TTS_PROVIDER=edge y sesiones en memoria):
//   node pruebas/27_voz_humanizada/codigo/03_navegador_voz.cjs <carpeta de resultados>
// Sale con código 1 si alguna frase no usó la voz neuronal.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100';
const CASO = process.env.CASO || 'CIR-005';
const FRASES = ['¿Desde cuándo tiene el dolor?', '¿Ha tenido fiebre o vómitos?'];

(async () => {
  const outDir = path.resolve(process.argv[2] || 'pruebas/27_voz_humanizada/resultados');
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ args: ['--mute-audio', '--autoplay-policy=no-user-gesture-required'] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();

  await page.addInitScript(frases => {
    const t0 = performance.now();
    const ms = () => Math.round(performance.now() - t0);
    window.__voz = [];
    const log = (evento, detalle = '') => window.__voz.push({ t: ms(), evento, detalle });
    const fetchOriginal = window.fetch;
    window.fetch = async (url, options) => {
      if (String(url).includes('/api/voz')) {
        const { personaje, texto } = JSON.parse(options.body);
        log('pide_audio', `${personaje}: ${texto.slice(0, 60)}`);
        const response = await fetchOriginal(url, options);
        log('llega_audio', `HTTP ${response.status}`);
        return response;
      }
      return fetchOriginal(url, options);
    };
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      this.addEventListener('ended', () => log('fin_audio'), { once: true });
      log('suena_neuronal');
      return play.call(this);
    };
    if (window.speechSynthesis) {
      const speak = window.speechSynthesis.speak.bind(window.speechSynthesis);
      window.speechSynthesis.speak = utterance => { log('suena_navegador', utterance.text.slice(0, 60)); speak(utterance); };
    }
    window.__frases = [...frases];
    class FakeRecognition {
      start() {
        const transcript = window.__frases.shift() || '¿Algo más?';
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
  const errores = [];
  page.on('pageerror', e => errores.push(e.message));

  await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
  await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
  const mic = page.locator('[aria-label="Micrófono"]');
  await mic.waitFor({ state: 'visible', timeout: 300000 });
  for (const frase of FRASES) {
    await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent === 'Tu turno', null, { timeout: 120000 });
    await mic.click();
    await page.waitForTimeout(1500);
  }
  await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent === 'Tu turno', null, { timeout: 120000 });
  await page.screenshot({ path: path.join(outDir, '03_navegador_consulta.png') });
  const eventos = await page.evaluate(() => window.__voz);
  await browser.close();

  // Una frase = desde que se pide el audio hasta que termina de sonar.
  const frases = [];
  let actual = null;
  for (const e of eventos) {
    if (e.evento === 'pide_audio') { actual = { texto: e.detalle, pide: e.t }; frases.push(actual); }
    else if (actual && e.evento === 'llega_audio') { actual.llega = e.t; actual.http = e.detalle; }
    else if (actual && e.evento === 'suena_neuronal') actual.suena = e.t;
    else if (actual && e.evento === 'suena_navegador') actual.navegador = true;
    else if (actual && e.evento === 'fin_audio') actual.fin = e.t;
  }
  let fallos = 0;
  console.log(`Caso ${CASO} en ${BASE_URL}: ${frases.length} frases habladas\n`);
  frases.forEach((f, i) => {
    const neuronal = f.suena !== undefined && !f.navegador;
    fallos += !neuronal;
    const espera = f.suena !== undefined ? f.suena - f.pide : null;
    const silencio = i > 0 && frases[i - 1].fin !== undefined && f.suena !== undefined ? f.suena - frases[i - 1].fin : null;
    f.voz = neuronal ? 'neuronal' : 'navegador';
    f.espera_ms = espera;
    f.silencio_desde_la_anterior_ms = silencio;
    console.log(`${String(i + 1).padStart(2)}. [${f.voz}] espera ${espera ?? '-'} ms, silencio ${silencio ?? '-'} ms  ${f.texto}`);
  });
  const esperas = frases.map(f => f.espera_ms).filter(v => v !== null);
  const promedio = esperas.length ? Math.round(esperas.reduce((a, b) => a + b, 0) / esperas.length) : 0;
  console.log(`\nEspera promedio del audio: ${promedio} ms; máxima: ${Math.max(0, ...esperas)} ms`);
  console.log(`Errores de JavaScript: ${errores.length ? errores.join(' | ') : 'ninguno'}`);
  console.log(fallos || errores.length ? `Resultado: ${fallos} frase(s) sin voz neuronal` : 'Resultado: todas las frases con voz neuronal');
  fs.writeFileSync(path.join(outDir, '03_navegador_voz.json'), JSON.stringify({ base_url: BASE_URL, caso: CASO, fecha: new Date().toISOString(), frases, eventos, errores }, null, 2));
  process.exit(fallos || errores.length ? 1 : 0);
})().catch(error => { console.error(error); process.exit(1); });
