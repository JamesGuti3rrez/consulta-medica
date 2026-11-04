// TA-020, avatar conversacional por rol (E2E). Recorre una consulta con turnos de cada rol y comprueba:
//   1. Indicador del personaje activo: escena (doctor o paciente hombre/mujer) y nombre del rol en el globo.
//   2. Estado de habla: «Hablando» mientras habla, «Listo» y «Tu turno» al terminar; video solo con voz sonando.
//   3. Degradación accesible: con «reducir movimiento» no hay video; si el navegador no reproduce el video queda la
//      imagen; el chat y el estado se anuncian a lectores de pantalla; la imagen describe al personaje.
// Uso (servidor con TTS_PROVIDER=edge en BASE_URL):
//   NAVEGADOR=chrome|msedge|firefox|webkit MOVIMIENTO=normal|reducido node pruebas/37_ta020_avatar_por_rol/probar_ta020.cjs <carpeta>
const fs = require('node:fs');
const path = require('node:path');
const { chromium, firefox, webkit } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100';
const CASO = process.env.CASO || 'CIR-005';
const NAVEGADOR = process.env.NAVEGADOR || 'chrome';
const MOVIMIENTO = process.env.MOVIMIENTO || 'normal';
const ANCHO = Number(process.env.ANCHO || 1440);
const ALTO = Number(process.env.ALTO || 1000);
const PREGUNTAS = [
  '¿Desde cuándo tiene el dolor?',
  'Realizo exploración física',
  'Solicito hemograma completo',
  'Solicito radiografía de tórax',
  'Solicito interconsulta con cardiología',
];

const lanzar = () => {
  if (NAVEGADOR === 'firefox') {
    return firefox.launch({ firefoxUserPrefs: { 'media.autoplay.default': 0, 'media.autoplay.blocking_policy': 0 } });
  }
  if (NAVEGADOR === 'webkit') return webkit.launch();
  return chromium.launch({ channel: NAVEGADOR, args: ['--mute-audio', '--autoplay-policy=no-user-gesture-required'] });
};

