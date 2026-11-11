// Fase 38: boca por sílaba y leve balanceo de los avatares (E2E). Recorre una consulta corta y comprueba:
//   1. La boca se mueve mientras suena la voz, con varias formas y a ritmo de sílaba (sin tiritar).
//   2. En silencio la boca está cerrada: se ve exactamente la imagen quieta.
//   3. Las capas de boca y cabeza son del personaje en escena y coinciden al píxel con la imagen.
//   4. La cabeza se balancea solo al hablar y vuelve a su sitio al terminar.
//   5. Con «reducir movimiento» no se anima nada y la consulta sigue.
// Uso (servidor en BASE_URL, por ejemplo uvicorn en el puerto 3100 con SESSION_STORE=memoria):
//   NAVEGADOR=chrome|msedge|firefox MOVIMIENTO=normal|reducido node pruebas/38_labios_por_silaba/probar_labios.cjs <carpeta>
const fs = require('node:fs');
const path = require('node:path');
const { chromium, firefox } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100';
const CASO = process.env.CASO || 'CIR-005';
const NAVEGADOR = process.env.NAVEGADOR || 'chrome';
const MOVIMIENTO = process.env.MOVIMIENTO || 'normal';
const ANCHO = Number(process.env.ANCHO || 1440);
const ALTO = Number(process.env.ALTO || 1000);
const PREGUNTAS = ['¿Desde cuándo tiene el dolor y cómo empezó?', 'Solicito hemograma completo'];
const MUESTRA_MS = 40;

const lanzar = () => (NAVEGADOR === 'firefox'
  ? firefox.launch({ firefoxUserPrefs: { 'media.autoplay.default': 0, 'media.autoplay.blocking_policy': 0 } })
  : chromium.launch({ channel: NAVEGADOR, args: ['--mute-audio', '--autoplay-policy=no-user-gesture-required'] }));

