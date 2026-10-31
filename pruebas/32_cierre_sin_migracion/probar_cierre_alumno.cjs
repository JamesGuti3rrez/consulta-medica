// Cierre de consulta de un alumno con sesión mientras falta la migración 0007 (E2E contra el localhost real).
//
// El servidor usa el Supabase del .env (SESSION_STORE=supabase) sin la tabla diagnosticos_finales. Un alumno temporal
// de Supabase Auth inicia sesión, hace una pregunta, escribe su diagnóstico, confirma y cierra: la consulta debe
// cerrarse (no 503), mostrar la hoja de evaluación con su diagnóstico y avisar que quedó guardado en la consulta.
// El alumno temporal se borra al final.
//
// Uso: node pruebas/32_cierre_sin_migracion/probar_cierre_alumno.cjs <carpeta de resultados>
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const CASO = process.env.CASO || 'CIR-005';
const DIAGNOSTICO = 'Hemofilia A con sangrado posoperatorio.';

function leerEnv() {
  const env = {};
  const archivo = path.resolve(__dirname, '..', '..', '.env');
  for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^([A-Z_]+)=(.*)$/);
    if (m) env[m[1]] = m[2].replace(/^['"]|['"]$/g, '');
  }
  return env;
}

(async () => {
  const outDir = path.resolve(process.argv[2] || 'pruebas/32_cierre_sin_migracion/resultados/local');
  fs.mkdirSync(outDir, { recursive: true });
  const comprobaciones = [];
  const comprobar = (descripcion, ok, detalle = '') => {
    comprobaciones.push({ descripcion, resultado: ok ? 'PASA' : 'FALLA', detalle: String(detalle) });
    console.log(`${ok ? 'PASA ' : 'FALLA'}  ${descripcion}${detalle !== '' ? `  (${String(detalle).slice(0, 110)})` : ''}`);
  };
  const env = leerEnv();
  const admin = { apikey: env.SUPABASE_SECRET_KEY, 'Content-Type': 'application/json' };
  if (!env.SUPABASE_SECRET_KEY.startsWith('sb_')) admin.Authorization = `Bearer ${env.SUPABASE_SECRET_KEY}`;
  const tabla = await fetch(`${env.SUPABASE_URL}/rest/v1/diagnosticos_finales?select=id&limit=1`, { headers: admin });
  console.log(`Servidor ${BASE_URL}, caso ${CASO}; tabla diagnosticos_finales en Supabase: HTTP ${tabla.status}\n`);

  const email = `alumno.prueba.sinmigracion.${crypto.randomBytes(4).toString('hex')}@example.com`;
  const password = crypto.randomBytes(18).toString('base64url');
  const browser = await chromium.launch({ args: ['--mute-audio'] });
  const errores = [];
  let userId = null;
  try {
    const creado = await fetch(`${env.SUPABASE_URL}/auth/v1/admin/users`, { method: 'POST', headers: admin,
      body: JSON.stringify({ email, password, email_confirm: true, user_metadata: { nombres: 'Alumno', apellidos: 'Prueba' } }) });
    userId = (await creado.json()).id;
    comprobar('alumno temporal creado', creado.ok && Boolean(userId), creado.status);

    const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
    page.on('pageerror', error => errores.push(error.message));
    await page.addInitScript(() => {
      class FakeRecognition {
        start() {
          const result = { resultIndex: 0, results: [Object.assign([{ transcript: '¿Desde cuándo tiene el dolor?' }], { isFinal: true })] };
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
    await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
    const login = await page.evaluate(async ({ email, password }) => {
      const client = await window.auth.ready;
      const { error } = await client.auth.signInWithPassword({ email, password });
      return error ? error.message : 'ok';
    }, { email, password });
    comprobar('alumno: inicia sesión', login === 'ok', login);
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
    await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
    const mic = page.locator('[aria-label="Micrófono"]');
    while (!(await mic.isVisible())) {
      const skip = page.locator('[data-role="skip-speech"]:visible').first();
      if (await skip.count()) await skip.click().catch(() => null);
      await page.waitForTimeout(300);
    }
    const turno = page.waitForResponse(r => r.url().includes('/message'), { timeout: 120000 });
    await mic.click();
    comprobar('alumno: pregunta al paciente', (await turno).status() === 200);
    await page.waitForFunction(() => document.querySelector('[data-role="conversation-status"]').textContent === 'Tu turno',
      null, { timeout: 120000 });

    await page.click('[data-role="diagnosis-button"]');
    await page.fill('[data-role="diagnosis-input"]', DIAGNOSTICO);
    await page.click('[data-role="save-diagnosis"]');
    const fin = page.waitForResponse(r => r.url().includes('/finish'), { timeout: 120000 });
    await page.click('[data-role="confirm-diagnosis"]');
    const respuesta = await fin;
    const cuerpo = await respuesta.json().catch(() => ({}));
    comprobar('cierre: el servidor responde 200 (antes 503)', respuesta.status() === 200, respuesta.status());
    comprobar('cierre: registro pendiente de la migración', cuerpo.registro?.motivo === 'registro_pendiente',
      JSON.stringify(cuerpo.registro));
    await page.locator('[data-role="evaluation-panel"]').waitFor({ state: 'visible', timeout: 30000 });
    await page.waitForTimeout(800);
    const propio = (await page.locator('[data-role="evaluation-student-diagnosis"]').textContent() || '').trim();
    comprobar('hoja de evaluación con el diagnóstico del alumno', propio === DIAGNOSTICO, propio);
    const aviso = (await page.locator('[data-role="evaluation-saved"]').textContent() || '').trim();
    comprobar('la hoja avisa que el diagnóstico quedó guardado en la consulta', aviso.includes('quedó guardado en esta consulta'), aviso);
    comprobar('la consulta quedó cerrada', cuerpo.phase === 'finalizada', cuerpo.phase);
    await page.screenshot({ path: path.join(outDir, 'cierre_alumno_sin_migracion.png') });
  } catch (error) {
    comprobar('la prueba llega al final', false, error.message.split('\n')[0]);
  } finally {
    if (userId) {
      const borrado = await fetch(`${env.SUPABASE_URL}/auth/v1/admin/users/${userId}`, { method: 'DELETE', headers: admin });
      comprobar('alumno temporal borrado', borrado.ok, borrado.status);
    }
    comprobar('sin errores de JavaScript en la página', errores.length === 0, errores.join(' | '));
    await browser.close();
    fs.writeFileSync(path.join(outDir, 'cierre_registro.json'), JSON.stringify({ servidor: BASE_URL, caso: CASO,
      tabla_http: tabla.status, fecha: new Date().toISOString(), comprobaciones }, null, 2));
  }
  const fallan = comprobaciones.filter(c => c.resultado === 'FALLA').length;
  console.log(`\n${comprobaciones.length - fallan} de ${comprobaciones.length} comprobaciones pasan`);
  process.exit(fallan ? 1 : 0);
})();
