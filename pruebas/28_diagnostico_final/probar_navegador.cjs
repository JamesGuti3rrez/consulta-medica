// HU-006 en el navegador (E2E): proponer y registrar el diagnóstico final en el simulador real.
//
// Parte 1, invitado: el diagnóstico es obligatorio y se valida antes de enviar (sin petición al servidor); hay un
// paso de confirmación que se puede cancelar para seguir en la consulta; si el servidor rechaza (422) o falla (503)
// la consulta sigue abierta y se puede reintentar; el doble clic en «Confirmar» envía una sola petición.
// Parte 2, alumno con sesión (usuario temporal de Supabase Auth, borrado al final): el cierre muestra el número de
// intento registrado y la segunda consulta del mismo caso es el intento 2.
//
// Uso (servidor en BASE_URL con SESSION_STORE=memoria; el .env con Supabase para crear el usuario temporal):
//   node pruebas/28_diagnostico_final/probar_navegador.cjs pruebas/28_diagnostico_final/capturas
// Sale con código 1 si alguna comprobación falla. Deja navegador_registro.json y las capturas.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100';
const CASO = process.env.CASO || 'EME-101';
const DIAGNOSTICO = 'Síndrome coronario agudo.\nJustificación: dolor opresivo irradiado al brazo izquierdo.';
const MENSAJES = {
  vacio: 'Escribe tu diagnóstico final antes de cerrar la consulta.',
  letras: 'El diagnóstico debe tener al menos 3 letras.',
  marcado: 'El diagnóstico no puede contener los signos < ni >.',
  noRegistrado: 'No se pudo registrar tu diagnóstico. La consulta sigue abierta: inténtalo de nuevo.',
};

function leerEnv() {
  const env = {};
  const archivo = path.resolve(__dirname, '..', '..', '.env');
  if (!fs.existsSync(archivo)) return env;
  for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^([A-Z_]+)=(.*)$/);
    if (m) env[m[1]] = m[2].replace(/^['"]|['"]$/g, '');
  }
  return env;
}

const outDir = path.resolve(process.argv[2] || 'pruebas/28_diagnostico_final/capturas');
const registro = { base_url: BASE_URL, caso: CASO, fecha: new Date().toISOString(), comprobaciones: [], finish: [] };
const comprobar = (descripcion, ok, detalle = '') => {
  registro.comprobaciones.push({ descripcion, resultado: ok ? 'PASA' : 'FALLA', detalle: String(detalle) });
};
const errors = [];
let browser = null;

