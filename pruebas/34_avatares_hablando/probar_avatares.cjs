// Avatares que hablan (E2E): cada personaje tiene su imagen quieta y su video en bucle (LivePortrait). Mientras suena
// la voz neuronal se ve el video; en los silencios vuelve la imagen. La prueba toma una muestra de la escena cada 40 ms
// y comprueba que el video solo se vea con audio sonando, que alterne en las pausas y que sea el del personaje en escena.
//
// Uso (servidor con TTS_PROVIDER=edge en BASE_URL; CASO elige el paciente):
//   node pruebas/34_avatares_hablando/probar_avatares.cjs <carpeta de resultados>
// Usa Google Chrome instalado, el navegador de los estudiantes. Sale con código 1 si algo falla.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100';
const CASO = process.env.CASO || 'CIR-005';
const ANCHO = Number(process.env.ANCHO || 1440);
const ALTO = Number(process.env.ALTO || 1000);
const ESCENA = '[data-purpose="consultation-canvas-container"]';

(async () => {
  const outDir = path.resolve(process.argv[2] || 'pruebas/34_avatares_hablando/resultados/local');
  fs.mkdirSync(outDir, { recursive: true });
  const comprobaciones = [];
  const comprobar = (descripcion, ok, detalle = '') => {
    comprobaciones.push({ descripcion, resultado: ok ? 'PASA' : 'FALLA', detalle: String(detalle) });
    console.log(`${ok ? 'PASA ' : 'FALLA'}  ${descripcion}${detalle !== '' ? `  (${detalle})` : ''}`);
  };
  const browser = await chromium.launch({ channel: 'chrome', args: ['--mute-audio', '--autoplay-policy=no-user-gesture-required'] });
  const page = await (await browser.newContext({ viewport: { width: ANCHO, height: ALTO } })).newPage();
  const errores = [];
  page.on('pageerror', error => errores.push(error.message));

  await page.addInitScript(() => {
    // Los <audio> de la voz no están en el DOM: se anotan al reproducirse.
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
      const visibles = [...document.querySelectorAll('.scene-video')]
        .filter(video => getComputedStyle(video).opacity !== '0')
        .map(video => video.src.split('/').pop());
      window.__muestras.push({
        t: Math.round(performance.now()),
        escena: avatar.dataset.scene,
        cambiando: avatar.classList.contains('is-switching'),
        videos: visibles,
        audio: [...window.__audios].some(audio => !audio.paused && !audio.ended && audio.currentTime > 0),
        // Respaldo: si la voz neuronal falla habla la del navegador y la boca se mueve toda la frase.
        navegador: Boolean(window.speechSynthesis?.speaking),
        estado: document.querySelector('[data-role="conversation-status"]')?.textContent || '',
      });
    }, 40);
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
  });

  const caso = await (await fetch(`${BASE_URL}/api/caso?caso=${CASO}`)).json();
  const sexo = caso.patient?.sex;
  const escenaPaciente = sexo === 'masculino' ? 'paciente-hombre' : 'paciente-mujer';
  console.log(`Caso ${CASO} (${sexo}) en ${BASE_URL}, ventana ${ANCHO}x${ALTO}\n`);
  const esperarTurno = () => page.waitForFunction(
    () => document.querySelector('[data-role="conversation-status"]')?.textContent === 'Tu turno', null, { timeout: 300000 });
  // Cuenta las veces que el video aparece mientras suena el audio: más de una vez quiere decir que alterna en las pausas.
  const analizar = (muestras, escena) => {
    const conAudio = muestras.filter(m => m.audio);
    const conVideo = muestras.filter(m => m.videos.length);
    let apariciones = 0;
    muestras.forEach((m, i) => { if (m.videos.length && !(muestras[i - 1]?.videos.length)) apariciones += 1; });
    return {
      muestras: muestras.length,
      con_audio: conAudio.length,
      con_video: conVideo.length,
      apariciones,
      con_voz_navegador: muestras.filter(m => m.navegador).length,
      video_sin_audio: conVideo.filter(m => !m.audio && !m.navegador).length,
      video_ajeno: conVideo.filter(m => m.videos.length > 1 || m.videos[0] !== `${escena}-hablando.mp4` || m.escena !== escena).length,
      video_en_cambio: conVideo.filter(m => m.cambiando).length,
    };
  };

  try {
    for (const nombre of ['doctor', 'paciente-hombre', 'paciente-mujer']) {
      const video = await page.request.get(`${BASE_URL}/assets/avatars/${nombre}-hablando.mp4`);
      comprobar(`video ${nombre}-hablando.mp4 publicado`, video.status() === 200 && video.headers()['content-type'] === 'video/mp4',
        `${video.status()} ${video.headers()['content-type']} ${video.headers()['content-length']} bytes`);
    }

    await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
    await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
    await page.locator('[data-role="doctor-bubble"]').waitFor({ state: 'visible', timeout: 60000 });

    // Misma resolución y proporción: la imagen quieta y el video se superponen sin que se note el cambio.
    await page.waitForFunction(() => document.querySelector('.scene-video')?.readyState >= 1, null, { timeout: 30000 });
    // naturalWidth de un <img> con srcset viene corregido por la densidad: se mide el archivo elegido por separado.
    const medidas = await page.evaluate(async () => {
      const img = document.querySelector('[data-role="scene-avatar"]');
      const video = document.querySelector('.scene-video');
      const archivo = new Image();
      archivo.src = img.currentSrc;
      await archivo.decode();
      const caja = el => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
      return { archivo: img.currentSrc.split('/').pop(), imagen: [archivo.naturalWidth, archivo.naturalHeight],
        video: [video.videoWidth, video.videoHeight], caja_imagen: caja(img), caja_video: caja(video) };
    });
    comprobar('imagen quieta y video con la misma proporción 16:9',
      medidas.imagen[0] * 9 === medidas.imagen[1] * 16 && medidas.video[0] === 1280 && medidas.video[1] === 720,
      `${medidas.archivo} ${medidas.imagen.join('x')}, video ${medidas.video.join('x')}`);
    comprobar('el video ocupa exactamente el lugar de la imagen', medidas.caja_imagen.join() === medidas.caja_video.join(),
      `imagen ${medidas.caja_imagen.join(',')} / video ${medidas.caja_video.join(',')}`);

    // Capturas: con la boca en movimiento y con la imagen quieta (en una pausa).
    await page.waitForFunction(() => window.__muestras.at(-1)?.videos.length, null, { timeout: 60000 });
    await page.locator(ESCENA).screenshot({ path: path.join(outDir, '1_doctor_hablando.png') });
    await page.waitForFunction(() => { const m = window.__muestras.at(-1); return m?.audio && !m.videos.length; }, null, { timeout: 60000 });
    await page.locator(ESCENA).screenshot({ path: path.join(outDir, '2_doctor_pausa.png') });

    await page.locator('[aria-label="Micrófono"]').waitFor({ state: 'visible', timeout: 300000 });
    await esperarTurno();
    await page.waitForTimeout(400);
    const presentacion = await page.evaluate(() => window.__muestras.splice(0));
    const doctor = analizar(presentacion.filter(m => m.escena === 'doctor'), 'doctor');
    console.log('Presentación del doctor:', JSON.stringify(doctor));
    comprobar('presentación: suena la voz neuronal', doctor.con_audio > 25, `${doctor.con_audio} muestras con audio`);
    comprobar('presentación: se ve el video del doctor mientras habla', doctor.con_video > 10, `${doctor.con_video} muestras`);
    comprobar('presentación: el video alterna con la imagen en las pausas', doctor.apariciones >= 4, `${doctor.apariciones} apariciones`);
    comprobar('presentación: el video nunca se ve sin audio sonando', doctor.video_sin_audio <= 2, `${doctor.video_sin_audio} muestras`);
    comprobar('presentación: solo el video del doctor, nunca durante el cambio de personaje',
      doctor.video_ajeno === 0 && doctor.video_en_cambio === 0, `ajeno ${doctor.video_ajeno}, en cambio ${doctor.video_en_cambio}`);
    const enTurno = await page.evaluate(() => [...document.querySelectorAll('.scene-video')].filter(v => getComputedStyle(v).opacity !== '0').length);
    comprobar(`turno del estudiante: se ve al paciente quieto (${escenaPaciente})`,
      enTurno === 0 && await page.evaluate(() => document.querySelector('[data-role="scene-avatar"]').dataset.scene) === escenaPaciente);
    await page.locator(ESCENA).screenshot({ path: path.join(outDir, '3_paciente_quieto.png') });

    // El paciente responde con su video (hombre o mujer, según el caso).
    await page.locator('[aria-label="Micrófono"]').click();
    await page.locator('[data-role="patient-bubble"]').waitFor({ state: 'visible', timeout: 120000 });
    await page.waitForFunction(() => window.__muestras.at(-1)?.videos.length, null, { timeout: 60000 });
    await page.locator(ESCENA).screenshot({ path: path.join(outDir, '4_paciente_hablando.png') });
    await esperarTurno();
    await page.waitForTimeout(400);
    const respuesta = await page.evaluate(() => window.__muestras.splice(0));
    const paciente = analizar(respuesta.filter(m => m.escena === escenaPaciente), escenaPaciente);
    console.log('Respuesta del paciente:', JSON.stringify(paciente));
    comprobar('respuesta: se ve el video del paciente mientras habla', paciente.con_video > 5, `${paciente.con_video} muestras`);
    comprobar('respuesta: el video nunca se ve sin audio sonando', paciente.video_sin_audio <= 2, `${paciente.video_sin_audio} muestras`);
    comprobar(`respuesta: solo el video de ${escenaPaciente}`, paciente.video_ajeno === 0 && paciente.video_en_cambio === 0,
      `ajeno ${paciente.video_ajeno}, en cambio ${paciente.video_en_cambio}`);
    comprobar('al terminar la respuesta el paciente queda quieto', !respuesta.at(-1)?.videos.length);
    comprobar('sin errores de JavaScript en la página', errores.length === 0, errores.join(' | '));
    fs.writeFileSync(path.join(outDir, 'avatares_registro.json'), JSON.stringify({
      caso: CASO, sexo, ventana: `${ANCHO}x${ALTO}`, servidor: BASE_URL, fecha: new Date().toISOString(),
      comprobaciones, medidas, resumen: { doctor, paciente },
    }, null, 2));
  } catch (error) {
    comprobar('la prueba llega al final sin errores', false, error.message.split('\n')[0]);
    await page.screenshot({ path: path.join(outDir, 'error.png') }).catch(() => {});
    fs.writeFileSync(path.join(outDir, 'avatares_registro.json'), JSON.stringify({
      caso: CASO, sexo, servidor: BASE_URL, fecha: new Date().toISOString(), comprobaciones,
    }, null, 2));
  }
  await browser.close();
  const fallan = comprobaciones.filter(c => c.resultado === 'FALLA').length;
  console.log(`\n${comprobaciones.length - fallan} de ${comprobaciones.length} comprobaciones pasan`);
  process.exit(fallan ? 1 : 0);
})();
