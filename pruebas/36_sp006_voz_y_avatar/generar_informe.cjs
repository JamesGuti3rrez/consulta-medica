// Genera «SP-006 Informe - Seleccion de voz y avatares.docx» con las cifras de las corridas de esta fase
// (resultados/*.json), para que el informe no pueda contradecir la evidencia.
// Formato de los entregables: A4, márgenes de 2 cm, Arial 11 pt, encabezados de tabla en gris (como TA-019).
// Requiere el paquete docx: npm install --no-save docx@9.5.1 (o NODE_PATH a una carpeta donde esté instalado).
// Uso, desde la raíz: node pruebas/36_sp006_voz_y_avatar/generar_informe.cjs <salida.docx>
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, Footer, PageNumber, LevelFormat, PageBreak, BorderStyle,
} = require('docx');

const dir = path.join(__dirname, 'resultados');
const leer = archivo => JSON.parse(fs.readFileSync(path.join(dir, archivo), 'utf8'));
const voz = leer('voz.json');
const nav = leer('navegador.json');
const sinVideo = leer('sin_video/respaldo_registro.json');
const soloTexto = leer('solo_texto/respaldo_registro.json');
const salida = process.argv[2] || 'SP-006 Informe - Seleccion de voz y avatares.docx';

const ANCHO = 9638; // A4 (11906) menos márgenes de 1134 a cada lado
const GRIS = '475569';
const s = n => n.toFixed(2).replace('.', ',');
const pasan = registro => `${registro.comprobaciones.filter(c => c.resultado === 'PASA').length} de ${registro.comprobaciones.length}`;

// Cifras medidas.
const lat = voz.latencia;
const primeros = lat.flatMap(fila => [fila.primer_trozo_s.min, fila.primer_trozo_s.max]);
const medianas = lat.map(fila => fila.primer_trozo_s.mediana);
const totales = lat.map(fila => fila.total_s.mediana);
const latEdge = `mediana ${s(Math.min(...medianas))} a ${s(Math.max(...medianas))} s hasta el primer trozo de audio; picos de hasta ${s(Math.max(...primeros))} s`;
const chrome = nav.navegadores['Google Chrome'];
const chromium = nav.navegadores['Chromium de Playwright'];
const inicioWeb = chrome.inicio_voz_ms.filter(ms => ms !== null);
const videos = nav.archivos.filter(a => a.archivo.endsWith('.mp4'));
const imagenes = nav.archivos.filter(a => a.archivo.endsWith('-1280.webp'));
const kb = lista => `${Math.min(...lista.map(a => a.kb))} a ${Math.max(...lista.map(a => a.kb))} KB`;
const cargaVideo = chrome.videos.map(v => v.ms);
const pres = voz.presentacion_caracteres;
const vocesEsp = voz.voces.espanol;
const vocesSimulador = Object.entries(voz.voces.del_simulador);

// Bloques de texto.
// Sin marcas de referencia en el texto: la evidencia se nombra con palabras y las fuentes van al final.
const limpio = text => text.replace(/\s*\[(?:V|F\d|C: [^\]]*|E: [^\]]*)\]/g, '');
const t = (text, options = {}) => new TextRun({ text: limpio(text), ...options });
const p = (children, options = {}) => new Paragraph({
  spacing: { after: 120, line: 276 }, ...options, children: typeof children === 'string' ? [t(children)] : children,
});
const h1 = text => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(text)] });
const h2 = text => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(text)] });
const vineta = children => new Paragraph({
  numbering: { reference: 'vinetas', level: 0 }, spacing: { after: 80, line: 276 },
  children: typeof children === 'string' ? [t(children)] : children,
});
const leyenda = text => new Paragraph({ spacing: { before: 160, after: 80 }, keepNext: true, children: [t(text, { bold: true, size: 20, color: GRIS })] });
const nota = text => p([t(text, { italics: true, size: 19, color: GRIS })]);

