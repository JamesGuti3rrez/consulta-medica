// Graba una consulta corta para el video de demostración: la presentación del doctor y una pregunta al paciente.
// Playwright graba la imagen sin sonido; por eso se guarda cada audio de la voz neuronal (/api/voz) y el instante en
// que empezó a sonar. Al inicio se muestra un destello magenta de 400 ms cuyo instante también se anota: así
// montar_video.py ubica cada audio en el video con la precisión de un fotograma.
// Uso: BASE_URL=http://localhost:3100 node pruebas/38_labios_por_silaba/grabar_video.cjs <carpeta>
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100';
const CASO = process.env.CASO || 'CIR-005';
const PREGUNTAS = (process.env.PREGUNTAS || '¿Desde cuándo tiene el dolor y cómo empezó?').split('|');
const ANCHO = 1280;
const ALTO = 800;

(async () => {
  const outDir = path.resolve(process.argv[2] || 'pruebas/38_labios_por_silaba/resultados/video');
  fs.rmSync(outDir, { recursive: true, force: true });
  fs.mkdirSync(path.join(outDir, 'audios'), { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', args: ['--autoplay-policy=no-user-gesture-required', '--mute-audio'] });
  const context = await browser.newContext({ viewport: { width: ANCHO, height: ALTO }, recordVideo: { dir: outDir, size: { width: ANCHO, height: ALTO } } });
  const page = await context.newPage();
  const errores = [];
  page.on('pageerror', error => errores.push(error.message));

  // Cada audio de la voz neuronal se guarda con el nombre de su URL (el número de orden).
  const audios = new Map();
  page.on('response', async response => {
    if (!response.url().includes('/api/voz?')) return;
    try {
      const archivo = `audio_${String(audios.size + 1).padStart(2, '0')}.mp3`;
      audios.set(response.url(), archivo);
      fs.writeFileSync(path.join(outDir, 'audios', archivo), await response.body());
    } catch (error) {
      errores.push(`audio no guardado: ${error.message}`);
    }
  });

  await page.addInitScript(({ preguntas }) => {
    window.__linea = { destello: null, sonidos: [] };
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function (...args) {
      if (this instanceof HTMLAudioElement && !this.__anotado) {
        this.__anotado = true;
        this.addEventListener('playing', () => window.__linea.sonidos.push({ url: this.src, inicio: Date.now(), evento: 'playing' }));
        this.addEventListener('pause', () => window.__linea.sonidos.push({ url: this.src, fin: Date.now(), evento: 'pause' }));
      }
      return play.apply(this, args);
    };
    window.__preguntas = [...preguntas];
    class FakeRecognition {
      start() {
        const transcript = window.__preguntas.shift() || '¿Algo más?';
        const result = { resultIndex: 0, results: [Object.assign([{ transcript }], { isFinal: true })] };
        setTimeout(() => this.onstart?.(), 50);
        setTimeout(() => this.onresult?.(result), 400);
        setTimeout(() => this.onend?.(), 700);
      }
      stop() { setTimeout(() => this.onend?.(), 50); }
      abort() { this.stop(); }
    }
    window.SpeechRecognition = FakeRecognition;
    window.webkitSpeechRecognition = FakeRecognition;
  }, { preguntas: PREGUNTAS });

  const esperarTurno = () => page.waitForFunction(
    () => document.querySelector('[data-role="conversation-status"]')?.textContent === 'Tu turno', null, { timeout: 300000 });
  await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
  // Destello de sincronía: se anota el instante del primer fotograma pintado con el destello.
  await page.evaluate(() => new Promise(resolve => {
    const capa = Object.assign(document.createElement('div'), { id: 'destello' });
    capa.style.cssText = 'position:fixed;inset:0;background:#ff00ff;z-index:2147483647';
    document.body.append(capa);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      window.__linea.destello = Date.now();
      setTimeout(() => { capa.remove(); resolve(); }, 400);
    }));
  }));
  await page.waitForTimeout(800);
  await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
  const mic = page.locator('[aria-label="Micrófono"]');
  await mic.waitFor({ state: 'visible', timeout: 300000 });
  await esperarTurno();
  for (const pregunta of PREGUNTAS) {
    await page.waitForTimeout(700);
    await mic.click();
    await page.waitForFunction(() => /(hablando|respondiendo)$/.test(document.querySelector('[data-role="conversation-status"]')?.textContent || ''),
      null, { timeout: 120000 });
    await esperarTurno();
    console.log(`Respondida: «${pregunta}»`);
  }
  await page.waitForTimeout(1500);
  const linea = await page.evaluate(() => {
    const r = document.querySelector('[data-role="scene-avatar"]').getBoundingClientRect();
    return { ...window.__linea, escena: [r.x, r.y, r.width, r.height].map(Math.round) };
  });
  linea.fin = Date.now();
  linea.sonidos = linea.sonidos.map(s => ({ ...s, archivo: audios.get(s.url) || null, url: s.url.replace(/^.*\/api/, '/api') }));
  const video = page.video();
  await context.close();
  await browser.close();
  const rutaVideo = await video.path();
  fs.renameSync(rutaVideo, path.join(outDir, 'pantalla.webm'));
  fs.writeFileSync(path.join(outDir, 'linea_de_tiempo.json'), JSON.stringify({ caso: CASO, base_url: BASE_URL, preguntas: PREGUNTAS, errores, ...linea }, null, 2));
  console.log(`Video en ${path.join(outDir, 'pantalla.webm')}; ${audios.size} audios; ${linea.sonidos.filter(s => s.evento === 'playing').length} inicios de voz; errores: ${errores.length}`);
})();
