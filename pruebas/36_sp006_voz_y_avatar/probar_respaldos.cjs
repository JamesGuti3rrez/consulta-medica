// SP-006, respaldos: la consulta sigue aunque falten el video o la voz.
//   sin_video   Los videos no cargan: se queda la imagen quieta, la voz neuronal suena y la consulta sigue.
//   solo_texto  Sin videos, sin /api/voz y sin voz del navegador: la consulta sigue solo con texto (globo y chat).
// Uso (servidor con TTS_PROVIDER=edge en BASE_URL):
//   RESPALDO=sin_video|solo_texto node pruebas/36_sp006_voz_y_avatar/probar_respaldos.cjs <carpeta de resultados>
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100';
const CASO = process.env.CASO || 'CIR-005';
const RESPALDO = process.env.RESPALDO || 'solo_texto';

(async () => {
  const outDir = path.resolve(process.argv[2] || `pruebas/36_sp006_voz_y_avatar/resultados/${RESPALDO}`);
  fs.mkdirSync(outDir, { recursive: true });
  const comprobaciones = [];
  const comprobar = (descripcion, ok, detalle = '') => {
    comprobaciones.push({ descripcion, resultado: ok ? 'PASA' : 'FALLA', detalle: String(detalle) });
    console.log(`${ok ? 'PASA ' : 'FALLA'}  ${descripcion}${detalle !== '' ? `  (${detalle})` : ''}`);
  };
  const browser = await chromium.launch({ channel: 'chrome', args: ['--mute-audio', '--autoplay-policy=no-user-gesture-required'] });
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
  const errores = [];
  page.on('pageerror', error => errores.push(error.message));
  const bloqueadas = { video: 0, voz: 0 };
  await page.route('**/*.mp4*', route => { bloqueadas.video += 1; return route.abort('connectionfailed'); });
  if (RESPALDO === 'solo_texto') {
    await page.route('**/api/voz?*', route => { bloqueadas.voz += 1; return route.abort('connectionfailed'); });
  }

  await page.addInitScript(sinVozNavegador => {
    if (sinVozNavegador) {
      delete window.speechSynthesis;
      delete Window.prototype.speechSynthesis;
    }
    window.__audios = new Set();
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function (...args) {
      if (this instanceof HTMLAudioElement) window.__audios.add(this);
      return play.apply(this, args);
    };
    window.__muestras = [];
    setInterval(() => {
      window.__muestras.push({
        video: [...document.querySelectorAll('.scene-video')].some(v => getComputedStyle(v).opacity !== '0'),
        audio: [...window.__audios].some(a => !a.paused && a.currentTime > 0),
        globo: [...document.querySelectorAll('[data-role="doctor-bubble"], [data-role="patient-bubble"]')]
          .some(el => !el.classList.contains('hidden')),
      });
    }, 50);
    window.__preguntas = ['¿Desde cuándo tiene el dolor?'];
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
  }, RESPALDO === 'solo_texto');

  const esperarTurno = () => page.waitForFunction(
    () => document.querySelector('[data-role="conversation-status"]')?.textContent === 'Tu turno', null, { timeout: 300000 });
  console.log(`Respaldo «${RESPALDO}», caso ${CASO} en ${BASE_URL}\n`);
  try {
    await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
    if (RESPALDO === 'solo_texto') {
      comprobar('el navegador queda sin voz propia', !(await page.evaluate(() => 'speechSynthesis' in window)));
    }
    const inicio = Date.now();
    await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
    await page.locator('[data-role="doctor-bubble"]').waitFor({ state: 'visible', timeout: 60000 });
    await page.waitForTimeout(800);
    await page.locator('[data-purpose="consultation-canvas-container"]').screenshot({ path: path.join(outDir, '1_presentacion.png') });
    await page.locator('[aria-label="Micrófono"]').waitFor({ state: 'visible', timeout: 300000 });
    await esperarTurno();
    const presentacion = ((Date.now() - inicio) / 1000).toFixed(1);
    await page.locator('[aria-label="Micrófono"]').click();
    await page.locator('[data-role="patient-bubble"]').waitFor({ state: 'visible', timeout: 120000 });
    await page.locator('[data-purpose="consultation-canvas-container"]').screenshot({ path: path.join(outDir, '2_paciente.png') });
    await esperarTurno();
    await page.waitForTimeout(500);

    const muestras = await page.evaluate(() => window.__muestras);
    const chat = await page.evaluate(() => [...document.querySelectorAll('.chat-row')].map(row => ({
      quien: row.className.replace('chat-row ', ''), texto: row.querySelector('.chat-text').textContent })));
    const imagen = await page.evaluate(() => {
      const img = document.querySelector('[data-role="scene-avatar"]');
      return { escena: img.dataset.scene, cargada: img.complete && img.naturalWidth > 0, src: img.currentSrc.split('/').pop() };
    });
    console.log(`Peticiones bloqueadas: videos ${bloqueadas.video}, voz neuronal ${bloqueadas.voz}`);
    console.log(`Presentación completa en ${presentacion} s; mensajes en el chat: ${chat.length}`);
    chat.forEach(m => console.log(`  ${m.quien.padEnd(12)} ${m.texto.slice(0, 80)}`));
    console.log('');

    comprobar('los videos se intentaron cargar y fallaron', bloqueadas.video > 0, `${bloqueadas.video} peticiones`);
    comprobar('nunca se ve un video: queda la imagen quieta', !muestras.some(m => m.video) && imagen.cargada, `${imagen.escena}, ${imagen.src}`);
    if (RESPALDO === 'sin_video') {
      comprobar('la voz neuronal suena igual', muestras.some(m => m.audio), `${muestras.filter(m => m.audio).length} muestras con audio`);
    } else {
      comprobar('la voz neuronal se intentó y no sonó nunca', bloqueadas.voz > 0 && !muestras.some(m => m.audio), `${bloqueadas.voz} peticiones`);
    }
    comprobar('el doctor presenta el caso completo en el chat', chat.filter(m => m.quien === 'chat-doctor').length >= 4,
      `${chat.filter(m => m.quien === 'chat-doctor').length} mensajes del doctor`);
    comprobar('cada frase se ve en el globo de diálogo', muestras.some(m => m.globo));
    comprobar('el paciente responde por texto', chat.some(m => m.quien === 'chat-patient' && m.texto.length > 5),
      chat.find(m => m.quien === 'chat-patient')?.texto.slice(0, 60));
    comprobar('sin errores de JavaScript en la página', errores.length === 0, errores.join(' | '));
    fs.writeFileSync(path.join(outDir, 'respaldo_registro.json'), JSON.stringify({
      respaldo: RESPALDO, caso: CASO, servidor: BASE_URL, fecha: new Date().toISOString(), bloqueadas,
      presentacion_s: Number(presentacion), comprobaciones, chat,
    }, null, 2));
  } catch (error) {
    comprobar('la prueba llega al final sin errores', false, error.message.split('\n')[0]);
    await page.screenshot({ path: path.join(outDir, 'error.png') }).catch(() => {});
  }
  await browser.close();
  const fallan = comprobaciones.filter(c => c.resultado === 'FALLA').length;
  console.log(`\n${comprobaciones.length - fallan} de ${comprobaciones.length} comprobaciones pasan`);
  process.exit(fallan ? 1 : 0);
})();
