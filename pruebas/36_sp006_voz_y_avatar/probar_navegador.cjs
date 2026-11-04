// SP-006, prueba mínima en el navegador: lo que la matriz necesita medir del lado del estudiante.
//   1. Web Speech API (voz del navegador, el respaldo): voces en español y tiempo hasta que empieza a hablar.
//   2. Avatares: si el navegador reproduce H.264 (Google Chrome y el Chromium de Playwright, que no lo trae),
//      peso y tiempo de carga de cada video y de su imagen quieta.
// Uso (servidor en BASE_URL): node pruebas/36_sp006_voz_y_avatar/probar_navegador.cjs <salida.json>
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const PERSONAJES = ['doctor', 'paciente-hombre', 'paciente-mujer'];

(async () => {
  const salida = path.resolve(process.argv[2] || 'pruebas/36_sp006_voz_y_avatar/resultados/navegador.json');
  const resultado = { fecha: new Date().toISOString(), servidor: BASE_URL, navegadores: {} };

  for (const [nombre, opciones] of [['Google Chrome', { channel: 'chrome' }], ['Chromium de Playwright', {}]]) {
    const browser = await chromium.launch({ ...opciones, args: ['--mute-audio', '--autoplay-policy=no-user-gesture-required'] });
    const page = await browser.newPage();
    // Página vacía del mismo servidor: los videos se miden sin el resto del simulador.
    await page.goto(`${BASE_URL}/privacidad.html`, { waitUntil: 'networkidle' });
    const datos = await page.evaluate(async ({ personajes }) => {
      const esperar = ms => new Promise(resolve => setTimeout(resolve, ms));
      // 1. Voz del navegador.
      let voces = speechSynthesis.getVoices();
      for (let i = 0; i < 20 && !voces.length; i += 1) { await esperar(100); voces = speechSynthesis.getVoices(); }
      const espanol = voces.filter(v => v.lang.toLowerCase().startsWith('es')).map(v => `${v.name} (${v.lang}${v.localService ? ', local' : ', en línea'})`);
      const inicios = [];
      for (let i = 0; i < 3; i += 1) {
        inicios.push(await new Promise(resolve => {
          const frase = new SpeechSynthesisUtterance('No hay alergias documentadas en la ficha.');
          frase.lang = 'es-ES';
          const desde = performance.now();
          frase.onstart = () => { speechSynthesis.cancel(); resolve(Math.round(performance.now() - desde)); };
          frase.onerror = () => resolve(null);
          speechSynthesis.speak(frase);
          setTimeout(() => resolve(null), 5000);
        }));
        await esperar(300);
      }
      // 2. Avatares.
      const h264 = document.createElement('video').canPlayType('video/mp4; codecs="avc1.640028"');
      const videos = [];
      for (const personaje of personajes) {
        videos.push(await new Promise(resolve => {
          const video = document.createElement('video');
          Object.assign(video, { muted: true, preload: 'auto' });
          const desde = performance.now();
          const fin = estado => resolve({ personaje, estado, ms: Math.round(performance.now() - desde),
            resolucion: `${video.videoWidth}x${video.videoHeight}`, duracion_s: Number(video.duration.toFixed(2)) || null });
          video.oncanplaythrough = () => fin('se puede reproducir');
          video.onerror = () => fin(`error ${video.error?.code}: no reproduce el formato`);
          setTimeout(() => fin('sin respuesta en 10 s'), 10000);
          video.src = `assets/avatars/${personaje}-hablando.mp4?m=${Math.random()}`;
        }));
      }
      return { voces_espanol: espanol, inicio_voz_ms: inicios, h264: h264 || '(no)', videos };
    }, { personajes: PERSONAJES });
    resultado.navegadores[nombre] = { version: browser.version(), ...datos };
    await browser.close();

    console.log(`== ${nombre} ${resultado.navegadores[nombre].version}`);
    console.log(`  Voz del navegador: ${datos.voces_espanol.length} voces en español; empieza a hablar en ${datos.inicio_voz_ms.map(ms => (ms === null ? 'sin voz' : `${ms} ms`)).join(', ')}`);
    datos.voces_espanol.forEach(voz => console.log(`    ${voz}`));
    console.log(`  Reproduce H.264 (MP4): ${datos.h264}`);
    datos.videos.forEach(v => console.log(`    ${v.personaje.padEnd(16)} ${v.estado}, ${v.ms} ms, ${v.resolucion}, ${v.duracion_s ?? '-'} s`));
  }

  // Peso de lo que descarga el estudiante por personaje.
  resultado.archivos = [];
  console.log('\n== Peso de los avatares');
  for (const personaje of PERSONAJES) {
    for (const archivo of [`${personaje}-hablando.mp4`, `${personaje}-1280.webp`, `${personaje}-800.webp`]) {
      const respuesta = await fetch(`${BASE_URL}/assets/avatars/${archivo}`);
      const bytes = (await respuesta.arrayBuffer()).byteLength;
      resultado.archivos.push({ archivo, estado: respuesta.status, tipo: respuesta.headers.get('content-type'), kb: Math.round(bytes / 1024) });
      console.log(`  ${archivo.padEnd(30)} ${respuesta.status} ${respuesta.headers.get('content-type').padEnd(11)} ${Math.round(bytes / 1024)} KB`);
    }
  }
  fs.mkdirSync(path.dirname(salida), { recursive: true });
  fs.writeFileSync(salida, JSON.stringify(resultado, null, 2));
  console.log(`\nResultado en ${path.relative(process.cwd(), salida)}`);
})();