(async () => {
  const outDir = path.resolve(process.argv[2] || `pruebas/37_ta020_avatar_por_rol/resultados/${NAVEGADOR}_${MOVIMIENTO}`);
  fs.mkdirSync(outDir, { recursive: true });
  const comprobaciones = [];
  const comprobar = (descripcion, ok, detalle = '') => {
    comprobaciones.push({ descripcion, resultado: ok ? 'PASA' : 'FALLA', detalle: String(detalle) });
    console.log(`${ok ? 'PASA ' : 'FALLA'}  ${descripcion}${detalle !== '' ? `  (${detalle})` : ''}`);
  };
  const browser = await lanzar();
  const context = await browser.newContext({ viewport: { width: ANCHO, height: ALTO }, reducedMotion: MOVIMIENTO === 'reducido' ? 'reduce' : 'no-preference' });
  const page = await context.newPage();
  const errores = [];
  page.on('pageerror', error => errores.push(error.message));

  await page.addInitScript(preguntas => {
    window.__audios = new Set();
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function (...args) {
      if (this instanceof HTMLAudioElement) window.__audios.add(this);
      return play.apply(this, args);
    };
    window.__muestras = [];
    setInterval(() => {
      const avatar = document.querySelector('[data-role="scene-avatar"]');
      if (!avatar) return;
      const visible = sel => { const el = document.querySelector(sel); return Boolean(el && !el.classList.contains('hidden') && !el.hidden); };
      const doctor = visible('[data-role="doctor-bubble"]');
      const paciente = visible('[data-role="patient-bubble"]');
      window.__muestras.push({
        escena: avatar.dataset.scene,
        cambiando: avatar.classList.contains('is-switching'),
        src: avatar.currentSrc.split('/').pop(),
        alt: avatar.alt,
        globo: doctor ? document.querySelector('[data-role="doctor-name"]').textContent.replace(' (Voz sintetizada)', '') : paciente ? 'Paciente' : null,
        estado: (doctor ? document.querySelector('[data-role="doctor-status"]') : paciente ? document.querySelector('[data-role="patient-status"]') : null)?.textContent.trim() || null,
        video: [...document.querySelectorAll('.scene-video')].some(v => getComputedStyle(v).opacity !== '0'),
        // Sonando: en reproducción y con datos. Firefox deja currentTime en 0 unos 500 ms al empezar la primera frase
        // aunque el audio ya suena (intento 02), así que no basta con mirar currentTime.
        audio: [...window.__audios].some(a => !a.paused && !a.ended && (a.currentTime > 0 || a.readyState >= 3)),
        navegador: Boolean(window.speechSynthesis?.speaking),
        conversacion: document.querySelector('[data-role="conversation-status"]')?.textContent || '',
        t: Math.round(performance.now()),
        detalle: [...window.__audios].filter(a => !a.paused || a.currentTime > 0).slice(-1)
          .map(a => `paused=${a.paused} ended=${a.ended} t=${a.currentTime.toFixed(2)} rs=${a.readyState}`)[0] || '',
      });
    }, 40);
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
  }, PREGUNTAS);

  const caso = await (await fetch(`${BASE_URL}/api/caso?caso=${CASO}`)).json();
  const escenaPaciente = caso.patient?.sex === 'masculino' ? 'paciente-hombre' : 'paciente-mujer';
  console.log(`TA-020 en ${NAVEGADOR} ${browser.version()}, movimiento ${MOVIMIENTO}, caso ${CASO} (${caso.patient?.sex}), ventana ${ANCHO}x${ALTO}\n`);
  const esperarTurno = () => page.waitForFunction(
    () => document.querySelector('[data-role="conversation-status"]')?.textContent === 'Tu turno', null, { timeout: 300000 });
  const ultimoChat = () => page.evaluate(() => {
    const filas = [...document.querySelectorAll('.chat-row')];
    return filas.map(f => ({ nombre: f.querySelector('.chat-name strong').textContent, texto: f.querySelector('.chat-text').textContent }));
  });

  try {
    await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
    const h264 = await page.evaluate(() => document.createElement('video').canPlayType('video/mp4; codecs="avc1.640028"'));
    const accesible = await page.evaluate(() => ({
      chat: [document.querySelector('[data-role="conversation-history"]').getAttribute('role'), document.querySelector('[data-role="conversation-history"]').getAttribute('aria-live')],
      estado: [document.querySelector('[data-role="conversation-status"]').getAttribute('role'), document.querySelector('[data-role="conversation-status"]').getAttribute('aria-live')],
      alt: document.querySelector('[data-role="scene-avatar"]').alt,
    }));
    comprobar('el chat se anuncia a lectores de pantalla (role="log", aria-live)', accesible.chat.join() === 'log,polite', accesible.chat.join());
    comprobar('el estado de la conversación se anuncia (role="status", aria-live)', accesible.estado.join() === 'status,polite', accesible.estado.join());

    await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
    await page.locator('[data-role="doctor-bubble"]').waitFor({ state: 'visible', timeout: 60000 });
    await page.waitForTimeout(1500);
    await page.locator('[data-purpose="consultation-canvas-container"]').screenshot({ path: path.join(outDir, '1_doctor.png') });
    const mic = page.locator('[aria-label="Micrófono"]');
    await mic.waitFor({ state: 'visible', timeout: 300000 });
    await esperarTurno();

    // Turnos: cada intervención del estudiante y quién responde.
    const turnos = [];
    let previos = (await ultimoChat()).length;
    for (const [i, pregunta] of PREGUNTAS.entries()) {
      await page.evaluate(() => { window.__desde = window.__muestras.length; });
      await mic.click();
      // La captura se toma cuando ya habla quien responde (no a un tiempo fijo: antes salía sin globo, intento 04).
      await page.waitForFunction(() => /(hablando|respondiendo)$/.test(document.querySelector('[data-role="conversation-status"]')?.textContent || ''),
        null, { timeout: 120000 });
      await page.waitForTimeout(700);
      await page.locator('[data-purpose="consultation-canvas-container"]').screenshot({ path: path.join(outDir, `${i + 2}_turno_${i + 1}.png`) });
      await esperarTurno();
      await page.waitForTimeout(300);
      const chat = await ultimoChat();
      const nuevos = chat.slice(previos).filter(m => m.nombre !== 'Tú');
      previos = chat.length;
      const muestras = await page.evaluate(() => window.__muestras.slice(window.__desde));
      const hablando = muestras.filter(m => m.globo && m.estado === 'Hablando');
      turnos.push({ pregunta, responden: nuevos.map(m => m.nombre), globos: [...new Set(hablando.map(m => m.globo))],
        escenas: [...new Set(hablando.map(m => `${m.globo}:${m.escena}`))], estados: [...new Set(hablando.map(m => m.conversacion))] });
      console.log(`Turno ${i + 1} «${pregunta}»: responde ${nuevos.map(m => m.nombre).join(', ') || '(nadie)'}; globo ${turnos.at(-1).globos.join(', ')}`);
    }
    console.log('');
    const todas = await page.evaluate(() => window.__muestras);

    // 1. Indicador del personaje activo.
    const roles = [...new Set(turnos.flatMap(t => t.responden))];
    comprobar('cada turno muestra en el globo el mismo rol que responde en el chat',
      turnos.every(t => t.responden.every(r => t.globos.includes(r))), turnos.map(t => `${t.responden.join('+')}→${t.globos.join('+')}`).join('; '));
    comprobar('roles que hablaron en la consulta', roles.length >= 3, ['Doctor', ...roles.filter(r => r !== 'Doctor')].join(', '));
    const escenaOk = todas.filter(m => m.globo).every(m => (m.globo === 'Paciente' ? m.escena === escenaPaciente : m.escena === 'doctor'));
    comprobar(`escena por rol: el paciente es ${escenaPaciente}; doctor y servicios en la escena del doctor`, escenaOk);
    // La imagen y su texto alternativo cambian al final del fundido (180 ms): se miran fuera del cambio y desde que
    // la página cargó la primera imagen.
    const quietas = todas.filter(m => !m.cambiando);
    comprobar('la imagen que se ve es la del personaje en escena (archivo mostrado)',
      quietas.filter(m => m.src).every(m => m.src.startsWith(`${m.escena}-`)),
      [...new Set(quietas.filter(m => m.src).map(m => `${m.escena}:${m.src}`))].join(' | '));
    comprobar('la imagen describe al personaje en escena (texto alternativo)',
      quietas.every(m => (m.escena === 'doctor' ? /Doctor/.test(m.alt) : /Paciente/.test(m.alt))), [...new Set(quietas.map(m => m.alt))].join(' | '));

    // 2. Estado de habla.
    const conGlobo = todas.filter(m => m.globo);
    comprobar('mientras un rol habla su globo dice «Hablando»', conGlobo.some(m => m.estado === 'Hablando'));
    comprobar('el estado de la conversación nombra al rol que habla',
      turnos.every(t => t.responden.filter(r => r !== 'Paciente').every(r => t.estados.includes(`${r} hablando`))
        && (!t.responden.includes('Paciente') || t.estados.includes('Paciente respondiendo'))), turnos.map(t => t.estados.join('/')).join('; '));
    const final = todas.at(-1);
    comprobar('al terminar el turno: «Listo», «Tu turno» y sin video', final.conversacion === 'Tu turno' && !final.video && (!final.globo || final.estado === 'Listo'),
      `${final.estado} / ${final.conversacion}`);
    const conVideo = todas.filter(m => m.video);
    const conVoz = todas.filter(m => m.audio || m.navegador);
    console.log(`Muestras: ${todas.length}; con voz ${conVoz.length} (neuronal ${todas.filter(m => m.audio).length}, navegador ${todas.filter(m => m.navegador).length}); con video ${conVideo.length}; H.264: «${h264 || 'no'}»`);
    // Tramos seguidos de video sin voz: la boca se cierra 140 ms después del último sonido (SILENCE_HOLD) y algunos
    // motores tardan en marcar el audio como terminado, así que al final de una frase cabe un tramo corto.
    const tramos = [];
    const contexto = [];
    let largo = 0;
    todas.forEach((m, i) => {
      if (m.video && !m.audio && !m.navegador) largo += 1;
      else if (largo) {
        tramos.push(largo * 40);
        if (largo * 40 > 200) contexto.push(todas.slice(Math.max(0, i - largo - 4), i + 4));
        largo = 0;
      }
    });
    if (largo) tramos.push(largo * 40);
    comprobar('el video no sigue con la voz callada (tramos de 200 ms o menos, el cierre de la boca)',
      tramos.every(ms => ms <= 200), tramos.length ? `${tramos.length} tramos, el mayor de ${Math.max(...tramos)} ms` : 'ningún tramo');
    if (MOVIMIENTO === 'reducido') {
      comprobar('reducir movimiento: nunca hay video, queda la imagen y el estado «Hablando»', conVideo.length === 0 && conGlobo.some(m => m.estado === 'Hablando'), `${conVideo.length} muestras con video`);
    } else if (h264) {
      comprobar('la boca se mueve (video) mientras suena la voz', conVideo.length > 20, `${conVideo.length} muestras`);
    } else {
      comprobar('sin H.264: queda la imagen quieta y la consulta sigue', conVideo.length === 0, 'el navegador no reproduce MP4');
    }
    comprobar('sin errores de JavaScript en la página', errores.length === 0, errores.join(' | '));
    fs.writeFileSync(path.join(outDir, 'ta020_registro.json'), JSON.stringify({
      navegador: NAVEGADOR, version: browser.version(), movimiento: MOVIMIENTO, caso: CASO, ventana: `${ANCHO}x${ALTO}`, h264,
      fecha: new Date().toISOString(), comprobaciones, turnos, tramos_largos: contexto, muestras: { total: todas.length, con_voz: conVoz.length, con_video: conVideo.length },
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