const celda = (contenido, ancho, { cabecera = false, relleno } = {}) => new TableCell({
  width: { size: ancho, type: WidthType.DXA },
  shading: cabecera || relleno ? { type: ShadingType.CLEAR, color: 'auto', fill: relleno || 'F2F2F2' } : undefined,
  margins: { top: 60, bottom: 60, left: 100, right: 100 },
  children: (Array.isArray(contenido) ? contenido : [contenido]).map(linea => new Paragraph({
    spacing: { after: 40 },
    children: [t(linea, { bold: cabecera, size: 19 })],
  })),
});
const tabla = (anchos, cabecera, filas, { primeraColumna = false } = {}) => new Table({
  width: { size: ANCHO, type: WidthType.DXA },
  columnWidths: anchos,
  rows: [
    ...(cabecera ? [new TableRow({ tableHeader: true, children: cabecera.map((texto, i) => celda(texto, anchos[i], { cabecera: true })) })] : []),
    ...filas.map(fila => new TableRow({
      cantSplit: true,
      children: fila.map((texto, i) => celda(texto, anchos[i], { relleno: primeraColumna && i === 0 ? 'F2F2F2' : undefined })),
    })),
  ],
});
const espacio = () => new Paragraph({ spacing: { after: 60 }, children: [] });

// Fuentes externas, consultadas el 4 de noviembre de 2026.
const FUENTES = [
  ['F1', 'Microsoft. Precios de Azure AI Speech (plan F0 y pago por uso, avatar).', 'https://azure.microsoft.com/en-us/pricing/details/speech/'],
  ['F2', 'Microsoft Learn. Idiomas y voces de texto a voz de Azure AI Speech.', 'https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts'],
  ['F3', 'Microsoft Learn. Avatar de texto a voz: tipos, salida, tiempo real y precios.', 'https://learn.microsoft.com/en-us/azure/ai-services/speech-service/text-to-speech-avatar/what-is-text-to-speech-avatar'],
  ['F4', 'Microsoft. Azure for Students: 100 USD de crédito por 12 meses, sin tarjeta, renovable.', 'https://azure.microsoft.com/en-us/free/students'],
  ['F5', 'PyPI. Paquete edge-tts 7.3.1, licencia LGPLv3, «Microsoft Edge\'s online text-to-speech service».', 'https://pypi.org/project/edge-tts/'],
  ['F6', 'Hugging Face. KwaiVGI/LivePortrait: licencia MIT; los modelos de InsightFace que usa son solo para investigación no comercial.', 'https://huggingface.co/KwaiVGI/LivePortrait'],
  ['F7', 'met4citizen/TalkingHead: avatar 3D con sincronía labial, licencia MIT; español sin módulo propio (necesita visemas, p. ej. de Azure).', 'https://github.com/met4citizen/TalkingHead'],
  ['F8', 'Rive. Precios: editor y runtimes gratuitos; exportar requiere plan de pago (Cadet).', 'https://rive.app/docs/account-admin/pricing'],
  ['F9', 'Reseñas de precios de D-ID 2026 (sin página oficial consultable): prueba de 14 días con marca de agua y uso no comercial; planes de API por créditos.', 'https://www.creatify.ai/blog/d-id-pricing-(2026)-plans-credits-and-what-you-ll-actually-pay'],
];

