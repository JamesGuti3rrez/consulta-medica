// Escena de la consulta en el navegador (E2E): el doctor presenta el caso y, desde que empieza el interrogatorio,
// se ve al paciente (hombre o mujer, según el caso) con su globo de diálogo. Si el doctor o un servicio (laboratorio)
// entrega un hallazgo, aparece el doctor con su globo y al terminar el turno vuelve el paciente. Con el diálogo
// directo (TA-017) el doctor no repite la pregunta del estudiante.
//
// Uso (servidor en BASE_URL; CASO elige el paciente):
//   node pruebas/29_escena_consulta/probar_escena.cjs <carpeta de resultados>
// Sale con código 1 si alguna comprobación falla. Deja escena_registro.json y capturas de cada momento.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100';
const CASO = process.env.CASO || 'CIR-005';
const ANCHO = Number(process.env.ANCHO || 1440);
const ALTO = Number(process.env.ALTO || 1000);
const PREGUNTAS = ['¿Dónde le duele exactamente?', 'Realizo exploración física', 'Solicito hemograma'];
const ESCENA = '[data-purpose="consultation-canvas-container"]';

(async () => {
  const outDir = path.resolve(process.argv[2] || 'pruebas/29_escena_consulta/resultados/local');
  fs.mkdirSync(outDir, { recursive: true });
  const comprobaciones = [];
  const comprobar = (descripcion, ok, detalle = '') => {
    comprobaciones.push({ descripcion, resultado: ok ? 'PASA' : 'FALLA', detalle: String(detalle) });
    console.log(`${ok ? 'PASA ' : 'FALLA'}  ${descripcion}${detalle !== '' ? `  (${detalle})` : ''}`);
  };
  const browser = await chromium.launch({ args: ['--mute-audio', '--autoplay-policy=no-user-gesture-required'] });
  const page = await (await browser.newContext({ viewport: { width: ANCHO, height: ALTO } })).newPage();
  const errores = [];
  page.on('pageerror', error => errores.push(error.message));

  await page.addInitScript(preguntas => {
    // Cada cambio de escena o de globo queda registrado con quién habla y qué dice.
    window.__escena = [];
    const registrar = () => {
      const avatar = document.querySelector('[data-role="scene-avatar"]');
      const visible = role => {
        const el = document.querySelector(`[data-role="${role}"]`);
        return Boolean(el && !el.hidden && !el.classList.contains('hidden'));
      };
      const fila = {
        escena: avatar?.dataset.scene || null,
        globo: visible('doctor-bubble') ? 'doctor' : visible('patient-bubble') ? 'paciente' : null,
        texto: visible('doctor-bubble') ? document.querySelector('[data-role="doctor-text"]').textContent.trim()
          : visible('patient-bubble') ? document.querySelector('[data-role="patient-text"]').textContent.trim() : '',
      };
      const ultima = window.__escena.at(-1);
      if (!ultima || ultima.escena !== fila.escena || ultima.globo !== fila.globo || ultima.texto !== fila.texto) {
        window.__escena.push(fila);
      }
    };
    document.addEventListener('DOMContentLoaded', () => {
      registrar();
      new MutationObserver(registrar).observe(document.body, {
        subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['hidden', 'class', 'data-scene'],
      });
    });
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
  const sexo = caso.patient?.sex;
  const escenaPaciente = sexo === 'masculino' ? 'paciente-hombre' : 'paciente-mujer';
  console.log(`Caso ${CASO} (${sexo}) en ${BASE_URL}, ventana ${ANCHO}x${ALTO}\n`);

  // Sin el elemento de la escena (versión anterior) se informa «sin escena» y la prueba sigue.
  const escenaActual = () => page.evaluate(
    () => document.querySelector('[data-role="scene-avatar"]')?.dataset.scene || 'sin escena');
  const imagenCargada = () => page.evaluate(() => {
    const img = document.querySelector('[data-role="scene-avatar"]');
    return img ? { src: img.currentSrc, ancho: img.naturalWidth, alt: img.alt } : null;
  });
  const esperarTurno = () => page.waitForFunction(
    () => document.querySelector('[data-role="conversation-status"]')?.textContent === 'Tu turno', null, { timeout: 180000 });

  try {
    await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
    comprobar('antes de iniciar se ve al doctor', await escenaActual() === 'doctor', await escenaActual());
    const inicial = await imagenCargada();
    comprobar('la imagen del doctor carga', Boolean(inicial?.ancho) && /doctor-\d+\.webp/.test(inicial?.src || ''), inicial?.src);

    await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
    await page.locator('[data-role="doctor-bubble"]').waitFor({ state: 'visible', timeout: 60000 });
    await page.waitForTimeout(400);
    comprobar('presentación: doctor con su globo', await escenaActual() === 'doctor'
      && await page.locator('[data-role="doctor-bubble"]').isVisible()
      && await page.locator('[data-role="patient-bubble"]').isHidden());
    await page.locator(ESCENA).screenshot({ path: path.join(outDir, '1_presentacion_doctor.png') });

    const mic = page.locator('[aria-label="Micrófono"]');
    await mic.waitFor({ state: 'visible', timeout: 300000 });
    await esperarTurno();
    await page.waitForTimeout(400);
    comprobar(`al empezar el interrogatorio se ve al paciente (${escenaPaciente})`, await escenaActual() === escenaPaciente,
      await escenaActual());
    const paciente = await imagenCargada();
    comprobar('la imagen del paciente carga', Boolean(paciente?.ancho) && paciente.src.includes(escenaPaciente), paciente?.src);
    await page.locator(ESCENA).screenshot({ path: path.join(outDir, '2_interrogatorio_paciente.png') });

    // Turno 1: el paciente responde con su globo.
    await mic.click();
    await page.locator('[data-role="patient-bubble"]').waitFor({ state: 'visible', timeout: 120000 });
    await page.waitForTimeout(400);
    comprobar('pregunta al paciente: responde el paciente con su globo', await escenaActual() === escenaPaciente
      && await page.locator('[data-role="patient-bubble"]').isVisible()
      && await page.locator('[data-role="doctor-bubble"]').isHidden());
    await page.locator(ESCENA).screenshot({ path: path.join(outDir, '3_paciente_responde.png') });
    // En pantallas pequeñas el globo va debajo de la imagen y no tapa la cara.
    const cajas = await page.evaluate(() => {
      const caja = sel => document.querySelector(sel).getBoundingClientRect();
      return { imagen: caja('[data-role="scene-avatar"]'), globo: caja('[data-role="patient-bubble"]') };
    });
    if (ANCHO < 640) {
      comprobar('celular: el globo queda debajo de la imagen', cajas.globo.top >= cajas.imagen.bottom - 1,
        `globo ${Math.round(cajas.globo.top)} / imagen ${Math.round(cajas.imagen.bottom)}`);
    } else {
      comprobar('escritorio: el globo queda dentro de la escena, al lado del personaje',
        cajas.globo.top >= cajas.imagen.top && cajas.globo.right <= cajas.imagen.left + cajas.imagen.width * 0.45,
        `globo ${Math.round(cajas.globo.left)}-${Math.round(cajas.globo.right)} / imagen ${Math.round(cajas.imagen.left)}-${Math.round(cajas.imagen.right)}`);
    }
    await esperarTurno();

    // Turnos 2 y 3: hallazgos del doctor y del laboratorio. Mientras hablan se ve al doctor; después vuelve el paciente.
    for (const [numero, pregunta] of PREGUNTAS.slice(1).entries()) {
      const desde = await page.evaluate(() => window.__escena.length);
      await mic.click();
      await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]')?.textContent === 'Doctor hablando',
        null, { timeout: 120000 });
      await page.waitForTimeout(400);
      comprobar(`«${pregunta}»: mientras entrega el hallazgo se ve al doctor con su globo`, await escenaActual() === 'doctor'
        && await page.locator('[data-role="doctor-bubble"]').isVisible());
      await page.locator(ESCENA).screenshot({ path: path.join(outDir, `${4 + numero}_hallazgo_doctor.png`) });
      await esperarTurno();
      await page.waitForTimeout(400);
      comprobar(`«${pregunta}»: al terminar el turno vuelve el paciente`, await escenaActual() === escenaPaciente, await escenaActual());
      const turno = (await page.evaluate(() => window.__escena)).slice(desde);
      comprobar(`«${pregunta}»: el doctor no repite la pregunta del estudiante (TA-017)`,
        !turno.some(fila => fila.globo === 'doctor' && fila.texto === pregunta));
    }

    const linea = await page.evaluate(() => window.__escena);
    const conGlobo = linea.filter(fila => fila.globo);
    comprobar('ningún globo aparece sobre la imagen de otro personaje',
      conGlobo.every(fila => (fila.globo === 'doctor') === (fila.escena === 'doctor')),
      conGlobo.filter(fila => (fila.globo === 'doctor') !== (fila.escena === 'doctor')).map(f => `${f.escena}/${f.globo}`).join(', '));
    for (const nombre of ['doctor', 'paciente-hombre', 'paciente-mujer']) {
      const respuesta = await page.request.get(`${BASE_URL}/assets/avatars/${nombre}-800.webp`);
      comprobar(`imagen ${nombre} publicada`, respuesta.status() === 200 && respuesta.headers()['content-type'] === 'image/webp',
        `${respuesta.status()} ${respuesta.headers()['content-type']}`);
    }
    comprobar('sin errores de JavaScript en la página', errores.length === 0, errores.join(' | '));
    fs.writeFileSync(path.join(outDir, 'escena_registro.json'), JSON.stringify({
      caso: CASO, sexo, ventana: `${ANCHO}x${ALTO}`, servidor: BASE_URL, fecha: new Date().toISOString(),
      comprobaciones, linea_de_tiempo: linea,
    }, null, 2));
  } catch (error) {
    comprobar('la prueba llega al final sin errores', false, error.message.split('\n')[0]);
    await page.screenshot({ path: path.join(outDir, 'error.png') }).catch(() => {});
    fs.writeFileSync(path.join(outDir, 'escena_registro.json'), JSON.stringify({
      caso: CASO, sexo, ventana: `${ANCHO}x${ALTO}`, servidor: BASE_URL, fecha: new Date().toISOString(), comprobaciones,
      linea_de_tiempo: await page.evaluate(() => window.__escena).catch(() => []),
    }, null, 2));
  }
  await browser.close();
  const fallan = comprobaciones.filter(c => c.resultado === 'FALLA').length;
  console.log(`\n${comprobaciones.length - fallan} de ${comprobaciones.length} comprobaciones pasan`);
  process.exit(fallan ? 1 : 0);
})();
