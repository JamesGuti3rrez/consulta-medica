// Genera «TA-020 Informe de Avance - Avatar conversacional por rol.docx» con las cifras y capturas de las corridas
// (pruebas 34 a 37), para que el informe no pueda contradecir la evidencia.
// Formato de los entregables: A4, márgenes de 2 cm, Arial 11 pt, encabezados de tabla en gris (como TA-019).
// Requiere el paquete docx: npm install --no-save docx@9.5.1 (o NODE_PATH a una carpeta donde esté instalado).
// Uso, desde la raíz: node pruebas/37_ta020_avatar_por_rol/generar_informe.cjs <salida.docx>
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, Footer, PageNumber, LevelFormat, PageBreak, BorderStyle, ImageRun,
} = require('docx');

const raiz = path.resolve(__dirname, '../..');
const leer = ruta => JSON.parse(fs.readFileSync(path.join(raiz, ruta), 'utf8'));
const r37 = nombre => leer(`pruebas/37_ta020_avatar_por_rol/resultados/${nombre}/ta020_registro.json`);
const corridas = {
  chrome: r37('01_chrome'), edge: r37('02_edge'), firefox: r37('03_firefox'), webkit: r37('04_webkit'),
  reducido: r37('05_chrome_reducir_movimiento'), celular: r37('06_chrome_celular'),
};
const escena29 = fs.readFileSync(path.join(raiz, 'pruebas/37_ta020_avatar_por_rol/ejecucion/07_regresion_escena_29.txt'), 'utf8');
const voz35 = fs.readFileSync(path.join(raiz, 'pruebas/37_ta020_avatar_por_rol/ejecucion/08_regresion_voz_constante.txt'), 'utf8');
const sinVideo = leer('pruebas/36_sp006_voz_y_avatar/resultados/sin_video/respaldo_registro.json');
const soloTexto = leer('pruebas/36_sp006_voz_y_avatar/resultados/solo_texto/respaldo_registro.json');
const nav36 = leer('pruebas/36_sp006_voz_y_avatar/resultados/navegador.json');
const salida = process.argv[2] || 'TA-020 Informe de Avance - Avatar conversacional por rol.docx';

const ANCHO = 9638; // A4 (11906) menos márgenes de 1134 a cada lado
const GRIS = '475569';
const pasan = registro => `${registro.comprobaciones.filter(c => c.resultado === 'PASA').length} de ${registro.comprobaciones.length}`;
const resumenTxt = texto => (texto.match(/(\d+ de \d+) comprobaciones pasan/) || [])[1] || 'sin resultado';
const version = (registro, nombre) => `${nombre} ${registro.version.split('.')[0]}`;
const roles = [...new Set(corridas.chrome.turnos.flatMap(turno => turno.responden))];

// Bloques de texto.
const t = (text, options = {}) => new TextRun({ text, ...options });
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
    spacing: { after: 40 }, children: [t(linea, { bold: cabecera, size: 19 })],
  })),
});
const tabla = (anchos, cabecera, filas, { primeraColumna = false } = {}) => new Table({
  width: { size: ANCHO, type: WidthType.DXA },
  columnWidths: anchos,
  rows: [
    ...(cabecera ? [new TableRow({ tableHeader: true, children: cabecera.map((texto, i) => celda(texto, anchos[i], { cabecera: true })) })] : []),
    ...filas.map(fila => new TableRow({ cantSplit: true,
      children: fila.map((texto, i) => celda(texto, anchos[i], { relleno: primeraColumna && i === 0 ? 'F2F2F2' : undefined })) })),
  ],
});

// Figuras: el tamaño sale de la cabecera del PNG.
let numeroFigura = 0;
const figura = (ruta, pie, anchoPx = 560) => {
  const datos = fs.readFileSync(path.join(raiz, ruta));
  const ancho = datos.readUInt32BE(16);
  const alto = datos.readUInt32BE(20);
  numeroFigura += 1;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: 'png', data: datos, transformation: { width: anchoPx, height: Math.round(anchoPx * alto / ancho) } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [t(`Figura ${numeroFigura}. ${pie}`, { italics: true, size: 19, color: GRIS })] }),
  ];
};
const r = carpeta => `pruebas/37_ta020_avatar_por_rol/resultados/${carpeta}`;
const turnoDe = rol => corridas.chrome.turnos.findIndex(turno => turno.responden.includes(rol)) + 2;