// Imprime y guarda lo comprobado; también si la prueba se detuvo a mitad (antes del cambio, por ejemplo).
function terminar(error) {
  if (error) comprobar('la prueba llegó hasta el final', false, error.message.split('\n')[0]);
  registro.errores_de_la_pagina = errors;
  fs.writeFileSync(path.join(outDir, 'navegador_registro.json'), JSON.stringify(registro, null, 2));
  const fallos = registro.comprobaciones.filter(c => c.resultado !== 'PASA');
  for (const c of registro.comprobaciones) console.log(`${c.resultado}  ${c.descripcion}${c.detalle ? `  (${c.detalle.slice(0, 90)})` : ''}`);
  console.log(`\n${registro.comprobaciones.length - fallos.length} de ${registro.comprobaciones.length} comprobaciones pasan`);
  return fallos.length ? 1 : 0;
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const shot = name => path.join(outDir, `${name}.png`);
  browser = await chromium.launch({ args: ['--mute-audio'] });

  const nuevaPagina = async context => {
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    await page.addInitScript(() => {
      class FakeRecognition {
        start() {
          const transcript = '¿Desde cuándo tiene el dolor y hacia dónde se irradia?';
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
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', request => {
      if (request.url().includes('/finish')) {
        registro.finish.push({ momento: new Date().toISOString(), cuerpo: request.postDataJSON?.() ?? null });
      }
    });
    return page;
  };

  const iniciarConsulta = async page => {
    await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
    await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
    const mic = page.locator('[aria-label="Micrófono"]');
    while (!(await mic.isVisible())) {
      const skip = page.locator('[data-role="skip-speech"]:visible').first();
      if (await skip.count()) await skip.click().catch(() => null);
      await page.waitForTimeout(300);
    }
    await preguntar(page);
  };

  const preguntar = async page => {
    const reply = page.waitForResponse(r => r.url().includes('/message'), { timeout: 120000 });
    await page.locator('[aria-label="Micrófono"]').click();
    const response = await reply;
    await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent === 'Tu turno',
      null, { timeout: 120000 });
    return response.status();
  };

  const visible = async (page, role) => page.locator(`[data-role="${role}"]`).isVisible();
  const texto = async (page, role) => ((await page.locator(`[data-role="${role}"]`).textContent()) || '').trim();
  const finishes = () => registro.finish.length;

  // =============================================================== Parte 1: invitado
  const guest = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await nuevaPagina(guest);
  await iniciarConsulta(page);
  await page.click('[data-role="diagnosis-button"]');

  // CA1: vacío, sin petición
  await page.fill('[data-role="diagnosis-input"]', '   ');
  await page.click('[data-role="save-diagnosis"]');
  comprobar('vacío: mensaje de campo obligatorio', (await texto(page, 'diagnosis-feedback')) === MENSAJES.vacio,
    await texto(page, 'diagnosis-feedback'));
  comprobar('vacío: no pide confirmación', !(await visible(page, 'diagnosis-confirm')));
  comprobar('vacío: no envía nada al servidor', finishes() === 0, `${finishes()} peticiones`);

  // CA2: validación de texto en pantalla, sin petición
  await page.fill('[data-role="diagnosis-input"]', 'ab');
  await page.click('[data-role="save-diagnosis"]');
  comprobar('pocas letras: mensaje', (await texto(page, 'diagnosis-feedback')) === MENSAJES.letras, await texto(page, 'diagnosis-feedback'));
  await page.fill('[data-role="diagnosis-input"]', '<b>Apendicitis</b>');
  await page.click('[data-role="save-diagnosis"]');
  comprobar('con < >: mensaje', (await texto(page, 'diagnosis-feedback')) === MENSAJES.marcado, await texto(page, 'diagnosis-feedback'));
  comprobar('textos inválidos: ninguna petición', finishes() === 0, `${finishes()} peticiones`);
  await page.screenshot({ path: shot('navegador_01_validacion') });

  // CA3: confirmación con el texto escrito, y «Seguir en la consulta»
  await page.fill('[data-role="diagnosis-input"]', DIAGNOSTICO);
  await page.click('[data-role="save-diagnosis"]');
  comprobar('válido: aparece la confirmación', await visible(page, 'diagnosis-confirm'));
  comprobar('la confirmación muestra el diagnóstico', (await texto(page, 'diagnosis-confirm-text')) === DIAGNOSTICO.replace(/\s+/g, ' ').trim()
    || (await texto(page, 'diagnosis-confirm-text')).replace(/\s+/g, ' ') === DIAGNOSTICO.replace(/\s+/g, ' '),
    await texto(page, 'diagnosis-confirm-text'));
  comprobar('mostrar la confirmación no envía nada', finishes() === 0, `${finishes()} peticiones`);
  await page.locator('[data-role="diagnosis-confirm"]').screenshot({ path: shot('navegador_02_confirmacion') });
  await page.click('[data-role="cancel-confirm"]');
  comprobar('«Seguir en la consulta» oculta la confirmación', !(await visible(page, 'diagnosis-confirm')));
  comprobar('tras cancelar, el diagnóstico escrito se conserva', (await page.inputValue('[data-role="diagnosis-input"]')) === DIAGNOSTICO);
  const otra = await preguntar(page);
  comprobar('tras cancelar, se puede seguir preguntando', otra === 200, `HTTP ${otra}`);

  // CA7: el servidor falla (503 simulado): la consulta sigue abierta
  await page.route('**/finish', route => route.fulfill({
    status: 503, contentType: 'application/json', body: JSON.stringify({ detail: MENSAJES.noRegistrado }),
  }));
  await page.click('[data-role="diagnosis-button"]');
  await page.click('[data-role="save-diagnosis"]');
  await page.click('[data-role="confirm-diagnosis"]');
  await page.waitForFunction(m => document.querySelector('[data-role="diagnosis-feedback"]').textContent.includes(m),
    MENSAJES.noRegistrado, { timeout: 15000 }).catch(() => null);
  comprobar('503: muestra que no se registró', (await texto(page, 'diagnosis-feedback')).includes(MENSAJES.noRegistrado),
    await texto(page, 'diagnosis-feedback'));
  comprobar('503: no muestra la hoja de evaluación', !(await visible(page, 'evaluation-panel')));
  comprobar('503: el micrófono sigue habilitado', await page.locator('[aria-label="Micrófono"]').isEnabled());
  comprobar('503: «Guardar» vuelve a estar habilitado', await page.locator('[data-role="save-diagnosis"]').isEnabled());
  await page.screenshot({ path: shot('navegador_03_fallo_503') });
  await page.unroute('**/finish');

  // CA2/CA7: el servidor rechaza (422 simulado): muestra su motivo y sigue abierta
  await page.route('**/finish', route => route.fulfill({
    status: 422, contentType: 'application/json', body: JSON.stringify({ detail: MENSAJES.letras }),
  }));
  await page.click('[data-role="save-diagnosis"]');
  await page.click('[data-role="confirm-diagnosis"]');
  await page.waitForFunction(m => document.querySelector('[data-role="diagnosis-feedback"]').textContent.includes(m),
    MENSAJES.letras, { timeout: 15000 }).catch(() => null);
  comprobar('422: muestra el motivo del servidor', (await texto(page, 'diagnosis-feedback')).includes(MENSAJES.letras),
    await texto(page, 'diagnosis-feedback'));
  comprobar('422: no muestra la hoja de evaluación', !(await visible(page, 'evaluation-panel')));
  await page.unroute('**/finish');

  // CA6: doble clic en «Confirmar» con el servidor real: una sola petición
  const antes = finishes();
  await page.click('[data-role="save-diagnosis"]');
  const respuesta = page.waitForResponse(r => r.url().includes('/finish'), { timeout: 120000 });
  await page.locator('[data-role="confirm-diagnosis"]').dblclick();
  await page.locator('[data-role="confirm-diagnosis"]').click({ force: true, timeout: 2000 }).catch(() => null);
  const cierre = await respuesta;
  await page.locator('[data-role="evaluation-panel"]').waitFor({ state: 'visible', timeout: 30000 });
  await page.waitForTimeout(1500);
  comprobar('doble clic: una sola petición de cierre', finishes() - antes === 1, `${finishes() - antes} peticiones`);
  comprobar('cierre real: 200', cierre.status() === 200, cierre.status());
  const cuerpo = await cierre.json().catch(() => ({}));
  comprobar('se envía confirmado=true', registro.finish.at(-1)?.cuerpo?.confirmado === true, JSON.stringify(registro.finish.at(-1)?.cuerpo));
  comprobar('invitado: registro no guardado', cuerpo.registro?.guardado === false && cuerpo.registro?.motivo === 'invitado',
    JSON.stringify(cuerpo.registro));
  comprobar('invitado: la hoja explica que no se registró', (await texto(page, 'evaluation-saved')).includes('invitado')
    || (await texto(page, 'evaluation-saved')).includes('inicia sesión'), await texto(page, 'evaluation-saved'));
  comprobar('la hoja muestra el diagnóstico propuesto', (await texto(page, 'evaluation-student-diagnosis')).includes('Síndrome coronario agudo'),
    await texto(page, 'evaluation-student-diagnosis'));
  await page.screenshot({ path: shot('navegador_04_cerrada_invitado') });

  // =============================================================== Parte 2: alumno con sesión
  const env = leerEnv();
  const url = env.SUPABASE_URL;
  const secret = env.SUPABASE_SECRET_KEY;
  const publishable = env.SUPABASE_PUBLISHABLE_KEY;
  let userId = null;
  if (!url || !secret || !publishable) {
    comprobar('alumno: hay Supabase en el .env para crear el usuario temporal', false, 'faltan variables');
  } else {
    const admin = { apikey: secret, 'Content-Type': 'application/json' };
    if (!secret.startsWith('sb_')) admin.Authorization = `Bearer ${secret}`;
    const email = `alumno.prueba.hu006.${crypto.randomBytes(4).toString('hex')}@example.com`;
    const password = crypto.randomBytes(18).toString('base64url');
    try {
      const creado = await fetch(`${url}/auth/v1/admin/users`, { method: 'POST', headers: admin, body: JSON.stringify({
        email, password, email_confirm: true, user_metadata: { nombres: 'Alumno', apellidos: 'Prueba HU-006' },
      }) });
      const datos = await creado.json();
      userId = datos.id;
      comprobar('alumno temporal creado', creado.ok && Boolean(userId), creado.status);
      const student = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
      const alumno = await nuevaPagina(student);
      const intentos = [];
      for (let n = 1; n <= 2; n += 1) {
        await alumno.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
        if (n === 1) {
          const login = await alumno.evaluate(async ({ email, password }) => {
            const client = await window.auth.ready;
            const { error } = await client.auth.signInWithPassword({ email, password });
            return error ? error.message : 'ok';
          }, { email, password });
          comprobar('alumno: inicia sesión', login === 'ok', login);
        }
        await iniciarConsulta(alumno);
        await alumno.click('[data-role="diagnosis-button"]');
        await alumno.fill('[data-role="diagnosis-input"]', `${DIAGNOSTICO} (consulta ${n})`);
        await alumno.click('[data-role="save-diagnosis"]');
        const fin = alumno.waitForResponse(r => r.url().includes('/finish'), { timeout: 120000 });
        await alumno.click('[data-role="confirm-diagnosis"]');
        const cuerpoAlumno = await (await fin).json().catch(() => ({}));
        await alumno.locator('[data-role="evaluation-panel"]').waitFor({ state: 'visible', timeout: 30000 });
        await alumno.waitForTimeout(800);
        intentos.push(cuerpoAlumno.registro?.numero_intento);
        const mensaje = await texto(alumno, 'evaluation-saved');
        comprobar(`alumno, consulta ${n}: registro guardado`, cuerpoAlumno.registro?.guardado === true, JSON.stringify(cuerpoAlumno.registro));
        comprobar(`alumno, consulta ${n}: la hoja dice «intento ${n}»`, mensaje.includes(`intento ${n}`), mensaje);
        await alumno.screenshot({ path: shot(`navegador_0${4 + n}_alumno_intento_${n}`) });
      }
      comprobar('alumno: intentos 1 y 2 del mismo caso', JSON.stringify(intentos) === '[1,2]', JSON.stringify(intentos));
    } finally {
      if (userId) {
        const borrado = await fetch(`${url}/auth/v1/admin/users/${userId}`, { method: 'DELETE', headers: admin });
        registro.limpieza = { usuario_temporal_borrado: borrado.ok, http: borrado.status };
        comprobar('alumno temporal borrado', borrado.ok, borrado.status);
      }
    }
  }

  comprobar('sin errores de JavaScript en la página', errors.length === 0, errors.join(' | '));
  await browser.close();
  process.exit(terminar());
})().catch(async error => {
  await browser?.close().catch(() => null);
  process.exit(terminar(error) || 1);
});