const portada = [
  p([t('CONSULTA MÉDICA VIRTUAL  ·  INFORME DE SPIKE', { size: 17, color: GRIS, bold: true })], { spacing: { after: 80 } }),
  p([t('SP-006: Selección de tecnología para voz natural y avatares', { size: 34, bold: true })], { spacing: { after: 80 } }),
  p([t('Comparación de alternativas, prueba mínima en el simulador y selección: Azure AI Speech como voz definitiva, edge-tts como puente mientras llega la autorización y avatares con video de LivePortrait', { color: GRIS })], { spacing: { after: 240 } }),
  tabla([2600, 7038], null, [
    ['PBI', 'SP-006 · Seleccionar tecnología para voz natural y avatares'],
    ['Responsable', 'James Bryam Gutiérrez Rubio'],
    ['Fecha de las ejecuciones', '4 de noviembre de 2026 (hora de Perú, UTC-5)'],
    ['Rama', 'James'],
    ['Evidencia', ['pruebas/36_sp006_voz_y_avatar/ (prueba mínima de esta selección)', 'pruebas/34_avatares_hablando/ (integración de los avatares)', 'pruebas/35_voz_constante/ (una voz por personaje)', 'pruebas/27_voz_humanizada/ (voz neuronal, TA-019)']],
    ['Estado', 'Selección hecha y probada. La voz usa edge-tts de forma provisional; Azure AI Speech queda pendiente de la autorización de GitHub Student (sección 9).'],
    ['Versión', '1.0'],
  ], { primeraColumna: true }),
  nota('Todo lo que afirmo lo ejecuté y lo dejé guardado, con su salida y una foto real de la terminal, en la carpeta de pruebas indicada. Lo que no pude medir (Azure AI Speech, al que todavía no tengo acceso, y los servicios de pago) lo tomé de la documentación oficial o de reseñas, que cito en la sección 11.'),
  leyenda('Contenido'),
  tabla([900, 3919, 900, 3919], ['Sección', 'Tema', 'Sección', 'Tema'], [
    ['1', 'Resumen', '7', 'Selección documentada'],
    ['2', 'Contexto y requisitos', '8', 'Respaldo: voz del navegador y texto'],
    ['3', 'Metodología', '9', 'Limitaciones, riesgos y plan para Azure'],
    ['4', 'Voz natural: alternativas y matriz', '10', 'Trazabilidad y conclusión'],
    ['5', 'Avatares: alternativas y matriz', '11', 'Fuentes externas'],
    ['6', 'Prueba mínima y compatibilidad con el flujo actual', '', ''],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
];

const cuerpo = [
  h1('1. Resumen'),
  p('El simulador necesita dos cosas para que la consulta se sienta real: que el doctor y el paciente hablen con voz natural en español y que se vea a quien habla. En este spike comparé tres alternativas para cada parte, medí en el propio simulador las que se podían probar y dejé documentada la elección con sus límites y su respaldo.'),
  leyenda('Tabla 1. Selección'),
  tabla([1900, 3100, 4638], ['Parte', 'Tecnología elegida', 'Por qué'], [
    ['Voz definitiva', 'Azure AI Speech, plan gratuito F0', 'Servicio oficial con las mismas voces que ya usa el simulador (Alex y Camila de Perú, Jorge de México) [F2] y 0,5 millones de caracteres gratis al mes [F1]. Pendiente de la autorización de GitHub Student.'],
    ['Voz en uso (puente)', 'edge-tts por la ruta /api/voz', 'Gratis y sin cuenta, con las mismas voces neuronales. Funciona hoy: ' + latEdge + ' [V].'],
    ['Respaldo de voz', 'Voz del navegador (Web Speech API)', 'Siempre disponible y sin red; una voz fija por personaje (fase 35) [V].'],
    ['Respaldo final', 'Texto en el globo y en el chat', 'Toda frase se ve escrita aunque no haya ninguna voz: ' + pasan(soloTexto) + ' en la prueba «solo texto» [V].'],
    ['Avatar', 'Video en bucle de LivePortrait alternado con la imagen quieta, sincronizado por el volumen del audio', 'Costo cero, fotorrealista, independiente del idioma y del proveedor de voz; ya integrado (16 de 16 con paciente hombre y con paciente mujer) [V].'],
  ]),
  leyenda('Tabla 2. Criterios de aceptación'),
  tabla([3500, 2200, 3938], ['Criterio', 'Dónde', 'Resultado'], [
    ['Matriz comparativa de 2 a 3 alternativas con costo, latencia, idioma y licencias', 'Secciones 4.2 y 5.2', 'Cumplido: 3 alternativas de voz y 3 de avatar, con las cuatro columnas pedidas y más.'],
    ['Prueba mínima de voz y avatar y compatibilidad con el flujo actual', 'Sección 6', `Cumplido: voz medida (${voz.latencia.length * 5} síntesis), navegador, avatares y respaldos; ${pasan(sinVideo)} sin video y ${pasan(soloTexto)} solo texto.`],
    ['Selección documentada con limitaciones y respaldo de texto', 'Secciones 7, 8 y 9', 'Cumplido: cadena de respaldo de cuatro niveles probada y límites declarados.'],
  ]),

  h1('2. Contexto y requisitos'),
  h2('2.1 Qué necesita el simulador'),
  p('El texto de cada intervención lo genera el sistema de agentes (rama de Rodrigo). La voz y el avatar solo lo presentan: no deciden nada clínico. Con eso, los requisitos que me puse son:'),
  vineta('Español latinoamericano, de preferencia peruano, con voces distintas para el doctor, el paciente hombre y la paciente mujer.'),
  vineta('Respuesta rápida: la frase debe empezar a sonar en uno o dos segundos para que el diálogo no se corte.'),
  vineta('Costo cero o casi cero en la etapa académica, sin datos de tarjeta del equipo.'),
  vineta('Compatible con lo que ya existe: servidor FastAPI, frontend HTML y JavaScript sin empaquetador, despliegue en Vercel.'),
  vineta('Licencias que permitan el uso académico y que no obliguen a poner marcas de agua en el simulador.'),
  vineta('Si algo falla, la consulta sigue: nunca debe quedar trabada por la voz o el avatar.'),
  h2('2.2 La situación con Azure'),
  p('La voz definitiva acordada es Azure AI Speech. Para crear el recurso hace falta una suscripción de Azure. La vía para estudiantes, Azure for Students, da 100 USD de crédito por 12 meses sin tarjeta y se valida con el correo de la universidad [F4]. Mi correo institucional está bloqueado, así que no pude validarme por esa vía. Envié una solicitud a GitHub Student Developer Pack, que también da acceso a Azure para estudiantes, y estoy esperando la respuesta.'),
  p('Mientras tanto uso edge-tts (TA-019, rama James): una librería que usa el servicio en línea de lectura en voz alta de Microsoft Edge, con las mismas voces neuronales, sin clave [F5] [E: pruebas/27_voz_humanizada].'),
  h2('2.3 La situación con los avatares'),
  p('Hasta la fase 29 la escena mostraba ilustraciones fijas del doctor y del paciente. Para este spike probé varios caminos para generar un personaje que habla: los espacios gratuitos de Hugging Face fallaron (SadTalker con error de compilación y LivePortrait sin cupo de GPU), y D-ID ponía marca de agua en la prueba gratuita. Al final generé los videos con LivePortrait en Google Colab con GPU T4 gratuita, a partir de imágenes realistas hechas con Gemini y montadas sobre un consultorio en Photopea (fase 34).'),

  h1('3. Metodología'),
  p('Evalué cada alternativa con los mismos criterios. Lo que podía ejecutar en mi equipo lo medí; lo que no (Azure, al que no tengo acceso, y los servicios de avatar de pago) lo tomé de la documentación oficial o de reseñas, citadas en la sección 11.'),
  tabla([2300, 7338], ['Criterio', 'Cómo lo evalué'], [
    ['Costo', 'Precio publicado y cupo gratuito [F]. Para Azure estimé el consumo de una consulta con el texto real de los 43 casos [V].'],
    ['Latencia', `edge-tts: ${voz.latencia.length * 5} síntesis con las voces del simulador, frase corta y larga, 5 veces cada una [V]. Navegador: tiempo hasta que empieza a hablar [V]. Avatares: tiempo de carga de cada video [V].`],
    ['Idioma', 'Voces en español disponibles en cada alternativa, con atención a las de Perú [V] [F].'],
    ['Licencia y condiciones', 'Licencia del software y términos del servicio (marca de agua, uso comercial, servicio no oficial) [F].'],
    ['Compatibilidad', 'Integración con el flujo actual (texto del agente → /api/voz → audio → avatar) y pruebas de punta a punta en Google Chrome [V].'],
    ['Respaldo', 'Qué pasa si la alternativa falla: forcé fallos de red y bloqueé los videos.'],
  ]),

  h1('4. Voz natural: alternativas y matriz'),
  h2('4.1 Alternativas'),
  p([t('A. Azure AI Speech. ', { bold: true }), t('Servicio de voz de Microsoft en la nube, con SDK y API REST. Es la que el equipo había elegido como definitiva; aquí la confirmo con datos.')]),
  p([t('B. edge-tts. ', { bold: true }), t('Librería de Python que pide el audio al servicio de lectura en voz alta de Microsoft Edge. Es la que usa hoy el simulador, en la ruta /api/voz, con el audio transmitido mientras se genera y un reintento [C: backend/server/voice/tts.py, backend/server/api/voice.py].')]),
  p([t('C. Web Speech API. ', { bold: true }), t('La voz que trae el propio navegador. Era la voz del simulador antes de TA-019 y hoy es el respaldo.')]),
  p('También consideré servicios de pago por uso como ElevenLabs, Google Cloud Text-to-Speech u OpenAI, y motores locales como Piper. Los descarté sin medirlos: los de pago piden tarjeta y su cupo gratuito es menor o no apto para uso continuo, y los locales necesitan un servidor con CPU propia, que Vercel no ofrece.'),
  h2('4.2 Matriz comparativa de voz'),
  leyenda('Tabla 3. Voz natural: tres alternativas'),
  tabla([1700, 2646, 2646, 2646], ['Criterio', 'A. Azure AI Speech', 'B. edge-tts (en uso)', 'C. Web Speech API'], [
    ['Costo', ['F0: 0,5 millones de caracteres gratis al mes [F1].', 'Después, pago por uso por millón de caracteres; la tarifa exacta depende de la región y se ve en la calculadora de Azure [F1].'], ['Gratis, sin cuenta ni clave [F5].'], ['Gratis.']],
    ['Latencia', ['No medida: sin acceso todavía.', 'Servicio oficial con SDK que también transmite el audio por trozos.'], [`Primer trozo: mediana ${s(Math.min(...medianas))} a ${s(Math.max(...medianas))} s; picos de ${s(Math.max(...primeros))} s [V].`, `Frase completa: mediana ${s(Math.min(...totales))} a ${s(Math.max(...totales))} s [V].`], [`Empieza a hablar en ${Math.min(...inicioWeb)} a ${Math.max(...inicioWeb)} ms (la primera vez es la más lenta) [V].`]],
    ['Idioma y voces', ['Voces neuronales de Perú (Alex, Camila) y de México (Jorge, Dalia y otras), además de voces HD de México [F2].', 'Son las mismas que usa hoy el simulador.'], [`${vocesEsp} voces en español, entre ellas las 6 del simulador: ${vocesSimulador.map(([v]) => v.replace('Neural', '')).join(', ')} [V].`], [`Dependen del sistema operativo: en este equipo, ${chrome.voces_espanol.length} voces de México (${chrome.voces_espanol.map(v => v.split(' - ')[0].replace('Microsoft ', '')).join(' y ')}); ninguna de Perú [V].`, 'En otro equipo pueden ser otras.']],
    ['Licencia y condiciones', ['Servicio comercial de Microsoft bajo los términos de Azure.', 'Uso permitido con una suscripción.'], ['Librería con licencia LGPLv3 [F5].', 'Usa un servicio de Microsoft no documentado para terceros, sin acuerdo de servicio: puede cambiar o cerrarse sin aviso.'], ['API estándar del navegador, sin restricciones.']],
    ['Sincronía con el avatar', ['Entrega eventos de visema (forma de la boca por fonema) [F7].'], ['Solo límites de palabra; el simulador sincroniza por volumen.'], ['Eventos de inicio y fin; sin audio medible.']],
    ['Integración', ['Cambiar solo tts.stream() en el servidor; la ruta, las voces y el respaldo se reutilizan.'], ['Hecha: /api/voz, una voz por personaje, reintentos, voz constante [V].'], ['Hecha: respaldo con voz fija por personaje [V].']],
    ['Riesgo principal', ['El acceso depende de la autorización de estudiante.'], ['Servicio no oficial; picos de latencia.'], ['Voz robótica y distinta en cada equipo.']],
  ]),
  h2('4.3 ¿Alcanza el plan gratuito de Azure?'),
  p(`El doctor lee al presentar el caso entre ${pres.minimo} y ${pres.maximo} caracteres (mediana ${pres.mediana}) en los ${pres.casos} casos del catálogo [V] [E: 36/resultados/voz.json]. Si una consulta tiene unas 15 intervenciones de unos 100 caracteres (respuestas del paciente y hallazgos), gasta entre 1 500 y 2 000 caracteres. Con 500 000 caracteres al mes [F1], el plan F0 alcanza para unas 250 a 330 consultas al mes. Es una estimación: el largo real de las respuestas depende de cada estudiante.`),

  h1('5. Avatares: alternativas y matriz'),
  h2('5.1 Alternativas'),
  p([t('A. Video pregrabado en bucle (LivePortrait). ', { bold: true }), t('Un video corto por personaje, generado una vez, que se muestra mientras suena la voz; en los silencios vuelve la imagen quieta (su primer fotograma). La boca sigue el volumen del audio, no las sílabas. Es lo que usa hoy el simulador (fase 34).')]),
  p([t('B. Avatar animado en el navegador con visemas. ', { bold: true }), t('Un personaje 2D (Rive) o 3D (TalkingHead, con modelos GLB) que mueve la boca según el fonema. Necesita un personaje dibujado o modelado con sus formas de boca y una voz que entregue visemas o tiempos por palabra [F7] [F8].')]),
  p([t('C. Avatar fotorrealista generado en la nube en tiempo real. ', { bold: true }), t('Servicios como el avatar de Azure AI Speech o D-ID, que devuelven un video del personaje diciendo la frase exacta, por WebRTC [F3] [F9].')]),
  h2('5.2 Matriz comparativa de avatares'),
  leyenda('Tabla 4. Avatares: tres alternativas'),
  tabla([1700, 2646, 2646, 2646], ['Criterio', 'A. Video LivePortrait (en uso)', 'B. Animado con visemas', 'C. Avatar en la nube'], [
    ['Costo', ['Cero: Colab con GPU T4 gratuita, una sola vez por personaje.'], ['Software gratis: TalkingHead es MIT [F7]; el editor y los runtimes de Rive son gratis, pero exportar exige su plan de pago [F8].', 'Costo en horas de diseño del personaje.'], ['Pago por minuto de video, aparte de la voz (Azure) [F1] [F3].', 'D-ID: prueba de 14 días con marca de agua y sin uso comercial [F9].']],
    ['Latencia y peso', [`Video de ${kb(videos)} e imagen de ${kb(imagenes)} por personaje [V].`, `Carga local en ${Math.min(...cargaVideo)} a ${Math.max(...cargaVideo)} ms [V]; después, el cambio es inmediato.`], ['Se dibuja en el navegador: sin espera de red tras cargar el modelo (no medido).'], ['Una sesión de video en vivo por consulta; depende de la red y de la región del servicio [F3] (no medido).']],
    ['Idioma', ['Independiente del idioma: sigue el volumen.'], ['Español sin módulo propio en TalkingHead: necesita visemas de la voz, por ejemplo de Azure [F7].'], ['Mismos idiomas que la voz del servicio [F3].']],
    ['Licencia', ['Código y pesos MIT; los modelos de InsightFace que usa son solo para investigación no comercial [F6]. Válido para el uso académico; para uso comercial habría que reemplazarlos.'], ['MIT (TalkingHead). Los modelos 3D de ejemplo tienen sus propias licencias [F7].'], ['Servicio comercial; la prueba gratuita de D-ID pone marca de agua [F9].']],
    ['Realismo y sincronía', ['Fotorrealista. La boca se mueve con la voz, pero no forma cada sílaba.'], ['Estilizado. La boca forma cada fonema.'], ['Fotorrealista y con sincronía exacta.']],
    ['Integración', ['Hecha: 16 de 16 con paciente hombre y con paciente mujer [V] [E: 34].'], ['Nueva capa de dibujo y personajes por crear.'], ['Clave de pago en el servidor, sesión WebRTC y costo por consulta.']],
    ['Riesgo principal', ['Gesto repetido (bucle de 10,6 s); nuevos personajes requieren Colab.'], ['Tiempo de diseño; estilo distinto al de las fotos actuales.'], ['Costo por uso y dependencia del proveedor.']],
  ]),

  h1('6. Prueba mínima y compatibilidad con el flujo actual'),
  p('El flujo actual es: el agente devuelve el texto → el navegador lo muestra en el globo y en el chat → pide el audio a /api/voz → el audio suena mientras llega → el avatar alterna entre el video y la imagen según el volumen. Con la prueba mínima comprobé cada pieza en mi equipo, con un servidor de prueba aparte (sesiones en memoria, sin tocar Supabase de producción).'),
  leyenda('Tabla 5. Prueba mínima de voz y avatar'),
  tabla([2700, 4438, 2500], ['Prueba', 'Qué se comprobó', 'Resultado'], [
    ['Voz edge-tts (36/01)', `Caracteres de la presentación de los ${pres.casos} casos; voces disponibles; latencia de 3 voces × 2 frases × 5 repeticiones.`, `${latEdge}. Las 6 voces del simulador disponibles [V].`],
    ['Navegador (36/02)', 'Voces del navegador, si reproduce H.264 y cuánto tardan en cargar los videos, en Google Chrome y en el Chromium de Playwright.', `Chrome ${chrome.version.split('.')[0]} y Chromium ${chromium.version.split('.')[0]}: H.264 sí («${chrome.h264}»); 1280×720, 10,57 s [V].`],
    ['Respaldo sin video (36/03)', 'Los videos no cargan (bloqueados).', `${pasan(sinVideo)}: imagen quieta y voz neuronal [V].`],
    ['Respaldo solo texto (36/04)', 'Sin videos, sin /api/voz y sin voz del navegador.', `${pasan(soloTexto)}: la consulta sigue con texto [V].`],
    ['Avatares en la consulta (34)', 'El video solo con audio, alternando en las pausas, del personaje correcto.', '16 de 16 (hombre) y 16 de 16 (mujer) [V].'],
    ['Voz constante (35)', 'Fallos de red forzados en /api/voz.', 'Antes 4 de 7; después 7 de 7 y 8 de 8 [V].'],
    ['Voz humanizada (27)', 'Una voz neuronal por personaje en el navegador real.', '32 de 32 frases con voz neuronal [V].'],
  ]),
  nota('Hice estas pruebas en Windows con Google Chrome 156 y Chromium 153. Firefox, WebKit (Safari) y el celular los probé después, en la tarea TA-020.'),

  h1('7. Selección documentada'),
  h2('7.1 Voz'),
  p('Elijo Azure AI Speech (plan F0) como voz definitiva, con edge-tts como puente mientras llega la autorización. Mis razones:'),
  vineta('Tiene las mismas voces que ya suenan en el simulador, así que el estudiante no notará el cambio [F2].'),
  vineta('El cambio es pequeño: solo la función que pide el audio (tts.stream()). La ruta /api/voz, la elección de voz por personaje, la transmisión por trozos, los reintentos y la voz constante se reutilizan [C: backend/server/voice/tts.py].'),
  vineta('Es un servicio oficial con acuerdo de servicio, a diferencia de edge-tts, que puede dejar de funcionar sin aviso.'),
  vineta('El plan gratuito alcanza para unas 250 a 330 consultas al mes (sección 4.3).'),
  vineta('Entrega visemas, que permitirían en el futuro una boca sincronizada por fonema (alternativa B de avatares).'),
  h2('7.2 Avatar'),
  p('Elijo el video en bucle de LivePortrait alternado con la imagen quieta. Es la única alternativa fotorrealista sin costo, funciona con cualquier proveedor de voz y ya está integrada y probada. Las alternativas B y C quedan como mejoras posibles: B si se adopta Azure y se quiere sincronía por fonema, y C solo si el proyecto contara con presupuesto por minuto de video.'),

  h1('8. Respaldo: voz del navegador y texto'),
  p('La consulta nunca depende de una sola pieza. Cada nivel entra solo si el anterior falla, y el texto está siempre en pantalla:'),
  leyenda('Tabla 6. Cadena de respaldo'),
  tabla([700, 2900, 3538, 2500], ['Nivel', 'Qué se usa', 'Cuándo', 'Evidencia'], [
    ['1', 'Voz neuronal (edge-tts hoy, Azure después)', 'Siempre que responda. Una frase que falla se pide de nuevo hasta 3 veces.', 'Fase 35, escenario A: 7 de 7'],
    ['2', 'Voz del navegador, fija por personaje', 'Solo si la voz neuronal falla desde la primera frase: toda la consulta usa esta voz.', 'Fase 35, escenario B: 8 de 8'],
    ['3', 'Texto en el globo y en el chat', 'Siempre visible. Si la voz neuronal ya sonó y luego falla, la frase se muestra sin voz: nunca con otra voz.', `36/04 solo texto: ${pasan(soloTexto)}`],
    ['Avatar', 'Imagen quieta del personaje', 'Si el video no carga o el navegador no lo reproduce.', `36/03 sin video: ${pasan(sinVideo)}`],
  ]),

  h1('9. Limitaciones, riesgos y plan para Azure'),
  h2('9.1 Limitaciones'),
  vineta('La boca del avatar sigue el volumen, no las sílabas: el movimiento es genérico.'),
  vineta('Hay tres personajes (doctor, paciente hombre, paciente mujer). Las imágenes con gesto de dolor no están integradas, y un personaje nuevo exige volver a generar su video en Colab.'),
  vineta('Los modelos de InsightFace que usa LivePortrait son para uso no comercial; si el proyecto se volviera comercial habría que reemplazarlos [F6].'),
  vineta('Con la voz del navegador, la voz del paciente puede no coincidir con su sexo: el navegador no informa si una voz es de hombre o de mujer.'),
  vineta('No pude medir Azure: comprobaré su latencia real al migrar.'),
  vineta('En este spike solo probé en Windows con Chrome y Chromium.'),
  h2('9.2 Riesgos de mantener edge-tts'),
  vineta(`Picos de latencia de hasta ${s(Math.max(...primeros))} s en este equipo [V]; la fase 35 evita que cambien de voz, pero la frase tarda más en sonar.`),
  vineta('Microsoft puede cambiar o cerrar el servicio que usa edge-tts; ya restringió funciones antes. Si pasa, el simulador cae al nivel 2 de respaldo.'),
  h2('9.3 Plan para Azure AI Speech'),
  vineta('Al llegar la autorización de GitHub Student, crear un recurso de Speech en el plan F0, en una región que tenga las voces de Perú.'),
  vineta('Guardar la clave y la región solo en .env y en Vercel (AZURE_SPEECH_KEY, AZURE_SPEECH_REGION); nunca en el navegador.'),
  vineta('Cambiar tts.stream() para pedir el audio a Azure con las mismas voces; mantener edge-tts y la voz del navegador como respaldo.'),
  vineta('Repetir las pruebas de las fases 34, 35 y 36 y medir la latencia real de Azure para completar la tabla 3.'),
  vineta('Actualizar el aviso de privacidad para mencionar a Microsoft como encargado del audio.'),

  h1('10. Trazabilidad y conclusión'),
  leyenda('Tabla 7. De cada decisión a su evidencia'),
  tabla([3000, 3638, 3000], ['Decisión', 'Dónde está en el código', 'Prueba'], [
    ['Voz neuronal por personaje', 'backend/server/voice/tts.py, backend/server/api/voice.py', 'pruebas/27_voz_humanizada'],
    ['Una voz por personaje toda la consulta', 'speak() en frontend/public/js/simulacion.js', 'pruebas/35_voz_constante'],
    ['Avatar: video e imagen quieta por volumen', 'sceneVideo, setTalking, followVoice en simulacion.js; prepare-avatar-videos.mjs', 'pruebas/34_avatares_hablando'],
    ['Respaldo sin video y solo texto', 'setTalking y speak en simulacion.js', 'pruebas/36_sp006_voz_y_avatar (03 y 04)'],
    ['Medición de voz y navegador', 'medir_voz.py, probar_navegador.cjs', 'pruebas/36_sp006_voz_y_avatar (01 y 02)'],
  ]),
  h2('10.1 Conclusión'),
  p('Para la voz elijo Azure AI Speech, porque es oficial, tiene las mismas voces peruanas que ya usa el simulador, su plan gratuito alcanza para el uso académico y migrar a él cambia una sola función. Mientras llega la autorización de GitHub Student, edge-tts cumple ese papel con buena latencia y una voz constante por personaje. Para el avatar elijo el video de LivePortrait alternado con la imagen quieta: es fotorrealista, gratuito y ya funciona con cualquier voz. Si la voz o el video fallan, la consulta sigue con la voz del navegador o, al final, solo con el texto, y lo probé.'),

  h1('11. Fuentes externas'),
  nota('Las consulté el 4 de noviembre de 2026. Los precios de los servicios cambian: antes de contratar hay que confirmarlos en la página oficial.'),
  tabla([5338, 4300], ['Fuente', 'Dirección'], FUENTES.map(([, texto, url]) => [texto, url])),
];

const doc = new Document({
  creator: 'James Bryam Gutiérrez Rubio',
  title: 'SP-006: Selección de tecnología para voz natural y avatares',
  styles: {
    default: { document: { run: { font: 'Arial', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Arial', size: 32, bold: true }, paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Arial', size: 26, bold: true }, paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: 'vinetas', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, border: { top: { style: BorderStyle.SINGLE, size: 4, color: 'D0D5DD', space: 4 } },
      children: [t('Consulta Médica Virtual · Informe SP-006 · Página ', { size: 17, color: GRIS }), new TextRun({ children: [PageNumber.CURRENT], size: 17, color: GRIS })] })] }) },
    children: [...portada, ...cuerpo],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(salida, buffer);
  console.log(`Informe en ${salida}`);
});