const portada = [
  p([t('CONSULTA MÉDICA VIRTUAL  ·  INFORME DE AVANCE', { size: 17, color: GRIS, bold: true })], { spacing: { after: 80 } }),
  p([t('TA-020: Avatar conversacional por rol (reactivado)', { size: 34, bold: true })], { spacing: { after: 80 } }),
  p([t('Doctor y paciente realistas que mueven la boca mientras hablan, un indicador para cada rol y una consulta que sigue funcionando aunque falte el video o la voz', { color: GRIS })], { spacing: { after: 240 } }),
  tabla([2600, 7038], null, [
    ['PBI', 'TA-020 · Avatar conversacional por rol (reactivado)'],
    ['Responsable', 'James Bryam Gutiérrez Rubio'],
    ['Fecha de las ejecuciones', '4 de noviembre de 2026 (hora de Perú, UTC-5)'],
    ['Rama', 'James'],
    ['Evidencia', ['pruebas/37_ta020_avatar_por_rol/ (roles, navegadores y accesibilidad)', 'pruebas/34_avatares_hablando/ (videos de los avatares)', 'pruebas/35_voz_constante/ (una voz por personaje)', 'pruebas/36_sp006_voz_y_avatar/ (respaldos sin video y solo texto)']],
    ['Estado', 'Terminado y probado en Chrome, Edge, Firefox y WebKit, en escritorio y celular.'],
    ['Versión', '1.0'],
  ], { primeraColumna: true }),
  nota('Todo lo que cuento aquí lo ejecuté y lo dejé guardado con su salida y una foto real de la terminal en la carpeta de pruebas indicada. Cuando algo no salió a la primera, lo dejé como intento fallido y explico cómo lo corregí.'),
  leyenda('Contenido'),
  tabla([900, 3919, 900, 3919], ['Sección', 'Tema', 'Sección', 'Tema'], [
    ['1', 'Resumen', '6', 'Pruebas en los navegadores'],
    ['2', 'Cómo estaba antes', '7', 'Degradación accesible'],
    ['3', 'Cómo hice los avatares', '8', 'Intentos fallidos y correcciones'],
    ['4', 'Un indicador para cada rol', '9', 'Limitaciones y pendientes'],
    ['5', 'Sincronización con la voz (sin lip-sync)', '10', 'Trazabilidad y conclusión'],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
];

const filasNavegador = [
  ['Google Chrome', corridas.chrome, version(corridas.chrome, 'Chrome'), 'Escritorio 1440×1000'],
  ['Microsoft Edge', corridas.edge, version(corridas.edge, 'Edge'), 'Escritorio 1440×1000'],
  ['Firefox', corridas.firefox, version(corridas.firefox, 'Firefox'), 'Escritorio 1440×1000'],
  ['WebKit (motor de Safari)', corridas.webkit, `WebKit ${corridas.webkit.version}`, 'Escritorio 1440×1000'],
  ['Chrome, «reducir movimiento»', corridas.reducido, version(corridas.reducido, 'Chrome'), 'Escritorio, preferencia del sistema'],
  ['Chrome en celular', corridas.celular, version(corridas.celular, 'Chrome'), 'Pantalla de 390×844'],
];

const cuerpo = [
  h1('1. Resumen'),
  p('En esta tarea hice que la escena de la consulta muestre a quien está hablando con un avatar realista que mueve la boca mientras suena su voz. El doctor presenta el caso y luego aparece el paciente, hombre o mujer según el caso. Cuando hablan el laboratorio, radiología o el especialista, se ve la escena del doctor y el globo dice qué servicio está hablando.'),
  p('La boca no está sincronizada sílaba por sílaba (no es lip-sync): se mueve mientras hay sonido y se cierra en los silencios. Lo digo así en la sección 5 porque el criterio pide dejarlo explícito.'),
  leyenda('Tabla 1. Criterios de aceptación'),
  tabla([3300, 3500, 2838], ['Criterio', 'Qué hice', 'Resultado'], [
    ['Avatar o indicador de personaje activo para cada rol habilitado', 'Avatar del doctor y del paciente (hombre o mujer); el globo nombra al rol que habla y cambia su ícono; el estado de la conversación dice quién habla.', `Los ${roles.length} roles (${roles.join(', ')}) aparecen con su indicador correcto en todos los navegadores.`],
    ['Sincronización básica visual o estado de habla; explicitar si no hay lip-sync', 'Video del personaje mientras suena la voz e imagen quieta en los silencios; estado «Hablando», «Listo» y «Tu turno». No hay lip-sync: la boca sigue el volumen.', `Chrome ${pasan(corridas.chrome)}, Edge ${pasan(corridas.edge)}, Firefox ${pasan(corridas.firefox)}, WebKit ${pasan(corridas.webkit)}.`],
    ['Pruebas en navegadores definidos y degradación accesible', 'Cuatro navegadores, celular, «reducir movimiento», sin video, solo texto, lectores de pantalla y texto alternativo.', `Reducir movimiento ${pasan(corridas.reducido)}, celular ${pasan(corridas.celular)}, sin video ${pasan(sinVideo)}, solo texto ${pasan(soloTexto)}.`],
  ]),

  h1('2. Cómo estaba antes'),
  p('Antes de esta tarea la escena mostraba ilustraciones fijas de caricatura: el doctor y el paciente no se movían al hablar. Además, cuando hablaba el laboratorio, radiología o el especialista, el globo de la escena seguía diciendo «Doctor (Voz sintetizada)», aunque en el chat sí aparecía el rol correcto. Tampoco había nada para quien usa un lector de pantalla o tiene activada la opción del sistema para reducir el movimiento.'),

  h1('3. Cómo hice los avatares'),
  h2('3.1 Las imágenes y los videos'),
  p('Generé tres personajes realistas con Gemini: el doctor, un paciente hombre y una paciente mujer, con el mismo encuadre de busto y la luz desde la izquierda. Los monté en Photopea sobre una foto de consultorio a 1280×720. Para que hablen usé LivePortrait, que copia los movimientos de la cara de un video guía (una persona hablando de frente durante 4 o 5 segundos) a cada imagen y conserva el consultorio completo.'),
  p('No tengo una GPU en mi equipo, así que primero intenté con los espacios gratuitos de Hugging Face: SadTalker falló al compilar y LivePortrait se quedó sin cupo de GPU. D-ID sí funcionó, pero ponía su marca de agua. Al final lo hice en Google Colab con una GPU T4 gratuita, y ahí también tuve que corregir varias cosas:'),
  vineta('No usé el requirements.txt del proyecto, porque en el Colab actual (Python 3.13) compilaba versiones antiguas desde cero. Instalé solo lo necesario: tyro, onnx, onnxruntime-gpu, pykalman, lmdb, ffmpeg-python, imageio-ffmpeg, rich, albumentations y scikit-image.'),
  vineta('Descargué los pesos del modelo con huggingface_hub.snapshot_download, porque el comando huggingface-cli ya no funciona.'),
  vineta('El video guía tiene que mostrar la cara completa; si no es cuadrado, hay que usar la opción --flag_crop_driving_video.'),
  p('El resultado fue un video MP4 por personaje, de 5,36 segundos a 14 fotogramas por segundo y 1280×720.'),
  h2('3.2 Cómo los preparé para la web'),
  p('Al revisar los videos encontré dos problemas y los corregí con un script (frontend/scripts/prepare-avatar-videos.mjs):'),
  vineta('La imagen original de Photopea y el video no tenían exactamente el mismo color, por la compresión, y el cambio se notaba. Por eso uso como imagen quieta el primer fotograma del propio video, que además tiene la boca cerrada.'),
  vineta('Los videos terminan con la boca abierta, y al repetirse saltaban. Los convertí en un bucle de ida y vuelta (hacia adelante y luego al revés, 10,6 segundos), que no tiene corte.'),
  p(`Cada video pesa entre ${Math.min(...nav36.archivos.filter(a => a.archivo.endsWith('.mp4')).map(a => a.kb))} y ${Math.max(...nav36.archivos.filter(a => a.archivo.endsWith('.mp4')).map(a => a.kb))} KB y cada imagen quieta entre ${Math.min(...nav36.archivos.filter(a => a.archivo.endsWith('-1280.webp')).map(a => a.kb))} y ${Math.max(...nav36.archivos.filter(a => a.archivo.endsWith('-1280.webp')).map(a => a.kb))} KB. Están en frontend/public/assets/avatars/ y los originales en frontend/src/assets/avatars/videos/.`),

  h1('4. Un indicador para cada rol'),
  p('El simulador tiene cinco roles que hablan. Para cada uno el estudiante ve quién habla de tres formas: el avatar de la escena, el nombre y el ícono del globo, y el estado de la conversación en el panel derecho. Al revisar este criterio corregí el globo, que antes decía siempre «Doctor» para los servicios (frontend/public/js/simulacion.js, setSpeaker).'),
  leyenda('Tabla 2. Qué ve el estudiante cuando habla cada rol'),
  tabla([1700, 2700, 2700, 2538], ['Rol', 'Avatar en la escena', 'Globo', 'Estado de la conversación'], [
    ['Doctor', 'Doctor (video al hablar)', '«Doctor (Voz sintetizada)», ícono de voz', '«Doctor hablando»'],
    ['Paciente', 'Paciente hombre o mujer, según el sexo del caso (video al hablar)', '«Paciente», a la izquierda', '«Paciente respondiendo»'],
    ['Laboratorio', 'Escena del doctor (video al hablar)', '«Laboratorio (Voz sintetizada)», ícono de laboratorio', '«Laboratorio hablando»'],
    ['Radiología', 'Escena del doctor (video al hablar)', '«Radiología (Voz sintetizada)», ícono de radiología', '«Radiología hablando»'],
    ['Especialista', 'Escena del doctor (video al hablar)', '«Especialista (Voz sintetizada)», ícono de especialista', '«Especialista hablando»'],
  ]),
  p('Cada rol tiene además su propia voz, y la conserva durante toda la consulta (pruebas/35_voz_constante).'),
  ...figura(`${r('01_chrome')}/1_doctor.png`, 'El doctor presenta el caso: se ve su video mientras habla y el globo dice «Hablando».'),
  ...figura(`${r('01_chrome')}/${turnoDe('Paciente')}_turno_${turnoDe('Paciente') - 1}.png`, 'El paciente responde a la pregunta del estudiante, con su globo a la izquierda.'),
  ...figura(`${r('01_chrome')}/${turnoDe('Laboratorio')}_turno_${turnoDe('Laboratorio') - 1}.png`, 'El laboratorio entrega un resultado: escena del doctor, pero el globo dice «Laboratorio».'),
  ...figura(`${r('01_chrome')}/${turnoDe('Radiología')}_turno_${turnoDe('Radiología') - 1}.png`, 'Radiología entrega su informe con su nombre y su ícono en el globo.'),
  ...figura(`${r('01_chrome')}/${turnoDe('Especialista')}_turno_${turnoDe('Especialista') - 1}.png`, 'El especialista responde la interconsulta.'),

  h1('5. Sincronización con la voz (sin lip-sync)'),
  p('Lo digo de forma explícita: no hay lip-sync. Los videos son un bucle genérico de una boca que habla y no están ligados al texto. Lo que hice es una sincronización por volumen:'),
  vineta('El simulador mide el volumen del audio que está sonando, unas 60 veces por segundo, con la Web Audio API del navegador.'),
  vineta('Mientras hay sonido se ve el video del personaje; en los silencios (comas, pausas y el final de cada frase) vuelve su imagen quieta. La boca espera 140 ms antes de cerrarse para no parpadear entre sílabas.'),
  vineta('El video sigue desde donde se quedó, para que cada palabra no empiece con el mismo gesto.'),
  vineta('Si la voz es la del navegador (respaldo), el volumen no se puede medir: la boca se mueve durante toda la frase.'),
  p('Además de la boca, el globo muestra el estado de habla: «Hablando» mientras habla el personaje, «Listo» al terminar y «Tu turno» en el panel cuando le toca al estudiante.'),
  p(`En las pruebas el video nunca siguió visible con la voz callada más allá del cierre normal de la boca, y en Chrome se vio durante ${corridas.chrome.muestras.con_video} de las ${corridas.chrome.muestras.con_voz} muestras con voz (el resto son las pausas, cuando la boca está cerrada).`),

  h1('6. Pruebas en los navegadores'),
  p('Definí los navegadores que usan los estudiantes en computadoras con Windows: Google Chrome, Microsoft Edge y Firefox. Para Safari usé WebKit, su motor, porque Safari no existe para Windows. También probé Chrome con la pantalla de un celular y con la opción «reducir movimiento».'),
  p('Cada prueba recorre una consulta completa con un turno de cada rol (pruebas/37_ta020_avatar_por_rol/probar_ta020.cjs): la presentación del doctor, una pregunta al paciente, la exploración física, un hemograma, una radiografía y una interconsulta. Toma una muestra de la escena cada 40 ms y comprueba el indicador de cada rol, el estado de habla, el video, la accesibilidad y que no haya errores.'),
  leyenda('Tabla 3. Resultados por navegador'),
  tabla([2500, 1700, 2300, 1300, 1838], ['Navegador', 'Versión', 'Pantalla', 'Video (MP4)', 'Resultado'],
    filasNavegador.map(([nombre, registro, ver, pantalla]) => [nombre, ver, pantalla, registro.h264 ? 'Sí' : 'No', pasan(registro)])),
  p(`Además repetí las pruebas de las fases anteriores, porque cambié el código de la escena: la escena de la consulta (fase 29) dio ${resumenTxt(escena29)} y la voz constante (fase 35) dio ${resumenTxt(voz35)}.`),
  ...figura(`${r('06_chrome_celular')}/1_doctor.png`, 'En el celular el globo va debajo de la imagen para no tapar la cara.', 300),

  h1('7. Degradación accesible'),
  p('Que la consulta funcione aunque falte algo era parte del criterio. Probé cada caso por separado:'),
  leyenda('Tabla 4. Qué pasa cuando falta algo'),
  tabla([2600, 4238, 2800], ['Situación', 'Qué ve y oye el estudiante', 'Prueba'], [
    ['Tiene activado «reducir movimiento» en el sistema', 'No se reproduce el video: queda la imagen quieta. El globo sigue diciendo «Hablando» y la voz suena igual.', `Chrome con reducir movimiento: ${pasan(corridas.reducido)}`],
    ['El video no carga o el navegador no lo reproduce', 'Queda la imagen quieta del personaje y la voz suena igual.', `Videos bloqueados (fase 36): ${pasan(sinVideo)}`],
    ['La voz neuronal falla desde el inicio', 'Toda la consulta habla con la voz del navegador, una voz fija por personaje.', 'Fase 35, escenario B: 8 de 8'],
    ['No hay ninguna voz', 'Cada frase se ve escrita en el globo y en el chat, y la consulta sigue.', `Solo texto (fase 36): ${pasan(soloTexto)}`],
    ['Usa un lector de pantalla', 'El chat está marcado como registro de conversación y el estado como aviso, así que el lector anuncia cada intervención y de quién es el turno. La imagen tiene un texto alternativo con el personaje en escena y el video está oculto para el lector.', 'Comprobado en las 6 corridas de la tabla 3'],
    ['Usa un celular', 'El globo va debajo de la imagen.', `Chrome en 390×844: ${pasan(corridas.celular)}`],
  ]),

  h1('8. Intentos fallidos y correcciones'),
  tabla([3000, 6638], ['Qué pasó', 'Cómo lo corregí'], [
    ['Al probar los avatares, el servidor de prueba usaba un servicio de RAG externo que no estaba levantado y el paciente no respondía.', 'Inicié el servidor de prueba con el RAG local (fase 34, intento 1).'],
    ['Una caída de internet hizo fallar al modelo de lenguaje y a la voz a la vez.', 'Repetí la prueba cuando volvió la conexión (fase 34, intento 2).'],
    ['El doctor cambiaba de voz entre frases: una frase lenta pasaba a la voz del navegador.', 'Cada consulta conserva una voz; los fallos se reintentan sin cambiar de voz (fase 35).'],
    ['Escribí que el Chromium de pruebas no reproducía MP4, y no era cierto en Windows.', 'Lo corregí y probé el caso sin video bloqueando los videos (fase 36).'],
    ['El texto alternativo de la imagen se medía a mitad del cambio de personaje.', 'La prueba lo mide fuera de los 180 ms del cambio (fase 37, intento 1).'],
    ['En Firefox la prueba vio 480 ms de video «sin audio» al empezar la consulta.', 'El audio ya sonaba, pero Firefox deja su tiempo en cero al principio. La prueba ahora mira si el audio está en reproducción (fase 37, intento 2).'],
    ['La prueba de la escena de la fase 29 esperaba «Doctor hablando» cuando habla el laboratorio, y se quedó esperando.', 'Era el comportamiento nuevo y correcto: ahora el estado dice «Laboratorio hablando». Actualicé esa prueba para aceptar el nombre de cada rol (fase 37, intento 3).'],
    ['Las capturas de los turnos salían sin globo, y en una el globo del especialista aparecía sobre el paciente.', 'Las tomaba a un tiempo fijo, antes de que llegara la respuesta o justo durante los 180 ms del cambio de imagen. Ahora la captura espera a que el rol esté hablando, y agregué una comprobación de que la imagen que se ve es la del personaje en escena (fase 37, intento 4).'],
    ['Con esa comprobación nueva, Firefox mostró un error real: al cambiar del doctor al paciente se veía un instante al doctor otra vez, porque Firefox mantiene la imagen anterior hasta decodificar la nueva.', 'Ahora la imagen vuelve a aparecer solo cuando la nueva ya está decodificada (setScene en simulacion.js), y repetí todas las pruebas (fase 37, intento 5).'],
  ]),

  h1('9. Limitaciones y pendientes'),
  vineta('No hay lip-sync: la boca sigue el volumen, no las sílabas. Con Azure AI Speech, que entrega la forma de la boca por fonema, se podría mejorar en el futuro.'),
  vineta('El laboratorio, radiología y el especialista no tienen avatar propio: hablan en la escena del doctor con su nombre en el globo.'),
  vineta('Las imágenes del paciente con gesto de dolor todavía no están integradas.'),
  vineta('Safari lo probé con WebKit en Windows, no en un Mac o iPhone real.'),
  vineta('LivePortrait usa modelos de InsightFace que solo permiten uso no comercial. Para este proyecto académico no es un problema.'),

  h1('10. Trazabilidad y conclusión'),
  leyenda('Tabla 5. De cada criterio a su código y su prueba'),
  tabla([2800, 3838, 3000], ['Criterio', 'Código', 'Prueba'], [
    ['Indicador por rol', 'setSpeaker en simulacion.js; globo doctor-name y doctor-icon en simulacion.html', 'probar_ta020.cjs, tabla 3'],
    ['Avatar del doctor y del paciente', 'setScene, sceneVideo en simulacion.js; prepare-avatar-videos.mjs', 'pruebas/34_avatares_hablando'],
    ['Estado de habla y sincronía por volumen', 'setTalking, followVoice, stopLips en simulacion.js', 'probar_ta020.cjs y pruebas/34'],
    ['Reducir movimiento', 'setTalking (prefers-reduced-motion)', '05_chrome_reducir_movimiento'],
    ['Lectores de pantalla', 'role="log" y role="status" con aria-live en simulacion.html', 'probar_ta020.cjs'],
    ['Sin video y solo texto', 'setTalking y speak en simulacion.js', 'pruebas/36_sp006_voz_y_avatar'],
  ]),
  h2('10.1 Conclusión'),
  p('Con esta tarea la consulta muestra siempre quién está hablando: el doctor y el paciente con un avatar realista que mueve la boca mientras suena su voz, y los servicios con su nombre en el globo. La boca no está sincronizada por sílaba, y así lo dejo dicho; está sincronizada con el volumen de la voz, que es suficiente para que se vea natural. Lo probé en Chrome, Edge, Firefox y WebKit, en escritorio y en celular, y la consulta sigue funcionando para quien reduce el movimiento, usa un lector de pantalla o se queda sin video o sin voz.'),
];

const doc = new Document({
  creator: 'James Bryam Gutiérrez Rubio',
  title: 'TA-020: Avatar conversacional por rol',
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
      children: [t('Consulta Médica Virtual · Informe de avance TA-020 · Página ', { size: 17, color: GRIS }), new TextRun({ children: [PageNumber.CURRENT], size: 17, color: GRIS })] })] }) },
    children: [...portada, ...cuerpo],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(salida, buffer);
  console.log(`Informe en ${salida}`);
});