(async () => {
  const outDir = path.resolve(process.argv[2] || `pruebas/38_labios_por_silaba/resultados/${NAVEGADOR}_${MOVIMIENTO}`);
  fs.mkdirSync(outDir, { recursive: true });
  const comprobaciones = [];
  const comprobar = (descripcion, ok, detalle = '') => {
    comprobaciones.push({ descripcion, resultado: ok ? 'PASA' : 'FALLA', detalle: String(detalle) });
    console.log(`${ok ? 'PASA ' : 'FALLA'}  ${descripcion}${detalle !== '' ? `  (${detalle})` : ''}`);
  };
  const browser = await lanzar();
  const context = await browser.newContext({ viewport: { width: ANCHO, height: ALTO },
    reducedMotion: MOVIMIENTO === 'reducido' ? 'reduce' : 'no-preference' });
  const page = await context.newPage();
  const errores = [];
  page.on('pageerror', error => errores.push(error.message));

  await page.addInitScript(({ preguntas, cada }) => {
    window.__audios = new Set();
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function (...args) {
      if (this instanceof HTMLAudioElement) window.__audios.add(this);
      return play.apply(this, args);
    };
    window.__muestras = [];
    setInterval(() => {
      const avatar = document.querySelector('[data-role="scene-avatar"]');
      const face = document.querySelector('.scene-face');
      if (!avatar || !face) return;
      const boca = document.querySelector('.scene-mouth.is-on');
      const cabeza = face.querySelector('.scene-head');
      window.__muestras.push({
        t: Math.round(performance.now()),
        escena: avatar.dataset.scene,
        cambiando: avatar.classList.contains('is-switching'),
        boca: boca && getComputedStyle(face).opacity !== '0' ? boca.dataset.mouth : null,
        capaBoca: (boca || face.querySelector('.scene-mouth'))?.src.split('/').pop() || '',
        capaCabeza: cabeza?.src.split('/').pop() || '',
        balanceo: face.style.transform || '',
        audio: [...window.__audios].some(a => !a.paused && !a.ended && (a.currentTime > 0 || a.readyState >= 3)),
        navegador: Boolean(window.speechSynthesis?.speaking),
        conversacion: document.querySelector('[data-role="conversation-status"]')?.textContent || '',
      });
    }, cada);
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
  }, { preguntas: PREGUNTAS, cada: MUESTRA_MS });

  console.log(`Fase 38 en ${NAVEGADOR} ${browser.version()}, movimiento ${MOVIMIENTO}, caso ${CASO}, ventana ${ANCHO}x${ALTO}\n`);
  const esperarTurno = () => page.waitForFunction(
    () => document.querySelector('[data-role="conversation-status"]')?.textContent === 'Tu turno', null, { timeout: 300000 });

  try {
    await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
    await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
    await page.locator('[data-role="doctor-bubble"]').waitFor({ state: 'visible', timeout: 60000 });
    // Captura con la boca abierta, si se abre.
    if (MOVIMIENTO !== 'reducido') {
      await page.waitForFunction(() => document.querySelector('.scene-mouth.is-on'), null, { timeout: 20000 }).catch(() => {});
    } else {
      await page.waitForTimeout(1500);
    }
    await page.locator('[data-purpose="consultation-canvas-container"]').screenshot({ path: path.join(outDir, '1_doctor_hablando.png') });
    const mic = page.locator('[aria-label="Micrófono"]');
    await mic.waitFor({ state: 'visible', timeout: 300000 });
    await esperarTurno();
    for (const [i, pregunta] of PREGUNTAS.entries()) {
      await mic.click();
      await page.waitForFunction(() => /(hablando|respondiendo)$/.test(document.querySelector('[data-role="conversation-status"]')?.textContent || ''),
        null, { timeout: 120000 });
      await page.waitForTimeout(900);
      await page.locator('[data-purpose="consultation-canvas-container"]').screenshot({ path: path.join(outDir, `${i + 2}_turno_${i + 1}.png`) });
      await esperarTurno();
      console.log(`Turno ${i + 1} «${pregunta}» terminado`);
    }
    // Al terminar el turno el balanceo se apaga en ~0,5 s.
    await page.waitForTimeout(1200);
    const todas = await page.evaluate(() => window.__muestras);
    const capas = await page.evaluate(() => {
      const rect = el => { const r = el.getBoundingClientRect(); return [r.x, r.y, r.width, r.height].map(v => Math.round(v * 10) / 10); };
      const avatar = document.querySelector('[data-role="scene-avatar"]');
      return { imagen: rect(avatar), capas: [...document.querySelectorAll('.scene-face img')].map(rect),
        objectFit: [...document.querySelectorAll('.scene-face img')].map(img => getComputedStyle(img).objectFit),
        cargadas: [...document.querySelectorAll('.scene-face img')].every(img => img.complete && img.naturalWidth === 1280 && img.naturalHeight === 720),
        transform: document.querySelector('.scene-face').style.transform };
    });
    console.log('');

    const conVoz = todas.filter(m => m.audio || m.navegador);
    const conBoca = todas.filter(m => m.boca);
    console.log(`Muestras: ${todas.length}; con voz ${conVoz.length}; con la boca abierta ${conBoca.length}`);
    comprobar('sin errores de JavaScript en la página', errores.length === 0, errores.join(' | '));
    comprobar('las capas de boca y cabeza cargan a 1280x720', capas.cargadas);
    comprobar('las capas ocupan exactamente el rectángulo de la imagen, con el mismo object-fit',
      capas.capas.every(r => r.every((v, i) => Math.abs(v - capas.imagen[i]) <= 0.5)) && capas.objectFit.every(f => f === 'cover'),
      `imagen ${capas.imagen.join(',')}`);
    const fuera = todas.filter(m => !m.cambiando && m.capaCabeza && !(m.capaCabeza.startsWith(`${m.escena}-cabeza`) && m.capaBoca.startsWith(`${m.escena}-boca-`)));
    comprobar('las capas son siempre del personaje en escena', fuera.length === 0,
      fuera.length ? `${fuera.length} muestras, p. ej. ${fuera[0].escena}: ${fuera[0].capaCabeza} ${fuera[0].capaBoca}` : '');

    // Tramos seguidos de boca abierta sin voz: al final de una frase cabe el cierre (80 ms de espera más un
    // fotograma) y el retraso con que algunos motores marcan el audio como terminado.
    const tramos = [];
    let largo = 0;
    todas.forEach(m => {
      if (m.boca && !m.audio && !m.navegador) largo += 1;
      else if (largo) { tramos.push(largo * MUESTRA_MS); largo = 0; }
    });
    if (largo) tramos.push(largo * MUESTRA_MS);
    comprobar('en silencio la boca está cerrada (tramos sin voz de 200 ms o menos)', tramos.every(ms => ms <= 200),
      tramos.length ? `${tramos.length} tramos, el mayor de ${Math.max(...tramos)} ms` : 'ningún tramo');
    const final = todas.at(-1);
    comprobar('al terminar el turno: boca cerrada y cabeza en su sitio', !final.boca && !final.balanceo && !capas.transform,
      `${final.conversacion}; boca ${final.boca}; balanceo «${final.balanceo}»`);

    if (MOVIMIENTO === 'reducido') {
      comprobar('reducir movimiento: nunca se abre la boca ni se balancea la cabeza',
        conBoca.length === 0 && todas.every(m => !m.balanceo), `${conBoca.length} muestras con boca`);
    } else {
      const formas = [...new Set(conBoca.map(m => m.boca))];
      comprobar('la boca se mueve mientras suena la voz', conVoz.length > 0 && conBoca.length > conVoz.length * 0.3,
        `${conBoca.length} de ${conVoz.length} muestras con voz`);
      comprobar('usa varias formas de boca', formas.length >= 3, formas.join(', '));
      // Ritmo: cambios de forma por segundo de voz. La v1 por letra tiritaba a ~15 por segundo.
      let cambios = 0;
      for (let i = 1; i < todas.length; i++) if (todas[i].boca !== todas[i - 1].boca && (todas[i].audio || todas[i].navegador)) cambios += 1;
      const porSegundo = cambios / (conVoz.length * MUESTRA_MS / 1000);
      comprobar('cambia de forma a ritmo de sílaba, sin tiritar (de 2 a 9 cambios por segundo de voz)',
        porSegundo >= 2 && porSegundo <= 9, `${porSegundo.toFixed(1)} por segundo`);
      const conBalanceo = conVoz.filter(m => m.balanceo && m.balanceo !== 'none');
      comprobar('la cabeza se balancea mientras habla', conBalanceo.length > conVoz.length * 0.5,
        `${conBalanceo.length} de ${conVoz.length} muestras con voz`);
      const giros = conBalanceo.map(m => Math.abs(Number((m.balanceo.match(/rotate\((-?[\d.]+)deg\)/) || [])[1] || 0)));
      comprobar('el balanceo es leve (giro máximo de 1,5° o menos)', giros.length > 0 && Math.max(...giros) <= 1.5,
        giros.length ? `${Math.max(...giros).toFixed(2)}°` : '');
    }
    fs.writeFileSync(path.join(outDir, 'labios_registro.json'), JSON.stringify({
      navegador: NAVEGADOR, version: browser.version(), movimiento: MOVIMIENTO, caso: CASO, ventana: `${ANCHO}x${ALTO}`,
      fecha: new Date().toISOString(), comprobaciones, capas, tramos,
      muestras: { total: todas.length, con_voz: conVoz.length, con_boca: conBoca.length },
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
