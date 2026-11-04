// Voz constante (E2E): cada personaje conserva la misma voz toda la consulta. Antes, si la voz neuronal fallaba o
// tardaba en una frase, solo esa frase sonaba con la voz del navegador y la siguiente volvía a la neuronal.
// La prueba fuerza fallos de red en /api/voz y registra qué voz suena en cada frase.
//
// Escenarios (ESCENARIO=a|b):
//   a  La voz neuronal suena y luego falla: la 2.ª frase falla al primer intento y la 3.ª en todos.
//      Se espera que la 2.ª suene neuronal al reintentar, que la 3.ª se muestre sin voz y que nunca hable el navegador.
//   b  La voz neuronal falla desde la primera frase: toda la consulta, paciente incluido, habla con la voz del
//      navegador, una voz fija por personaje, y no se vuelve a pedir la voz neuronal.
// Uso: node pruebas/35_voz_constante/probar_voz_constante.cjs <carpeta de resultados>
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100';
const CASO = process.env.CASO || 'CIR-005';
const ESCENARIO = process.env.ESCENARIO || 'a';

(async () => {
  const outDir = path.resolve(process.argv[2] || `pruebas/35_voz_constante/resultados/escenario_${ESCENARIO}`);
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

  // Frases en el orden en que se piden (sin contar reintentos) y cada petición con su resultado.
  const frases = [];
  const peticiones = [];
  await page.route('**/api/voz?*', route => {
    const url = new URL(route.request().url());
    const texto = url.searchParams.get('texto');
    const intento = Number(url.searchParams.get('intento') || 1);
    if (!frases.includes(texto)) frases.push(texto);
    const indice = frases.indexOf(texto);
    const falla = ESCENARIO === 'b' || (indice === 1 && intento === 1) || indice === 2;
    peticiones.push({ frase: indice + 1, intento, personaje: url.searchParams.get('personaje'), resultado: falla ? 'fallo forzado' : 'servidor' });
    return falla ? route.abort('connectionfailed') : route.continue();
  });

  await page.addInitScript(() => {
    // Qué voz suena en cada frase: el <audio> de la voz neuronal o speechSynthesis del navegador.
    window.__voces = [];
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function (...args) {
      if (this instanceof HTMLAudioElement) {
        this.addEventListener('playing', () => {
          const url = new URL(this.src, location.href);
          window.__voces.push({ voz: 'neuronal', personaje: url.searchParams.get('personaje'), texto: url.searchParams.get('texto'),
            intento: Number(url.searchParams.get('intento') || 1) });
        }, { once: true });
      }
      return play.apply(this, args);
    };
    const speak = window.speechSynthesis.speak.bind(window.speechSynthesis);
    window.speechSynthesis.speak = utterance => {
      const personaje = document.querySelector('[data-role="patient-bubble"]:not(.hidden)') ? 'patient' : 'doctor';
      window.__voces.push({ voz: 'navegador', personaje, nombre: utterance.voice?.name || '(predeterminada)', texto: utterance.text });
      return speak(utterance);
    };
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

  const esperarTurno = () => page.waitForFunction(
    () => document.querySelector('[data-role="conversation-status"]')?.textContent === 'Tu turno', null, { timeout: 300000 });
  console.log(`Escenario ${ESCENARIO.toUpperCase()}, caso ${CASO} en ${BASE_URL}\n`);

  try {
    await page.goto(`${BASE_URL}/simulacion.html?caso=${CASO}`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => !document.querySelector('[data-role="start-simulation"]').disabled);
    await page.getByRole('button', { name: /Iniciar simulaci/ }).click();
    await page.locator('[aria-label="Micrófono"]').waitFor({ state: 'visible', timeout: 300000 });
    await esperarTurno();
    // El paciente responde: debe seguir con la voz que ya eligió la consulta.
    await page.locator('[aria-label="Micrófono"]').click();
    await page.locator('[data-role="patient-bubble"]').waitFor({ state: 'visible', timeout: 120000 });
    await esperarTurno();
    await page.waitForTimeout(500);

    const voces = await page.evaluate(() => window.__voces);
    const chat = await page.evaluate(() => [...document.querySelectorAll('.chat-row .chat-text')].map(el => el.textContent));
    console.log('Frases pedidas a /api/voz:');
    frases.forEach((texto, i) => console.log(`  ${i + 1}. ${texto.slice(0, 70)}`));
    console.log('Peticiones:', peticiones.map(p => `f${p.frase}/i${p.intento}:${p.resultado === 'servidor' ? 'ok' : 'fallo'}`).join(' '));
    console.log('Voces que sonaron:');
    voces.forEach(v => console.log(`  ${v.voz.padEnd(9)} ${v.personaje.padEnd(8)} ${v.nombre || `intento ${v.intento}`}  «${v.texto.slice(0, 50)}»`));
    console.log('');

    const navegador = voces.filter(v => v.voz === 'navegador');
    const neuronal = voces.filter(v => v.voz === 'neuronal');
    if (ESCENARIO === 'a') {
      comprobar('la consulta empieza con la voz neuronal', voces[0]?.voz === 'neuronal', voces[0]?.voz);
      comprobar('la voz del navegador no suena nunca', navegador.length === 0, `${navegador.length} frases con el navegador`);
      comprobar('la 2.ª frase falla al primer intento y suena neuronal al reintentar',
        neuronal.some(v => v.texto === frases[1] && v.intento === 2), peticiones.filter(p => p.frase === 2).map(p => `i${p.intento}`).join(','));
      comprobar('la 3.ª frase se pide 3 veces y se muestra sin voz',
        peticiones.filter(p => p.frase === 3 && p.intento > 1).length === 2 && !voces.some(v => v.texto === frases[2]));
      comprobar('la consulta sigue después de la frase sin voz (el paciente responde con la voz neuronal)',
        neuronal.some(v => v.personaje === 'patient'));
    } else {
      comprobar('la voz neuronal se intenta 3 veces en la primera frase',
        peticiones.filter(p => p.frase === 1).map(p => p.intento).join() === '1,2,3', peticiones.filter(p => p.frase === 1).map(p => p.intento).join());
      comprobar('la voz neuronal no suena nunca', neuronal.length === 0, `${neuronal.length} frases neuronales`);
      comprobar('después no se vuelve a reintentar la voz neuronal', peticiones.every(p => p.frase === 1 || p.intento === 1),
        peticiones.filter(p => p.frase !== 1 && p.intento > 1).length);
      comprobar('todas las frases del doctor y del paciente suenan con el navegador',
        navegador.some(v => v.personaje === 'doctor') && navegador.some(v => v.personaje === 'patient'), `${navegador.length} frases`);
      for (const personaje of ['doctor', 'patient']) {
        const nombres = [...new Set(navegador.filter(v => v.personaje === personaje).map(v => v.nombre))];
        comprobar(`${personaje === 'doctor' ? 'el doctor' : 'el paciente'} conserva una sola voz del navegador`, nombres.length === 1, nombres.join(' | '));
      }
    }
    comprobar('el chat tiene la presentación completa y la respuesta del paciente', chat.length >= 5, `${chat.length} mensajes`);
    comprobar('sin errores de JavaScript en la página', errores.length === 0, errores.join(' | '));
    fs.writeFileSync(path.join(outDir, 'voz_registro.json'), JSON.stringify({
      escenario: ESCENARIO, caso: CASO, servidor: BASE_URL, fecha: new Date().toISOString(), comprobaciones, frases, peticiones, voces,
    }, null, 2));
  } catch (error) {
    comprobar('la prueba llega al final sin errores', false, error.message.split('\n')[0]);
    await page.screenshot({ path: path.join(outDir, 'error.png') }).catch(() => {});
  }
  await page.screenshot({ path: path.join(outDir, 'final.png') }).catch(() => {});
  await browser.close();
  const fallan = comprobaciones.filter(c => c.resultado === 'FALLA').length;
  console.log(`\n${comprobaciones.length - fallan} de ${comprobaciones.length} comprobaciones pasan`);
  process.exit(fallan ? 1 : 0);
})();
