// Sincronía de labios por sílaba para los avatares de la escena.
//
// El texto se convierte en una línea de sílabas: cada sílaba toma la forma de boca de su vocal (A, E/I, O/U o
// pequeña). Las consonantes no cambian la boca, salvo M, B y P (cierre breve) y F (boca pequeña breve). La
// puntuación cierra la boca y separa frases. Cerrada (null) es la imagen quieta del personaje.
//
// La línea se recorre con un reloj en sílabas:
// - Con la voz neuronal se mide el volumen del audio: el reloj solo avanza mientras suena y la boca se cierra en
//   los silencios. Al salir de una pausa larga (una coma, un punto) el reloj salta al inicio de frase más
//   cercano y ajusta la velocidad: así la boca no se desfasa en frases largas.
// - Con la voz del navegador no hay volumen que medir: el reloj avanza solo (con las pausas de la puntuación) y
//   cada aviso de palabra (onboundary) lo pone en esa palabra.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.Labios = api;
})(typeof self !== 'undefined' ? self : this, () => {
  const VOWELS = 'aeiouáéíóúü';
  // En vocales seguidas manda la más abierta: A, luego O/U, luego E, luego I.
  const NUCLEUS = [['aá', 'A'], ['oóuúü', 'O'], ['eé', 'E'], ['iíy', 'E']];
  const DIGIT_SHAPES = ['E', 'A', 'E', 'O'];
  // Parte de la sílaba que dura el cierre de M, B, P o la boca pequeña de F.
  const CLOSURE = 0.3;
  // Pausas de la puntuación, en sílabas, cuando no se mide la voz.
  const COMMA_PAUSE = 1.6;
  const STOP_PAUSE = 2.4;
  // Un silencio de al menos esto es una pausa de frase: edge-tts calla ~300 ms en una coma y el medidor ya
  // espera ~80 ms antes de dar el silencio; el cierre de una oclusiva (p, t, k) dura menos.
  const PAUSE_MS = 150;
  // Hasta dónde puede saltar el reloj al realinearse, en sílabas.
  const MAX_SNAP = 2;
  const MIN_MS = 100;
  const MAX_MS = 260;

  const nucleusShape = group => {
    for (const [letters, shape] of NUCLEUS) if ([...group].some(ch => letters.includes(ch))) return shape;
    return 'pequena';
  };

  // Sílabas aproximadas: cada grupo de vocales seguidas es una sílaba y lleva delante sus consonantes.
  const syllables = word => {
    const w = word.toLowerCase();
    const out = [];
    let onset = '';
    for (let i = 0; i < w.length;) {
      if (VOWELS.includes(w[i])) {
        let j = i;
        while (j < w.length && VOWELS.includes(w[j])) j++;
        out.push({ onset, shape: nucleusShape(w.slice(i, j)) });
        onset = '';
        i = j;
      } else {
        onset += w[i];
        i++;
      }
    }
    if (!out.length) out.push({ onset, shape: 'pequena' });
    return out;
  };

  // Línea de sílabas de un texto: steps [{u, m}] ordenados (u en sílabas), inicio de cada palabra en el texto
  // (para la voz del navegador) e inicios de frase (para realinear con la voz medida).
  const plan = (text, { pauses = false } = {}) => {
    const steps = [];
    const words = [];
    const boundaries = [0];
    let u = 0;
    const push = (at, m) => {
      if (steps.length && steps[steps.length - 1].m === m) return;
      if (steps.length && steps[steps.length - 1].u === at) steps.pop();
      if (steps.length && steps[steps.length - 1].m === m) return;
      steps.push({ u: at, m });
    };
    const boundary = () => {
      if (boundaries[boundaries.length - 1] !== u) boundaries.push(u);
    };
    for (const match of String(text || '').toLowerCase().matchAll(/[a-zñáéíóúü]+|\d+|[,.;:!?¡¿…\n]+/g)) {
      const token = match[0];
      if (/^\d/.test(token)) {
        words.push({ char: match.index, u });
        for (let i = 0; i < token.length * 2; i++) push(u++, DIGIT_SHAPES[i % DIGIT_SHAPES.length]);
      } else if (/^[a-zñáéíóúü]/.test(token)) {
        words.push({ char: match.index, u });
        for (const syllable of syllables(token)) {
          const last = syllable.onset.slice(-1);
          if (last && 'mbp'.includes(last)) {
            push(u, null);
            push(u + CLOSURE, syllable.shape);
          } else if (last === 'f') {
            push(u, 'pequena');
            push(u + CLOSURE, syllable.shape);
          } else {
            push(u, syllable.shape);
          }
          u += 1;
        }
      } else {
        push(u, null);
        boundary();
        if (pauses) u += /[.!?…\n]/.test(token) ? STOP_PAUSE : COMMA_PAUSE;
        boundary();
      }
    }
    push(u, null);
    boundary();
    return { steps, words, boundaries, total: u };
  };

  const mouthAt = (steps, u) => {
    let m = null;
    for (const step of steps) {
      if (step.u <= u) m = step.m;
      else break;
    }
    return m;
  };

  // Reloj de la boca. setMouth(m) recibe 'pequena', 'A', 'E', 'O' o null (cerrada) solo cuando cambia.
  const createLipSync = ({ setMouth, msPerSyllable = 170 }) => {
    let current = null;
    let line = null;
    let u = 0;
    let ms = msPerSyllable;
    let silentFor = 0;
    // Desde el último realineado: dónde estaba el reloj y cuánta voz sonó, para ajustar la velocidad.
    let anchor = null;
    let voicedSince = 0;
    const show = m => {
      if (m === current) return;
      current = m;
      setMouth(m);
    };
    const resync = () => {
      const nearest = line.boundaries.reduce((best, b) => (Math.abs(b - u) < Math.abs(best - u) ? b : best));
      if (Math.abs(nearest - u) > MAX_SNAP) return;
      if (anchor !== null && nearest > anchor && voicedSince > 0) {
        const measured = voicedSince / (nearest - anchor);
        ms = Math.min(MAX_MS, Math.max(MIN_MS, ms * 0.6 + measured * 0.4));
      }
      u = nearest;
      anchor = nearest;
      voicedSince = 0;
    };
    return {
      start(text, { pauses = false, msPerSyllable: rate } = {}) {
        line = plan(text, { pauses });
        u = 0;
        anchor = 0;
        voicedSince = 0;
        silentFor = 0;
        if (rate) ms = rate;
        show(null);
      },
      // Avanza dt ms. voiced: true o false si se mide la voz; null si no se puede medir.
      step(dt, voiced) {
        if (!line) return;
        if (voiced === false) {
          silentFor += dt;
          show(null);
          return;
        }
        if (voiced === true && silentFor >= PAUSE_MS) resync();
        silentFor = 0;
        u += dt / ms;
        voicedSince += dt;
        show(u >= line.total ? null : mouthAt(line.steps, u));
      },
      // Voz del navegador: empieza a decir la palabra que está en charIndex del texto.
      seekChar(charIndex) {
        if (!line) return;
        const word = line.words.filter(item => item.char <= charIndex).pop();
        if (word) u = word.u;
      },
      position: () => u,
      stop() {
        line = null;
        show(null);
      },
    };
  };

  return { syllables, plan, createLipSync };
});
