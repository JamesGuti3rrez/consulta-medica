// Genera «TA-020 Informe Correctivo - Boca por silaba y balanceo de la cabeza.docx» con las cifras y capturas de las
// corridas de esta carpeta, para que el informe no pueda contradecir la evidencia.
// Formato de los entregables: A4, márgenes de 2 cm, Arial 11 pt, encabezados de tabla en gris (como TA-020).
// Requiere el paquete docx: npm install --no-save docx@9.5.1 (o NODE_PATH a una carpeta donde esté instalado).
// Uso, desde la raíz: node pruebas/38_labios_por_silaba/generar_informe.cjs <salida.docx>
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, Footer, PageNumber, LevelFormat, PageBreak, BorderStyle, ImageRun,
} = require('docx');

const raiz = path.resolve(__dirname, '../..');
const fase = 'pruebas/38_labios_por_silaba';
const leer = ruta => JSON.parse(fs.readFileSync(path.join(raiz, ruta), 'utf8'));
const texto = ruta => fs.readFileSync(path.join(raiz, ruta), 'utf8');
const registro = nombre => leer(`${fase}/resultados/${nombre}/labios_registro.json`);
const corridas = {
  chrome: registro('01_chrome'), edge: registro('02_edge'), firefox: registro('03_firefox'),
  reducido: registro('04_chrome_reducir_movimiento'), celular: registro('05_chrome_celular'),
  bloqueadas: registro('06_chrome_capas_bloqueadas'),
};
const medicion = leer(`${fase}/resultados/00_antes_y_despues/medicion.json`);
const unitarias = texto(`${fase}/ejecucion/07_pruebas_unitarias_silabas.txt`);
const regresion = texto(`${fase}/ejecucion/08_regresion_ta020.txt`);
const backend = texto(`${fase}/ejecucion/09_suite_backend.txt`);
const video = leer(`${fase}/resultados/video/montaje.json`);
const salida = process.argv[2] || 'TA-020 Informe Correctivo - Boca por silaba y balanceo de la cabeza.docx';

const ANCHO = 9638; // A4 (11906) menos márgenes de 1134 a cada lado
const GRIS = '475569';
const pasan = r => `${r.comprobaciones.filter(c => c.resultado === 'PASA').length} de ${r.comprobaciones.length}`;
const detalle = (r, inicio) => (r.comprobaciones.find(c => c.descripcion.startsWith(inicio)) || {}).detalle || '';
const nodePasan = (unitarias.match(/ℹ pass (\d+)/) || [])[1];
const nodeFallan = (unitarias.match(/ℹ fail (\d+)/) || [])[1];
const resumenTxt = t => (t.match(/(\d+ de \d+) comprobaciones pasan/) || [])[1] || 'sin resultado';
const pytest = (backend.match(/(\d+) passed/) || [])[1];
const pytestSaltadas = (backend.match(/(\d+) skipped/) || [])[1];
const version = (r, nombre) => `${nombre} ${r.version.split('.')[0]}`;
const ritmo = detalle(corridas.chrome, 'cambia de forma').replace(' por segundo', '').replace('.', ',');
const giro = detalle(corridas.chrome, 'el balanceo es leve').replace('.', ',');
const antes = Object.fromEntries(medicion.antes.map(m => [m.personaje, m]));
const NOMBRES = { doctor: 'Doctor', 'paciente-hombre': 'Paciente hombre', 'paciente-mujer': 'Paciente mujer' };
const coma = n => String(n).replace('.', ',');
const kbCapas = Math.round(fs.readdirSync(path.join(raiz, 'frontend/public/assets/avatars'))
  .filter(f => /-(boca-[a-zA-Z]+|cabeza)\.webp$/.test(f))
  .reduce((suma, f) => suma + fs.statSync(path.join(raiz, 'frontend/public/assets/avatars', f)).size, 0) / 1000);

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
const figura = (ruta, pie, anchoPx = 560, altoMax = 760) => {
  const datos = fs.readFileSync(path.join(raiz, ruta));
  const ancho = datos.readUInt32BE(16);
  const alto = datos.readUInt32BE(20);
  let w = anchoPx;
  let h = Math.round(anchoPx * alto / ancho);
  if (h > altoMax) { w = Math.round(w * altoMax / h); h = altoMax; }
  numeroFigura += 1;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: 'png', data: datos, transformation: { width: w, height: h } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [t(`Figura ${numeroFigura}. ${pie}`, { italics: true, size: 19, color: GRIS })] }),
  ];
};
const r = carpeta => `${fase}/resultados/${carpeta}`;
const e = nombre => `${fase}/ejecucion/${nombre}_terminal.png`;

const portada = [
  p([t('CONSULTA MÉDICA VIRTUAL  ·  INFORME DE TRABAJO CORRECTIVO', { size: 17, color: GRIS, bold: true })], { spacing: { after: 80 } }),
  p([t('TA-020 (correctivo): Boca por sílaba y balanceo de la cabeza', { size: 34, bold: true })], { spacing: { after: 80 } }),
  p([t('Los avatares ya no cambian de tamaño al hablar: la boca sigue las sílabas de lo que dicen y la cabeza se balancea apenas, sobre la misma imagen quieta', { color: GRIS })], { spacing: { after: 240 } }),
  tabla([2600, 7038], null, [
    ['PBI', 'TA-020 · Avatar conversacional por rol (trabajo correctivo)'],
    ['Responsable', 'James Bryam Gutiérrez Rubio'],
    ['Fecha de las ejecuciones', '11 de noviembre de 2026 (hora de Perú, UTC-5)'],
    ['Rama', 'James; unida a main en el commit e50a4d5 y publicada en https://consulta-medica-three.vercel.app'],
    ['Evidencia', [`${fase}/ (pruebas, mediciones, salidas y fotos de la terminal)`, 'Video - Antes y despues de la correccion.mp4 (junto a este informe)']],
    ['Estado', 'Terminado, probado en Chrome, Edge y Firefox (escritorio y celular) y publicado.'],
    ['Versión', '1.0'],
  ], { primeraColumna: true }),
  nota('Todo lo que cuento aquí lo ejecuté y lo dejé guardado con su salida y una foto real de la terminal en la carpeta de pruebas indicada. Cuando algo no salió a la primera, lo dejé como intento fallido y explico cómo lo corregí.'),
  leyenda('Contenido'),
  tabla([900, 3919, 900, 3919], ['Sección', 'Tema', 'Sección', 'Tema'], [
    ['1', 'Resumen', '6', 'Video de demostración'],
    ['2', 'Qué estaba mal', '7', 'Degradación accesible'],
    ['3', 'Alternativas que evalué', '8', 'Intentos fallidos y correcciones'],
    ['4', 'Cómo lo corregí', '9', 'Limitaciones y pendientes'],
    ['5', 'Pruebas', '10', 'Trazabilidad y conclusión'],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
];

const filasNavegador = [
  ['Google Chrome', corridas.chrome, version(corridas.chrome, 'Chrome'), 'Escritorio 1440×1000'],
  ['Microsoft Edge', corridas.edge, version(corridas.edge, 'Edge'), 'Escritorio 1440×1000'],
  ['Firefox', corridas.firefox, version(corridas.firefox, 'Firefox'), 'Escritorio 1440×1000'],
  ['Chrome, «reducir movimiento»', corridas.reducido, version(corridas.reducido, 'Chrome'), 'Escritorio, preferencia del sistema'],
  ['Chrome en celular', corridas.celular, version(corridas.celular, 'Chrome'), 'Pantalla de 390×844'],
  ['Chrome, capas bloqueadas', corridas.bloqueadas, version(corridas.bloqueadas, 'Chrome'), 'Escritorio; bocas y cabeza sin cargar'],
];
const maxAntes = Math.max(...medicion.antes.map(m => m.escala_max_pct));
const peorAntes = medicion.antes.find(m => m.escala_max_pct === maxAntes);

const cuerpo = [
  h1('1. Resumen'),
  p('En la TA-020 los avatares hablaban con un video en bucle hecho con LivePortrait, que se mostraba mientras sonaba la voz y se cambiaba por la imagen quieta en cada pausa. Al usarlo noté tres problemas: la cabeza se agrandaba al hablar y volvía a su tamaño al callar, la boca no decía lo que se oía (se movía por volumen, sin lip-sync) y algunos gestos se veían raros.'),
  p(`En este trabajo correctivo reemplacé los videos por capas transparentes sobre la imagen quieta: una capa con la cabeza y cuatro con formas de boca, generadas a partir de la propia imagen. La boca cambia de forma por sílaba según el texto que se está diciendo, y la cabeza se balancea levemente (intensidad 0,4) solo mientras el personaje habla. En silencio no se muestra ninguna boca y la cara queda igual a la imagen original. Las capas pesan ${kbCapas} KB en total, contra 1 103 KB de los tres videos.`),
  leyenda('Tabla 1. Problemas, corrección y resultado'),
  tabla([2700, 3800, 3138], ['Problema', 'Corrección', 'Resultado medido'], [
    ['La cabeza cambiaba de tamaño al empezar y terminar cada frase', 'La cabeza es una capa idéntica a la imagen quieta; solo gira y se desplaza un poco, nunca cambia de escala', `Antes: hasta +${coma(maxAntes.toFixed(1))} % (${NOMBRES[peorAntes.personaje].toLowerCase()}). Ahora: la capa de la cabeza tiene escala ${coma(Math.max(...medicion.despues.map(d => Math.abs(d.cabeza_escala_pct))).toFixed(2))} % frente a la imagen`],
    ['La boca se movía por volumen y no decía lo que se oía', 'Boca por sílaba: cada sílaba toma la forma de su vocal (A, E/I, O/U o pequeña); M, B y P cierran la boca', `Chrome: ${ritmo} cambios de boca por segundo de voz, con las cuatro formas`],
    ['Gestos raros copiados de la grabación', 'Sin video: solo cambian la boca y una inclinación suave de la cabeza', `Giro máximo ${giro} y desplazamiento menor de 1 píxel`],
    ['Boca chueca en los primeros prototipos', 'Bocas deformadas desde la imagen quieta, siempre alineadas y simétricas', 'Cada boca solo cambia su propia zona: 0 píxeles distintos fuera de ella'],
  ]),

  h1('2. Qué estaba mal'),
  p('Lo primero que vi fue que, al hablar, la cabeza del personaje «crecía» respecto de la imagen quieta y, al callar, volvía a su tamaño. Como la página cambiaba entre el video y la imagen en cada pausa (comas y final de frase), el salto se repetía varias veces por oración.'),
  p(`Para saber por qué, medí cada fotograma de los tres videos de la TA-020 (commit ${medicion.antes_commit}) contra su imagen quieta. Busqué los mismos puntos de la cara en los dos y calculé la escala, el giro y el desplazamiento de la cabeza (medir_antes_y_despues.py). El archivo y el encuadre eran correctos: el primer fotograma era casi igual a la imagen. El problema estaba dentro del video: LivePortrait copió también el movimiento de mi cabeza al grabarme, y la cabeza se acercaba, se alejaba y giraba.`),
  leyenda('Tabla 2. Tamaño de la cabeza en los videos de la TA-020, frente a la imagen quieta'),
  tabla([2400, 1500, 1700, 2000, 2038], ['Personaje', 'Fotogramas', 'Escala media', 'Escala máxima', 'Giro máximo'],
    medicion.antes.map(m => [NOMBRES[m.personaje], String(m.fotogramas), `${m.escala_media_pct > 0 ? '+' : ''}${coma(m.escala_media_pct.toFixed(1))} %`,
      `+${coma(m.escala_max_pct.toFixed(1))} % (≈ ${coma(m.salto_max_px)} px)`, `${coma(m.giro_max_grados.toFixed(1))}°`])),
  p(`Un ${coma(maxAntes.toFixed(1))} % parece poco, pero en una cabeza de unos ${peorAntes.tamano_cabeza_px} píxeles son ${coma(peorAntes.salto_max_px)} píxeles que aparecen y desaparecen de golpe en cada pausa. Los «gestos raros» venían del mismo lugar: cejas, inclinaciones y expresiones de mi grabación.`),
  ...figura(r('00_antes_y_despues') + '/figura_salto_de_la_cabeza.png', 'Antes: a la izquierda de cada par la imagen quieta y a la derecha el fotograma del video con la cabeza más grande. Las líneas amarillas están en el mismo lugar en las dos.', 470),
  p('Además, como ya decía el informe de la TA-020, no había lip-sync: el video era un bucle genérico de una boca que habla y no estaba ligado a lo que se decía.'),

  h1('3. Alternativas que evalué'),
  p('El profesor sugirió Live-Avatar (Quark-Vision, Alibaba), un modelo que genera el video de una persona hablando a partir de una foto y un audio, con los labios sincronizados. Lo revisé y lo comparé con mi equipo:'),
  leyenda('Tabla 3. Lo que pide Live-Avatar y lo que tengo'),
  tabla([2600, 3800, 3238], ['Aspecto', 'Live-Avatar', 'Mi equipo y servicios gratuitos'], [
    ['Tarjeta gráfica', 'Una GPU de 80 GB (48 GB en FP8); 5 GPU H800 para tiempo real', 'Gráfica integrada Intel, unos 2 GB compartidos'],
    ['Memoria', 'Solo el modelo (14 mil millones de parámetros) ocupa unos 28 GB', '16 GB de RAM'],
    ['Nube gratuita', 'No hay demo pública ni API', 'Colab y Kaggle dan una T4 de 16 GB, menos de un tercio de lo mínimo'],
    ['Respuestas del LLM', 'Habría que generar el video de cada respuesta en el momento', 'Sin servidor con GPU no es posible; Vercel no tiene GPU'],
  ]),
  p('Live-Avatar quedó descartado por costo y hardware, y lo dejo como trabajo futuro. Elegí una solución que corre en el navegador sin GPU y que funciona con cualquier frase, incluidas las que el LLM inventa en el momento: cambiar la forma de la boca según las sílabas del texto que se está diciendo. El español se pronuncia casi como se escribe, así que las sílabas del texto son una buena guía de la boca.'),

  h1('4. Cómo lo corregí'),
  h2('4.1 Prototipos y decisiones'),
  p('Antes de tocar la aplicación hice un prototipo en el navegador con los tres personajes, para decidir con imágenes y no con suposiciones. Pasó por tres versiones:'),
  vineta('Versión 1: bocas recortadas de fotogramas de los videos y una forma por cada letra. La boca cambiaba unas 14,9 veces por segundo (69 ms por forma) y se veía «tiritar». Además la forma de la E mostraba demasiados dientes, como una sonrisa.'),
  vineta('Versión 2: una forma por sílaba, con un tiempo mínimo en cada una y un fundido corto. Bajó a 4,7 cambios por segundo (216 ms por forma) y el tiritar desapareció, pero a veces la boca se veía chueca: venía de fotogramas donde la cara estaba algo girada y con las asimetrías de mi forma de hablar.'),
  vineta('Versión 3 (la elegida): las bocas se generan deformando los labios de la propia imagen quieta y dibujando el interior de la boca. Salen siempre alineadas y simétricas, y no hay que grabar nada.'),
  p('En el mismo prototipo probé tres tipos de balanceo (ninguno, solo la cabeza o toda la escena como cámara en mano) con una intensidad de 0 a 2. Elegí balancear solo la cabeza, con intensidad 0,4: se nota que el personaje está vivo, pero no distrae.'),
  ...figura(r('00_antes_y_despues') + '/figura_versiones_de_la_boca_paciente-hombre.png', 'Las bocas «A» (arriba) y «E» (abajo) del paciente en cada versión. En la v1 y la v2 vienen del video; en la final se generan desde la imagen quieta.', 470),
  h2('4.2 Las capas de la cara'),
  p('El script frontend/scripts/generar-bocas.py ubica los labios en cada imagen quieta y genera, a 1280×720 y con fondo transparente, una capa con la cabeza (para el balanceo) y cuatro bocas: pequeña, A, E/I y O/U. Como todas salen de la misma imagen, calzan exactamente con ella. La capa de la cabeza está siempre encima de la imagen (así nunca se alternan) y en silencio no se muestra ninguna boca.'),
  ...figura(r('00_antes_y_despues') + '/figura_bocas_finales.png', 'Las formas de boca de cada personaje, tal como se ven en la escena (acercamiento a la boca).', 600),
  p(`Lo comprobé con el mismo método con que medí los videos: la capa de la cabeza tiene escala ${coma(Math.max(...medicion.despues.map(d => Math.abs(d.cabeza_escala_pct))).toFixed(2))} % y giro ${coma(Math.max(...medicion.despues.map(d => Math.abs(d.cabeza_giro_grados))).toFixed(2))}° frente a la imagen quieta, en los tres personajes. Su color difiere en promedio ${coma(Math.max(...medicion.despues.map(d => d.cabeza_diferencia_media)).toFixed(1))} niveles de 255 (como máximo ${Math.max(...medicion.despues.map(d => d.cabeza_diferencia_max))}, en pocos píxeles), por la compresión WebP; como la capa está siempre visible, esa diferencia no aparece ni desaparece. Cada boca deja intactos todos los píxeles fuera de su zona. Las capas se guardan en el repositorio porque el build de Vercel no tiene OpenCV para generarlas.`),
  h2('4.3 La boca por sílaba'),
  p('El módulo frontend/public/js/labios.js convierte el texto en una línea de sílabas y decide qué boca se ve en cada momento:'),
  vineta('Cada sílaba toma la forma de su vocal. Si hay dos vocales seguidas manda la más abierta: en «bue» manda la U (boca redonda) y en «ai», la A.'),
  vineta('Las consonantes no cambian la boca, salvo M, B y P, que la cierran un instante, y F, que la deja pequeña.'),
  vineta('La puntuación cierra la boca: en las comas y los puntos se ve la imagen quieta.'),
  vineta('Con la voz neuronal el reloj de sílabas avanza solo mientras suena el audio, y en cada pausa salta al inicio de la frase siguiente y ajusta la velocidad. Así la boca no se adelanta ni se atrasa en frases largas.'),
  vineta('Con la voz del navegador (respaldo) el reloj avanza solo y cada aviso de palabra lo corrige.'),
  h2('4.4 El balanceo de la cabeza'),
  p('Mientras el personaje habla, la capa de la cabeza gira y se desplaza muy poco, combinando ondas lentas para que no se note un ciclo. Con intensidad 0,4 el giro máximo es de medio grado y el desplazamiento menor de un píxel. El movimiento entra y sale suave y se detiene en unos 0,7 segundos al terminar de hablar. Con «reducir movimiento» activado en el sistema no se anima nada.'),

  h1('5. Pruebas'),
  p(`Escribí ${nodePasan} pruebas unitarias para la lógica de sílabas (frontend/tests/labios.test.mjs) y una prueba en el navegador (${fase}/probar_labios.cjs) que recorre una consulta real: la presentación del doctor, una pregunta al paciente y un hemograma. Toma una muestra de la escena cada 40 ms y comprueba la boca, el balanceo, la alineación de las capas y que no haya errores.`),
  leyenda('Tabla 4. Resultados por navegador'),
  tabla([2700, 1500, 2700, 2738], ['Corrida', 'Versión', 'Pantalla', 'Resultado'],
    filasNavegador.map(([nombre, reg, ver, pantalla]) => [nombre, ver, pantalla, `${pasan(reg)} comprobaciones`])),
  leyenda('Tabla 5. Otras pruebas'),
  tabla([3800, 3600, 2238], ['Prueba', 'Qué comprueba', 'Resultado'], [
    ['Unitarias de sílabas (node --test)', 'Sílabas, vocal que manda, cierres de M, B y P, pausas y ritmo', `${nodePasan} pasan, ${nodeFallan} fallan`],
    ['Medición antes y después', 'Escala de la cabeza en los videos; escala y giro de la capa de la cabeza; bocas solo en su zona', /FALLA/.test(texto(`${fase}/ejecucion/00_medicion_antes_y_despues.txt`)) ? 'FALLA' : 'PASA'],
    ['Regresión de la TA-020 (fase 37)', 'Indicador por rol, estados de habla, accesibilidad', `${resumenTxt(regresion)} comprobaciones`],
    ['Suite completa del backend (pytest)', 'Que el resto del simulador siga igual', `${pytest} pasan, ${pytestSaltadas} saltadas`],
  ]),
  p(`En Chrome la boca estuvo abierta en ${corridas.chrome.muestras.con_boca} de las ${corridas.chrome.muestras.con_voz} muestras con voz; el resto son los cierres de M, B, P y las pausas. Nunca quedó abierta con la voz callada más allá del cierre normal (${detalle(corridas.chrome, 'en silencio')}).`),
  ...figura(r('01_chrome') + '/1_doctor_hablando.png', 'Chrome: el doctor presenta el caso con la boca abierta en una sílaba.', 560),
  ...figura(r('01_chrome') + '/2_turno_1.png', 'Chrome: el paciente responde a la pregunta del estudiante.', 560),
  ...figura(r('05_chrome_celular') + '/1_doctor_hablando.png', 'En el celular (390×844) las capas siguen alineadas con la imagen.', 300),

  h1('6. Video de demostración'),
  p(`Junto a este informe está el archivo «Video - Antes y despues de la correccion.mp4» (${video.duracion_total_s} segundos, con sonido). Lo grabé en Chrome con las dos versiones del simulador, la de la TA-020 (commit ${medicion.antes_commit}) y la corregida, en la misma consulta: la presentación del doctor y una pregunta al paciente. Tiene tres partes:`),
  vineta(`Antes (${video.antes.duracion_s} s): los videos de LivePortrait. Se ve el cambio de tamaño de la cabeza en cada pausa.`),
  vineta(`Después (${video.despues.duracion_s} s): la boca por sílaba y el balanceo de 0,4.`),
  vineta(`Después, de cerca (${video.acercamiento.duracion_s} s): la misma grabación ampliada a la cara, para ver las formas de la boca.`),
  p('La voz se graba aparte porque el navegador de pruebas no graba sonido. Para que coincidan, al inicio de cada grabación la página muestra un destello de color y anota su hora; con ese fotograma el script montar_video.py coloca cada audio en su lugar (con la precisión de un fotograma, 40 ms).'),
  p(`Para comprobar la sincronía saqué del video los fotogramas alrededor del primer sonido audible de la parte «Después». La boca está cerrada antes del sonido, empieza a moverse unos 120 ms después y se abre del todo a los 160 ms, en la sílaba «Mar» de «Martín», que empieza con la M (labios cerrados).`),
  ...figura(r('video') + '/tira_primer_sonido.png', 'La boca del doctor, fotograma a fotograma (40 ms), alrededor del primer sonido audible de la parte «Después» del video.', 600),
  ...figura(r('video') + '/fotograma_antes.png', 'Fotograma de la parte «Antes»: con el video de LivePortrait el doctor sonríe y cambia la expresión que tiene en su imagen quieta.', 500),
  ...figura(r('video') + '/fotograma_cerca.png', 'Fotograma de la parte «Después, de cerca»: la boca en una sílaba con A.', 500),

  h1('7. Degradación accesible'),
  p('La TA-020 pedía que la consulta funcione aunque falte algo. Lo volví a probar con la versión corregida:'),
  leyenda('Tabla 6. Qué pasa cuando falta algo'),
  tabla([2600, 4238, 2800], ['Situación', 'Qué ve y oye el estudiante', 'Prueba'], [
    ['Tiene activado «reducir movimiento»', 'No se abre la boca ni se balancea la cabeza: queda la imagen quieta, con el globo diciendo «Hablando» y la voz normal.', `Chrome con reducir movimiento: ${pasan(corridas.reducido)}`],
    ['Las imágenes de boca y cabeza no cargan', 'Queda la imagen quieta del personaje, la voz suena y la consulta sigue.', `Capas bloqueadas: ${pasan(corridas.bloqueadas)}`],
    ['No hay voz neuronal', 'Habla la voz del navegador y la boca sigue sus avisos de palabra.', 'Prueba unitaria «sin medir la voz, el reloj avanza solo y sigue los avisos de palabra»'],
    ['Usa un lector de pantalla', 'Las capas están ocultas para el lector (aria-hidden); se mantienen el registro del chat y el estado de la TA-020.', `Regresión de la TA-020: ${resumenTxt(regresion)}`],
    ['Usa un celular', 'Las capas se ajustan a la imagen igual que en escritorio.', `Chrome en 390×844: ${pasan(corridas.celular)}`],
  ]),

  h1('8. Intentos fallidos y correcciones'),
  tabla([3400, 6238], ['Qué pasó', 'Cómo lo corregí'], [
    ['Prototipo v1: la boca cambiaba con cada letra, unas 15 veces por segundo, y tiritaba.', 'Pasé a una forma por sílaba con un tiempo mínimo en cada una (v2: 4,7 cambios por segundo).'],
    ['Prototipo v2: a veces la boca se veía chueca, porque venía de fotogramas del video con la cara girada.', 'Generé las bocas desde la imagen quieta (v3), así siempre quedan alineadas.'],
    ['Primer intento de la v3: abertura demasiado ancha, interior morado de dibujo animado, dientes muy blancos y la O sin forma redonda.', 'Ajusté la abertura, el color del interior y los dientes, y le di a la O su forma redonda.'],
    ['En Firefox, al terminar el turno la cabeza seguía moviéndose un poco (0,06°) cuando la prueba lo revisaba (10 de 11).', 'El freno del balanceo dependía de los fotogramas por segundo y Firefox sin ventana dibuja menos. Lo hice depender del tiempo: ahora se detiene en unos 0,7 s en cualquier navegador.'],
    ['Al agregar el modo «capas bloqueadas» a la prueba, las tres primeras corridas terminaron con un error de la prueba («tramos is not defined»), aunque todas las comprobaciones del simulador pasaban.', 'Era un error mío en la prueba (una variable quedó dentro de un bloque). Lo corregí y repetí todas las corridas; las fallidas están en intentos/01_variable_tramos_fuera_de_alcance.'],
    ['La prueba de la TA-020 (fase 37) exigía ver el video mientras el personaje habla, y ya no hay video.', 'Era el comportamiento nuevo y correcto. Actualicé esa prueba para que también cuente una capa de boca visible como «boca en movimiento».'],
    ['Con las capas bloqueadas, en 2 de 10 corridas hubo una sola muestra (40 ms) sin la imagen visible, justo al pasar de la escena del paciente a la del doctor (intentos/02).', 'Al terminar un cambio de personaje la imagen vuelve con un fundido de 250 ms que empieza en opacidad 0, y la prueba solo excusaba las muestras marcadas como «cambiando». Ahora cuenta como parte del cambio los 300 ms siguientes. No pude reproducirlo en 6 corridas más, así que lo dejo como observación: dura un fotograma, dentro del fundido del cambio.'],
    ['La primera medición falló aunque la cabeza no cambiaba de tamaño (intentos/04): exigía que la capa de la cabeza fuera idéntica a la imagen con un margen de 2 niveles de color, y la compresión WebP llega a 12 en pocos píxeles. Además la salida tenía los acentos rotos.', 'Ese umbral lo había puesto sin medir. La comprobación ahora mide lo que importa, la escala y el giro de la cabeza, con el mismo método que los videos, y la diferencia de color se informa. Los acentos se corrigieron con PYTHONIOENCODING=utf-8.'],
    ['La salida de la suite del backend quedó vacía en su .txt (intentos/03), aunque la foto mostraba 898 pruebas pasadas.', 'El comando guardaba solo la salida del último paso (cd ..). Lo agrupé en un bloque y lo repetí.'],
  ]),

  h1('9. Limitaciones y pendientes'),
  vineta('La boca sigue el texto, no el sonido real: es una aproximación por sílabas, no un análisis de fonemas del audio. Con un servicio que entregue los visemas de la voz (por ejemplo Azure AI Speech) se podría afinar.'),
  vineta('Son cuatro formas de boca y el interior es una sombra con algo de lengua y dientes, no dientes reales. Si se quiere más realismo, se puede grabar un clip dedicado a las bocas y pasarlo por LivePortrait.'),
  vineta('El laboratorio, radiología y el especialista siguen hablando en la escena del doctor, como en la TA-020.'),
  vineta('En el video, la boca empieza a moverse unos 120 ms después del primer sonido; parte se explica porque la primera sílaba empieza con M, pero conviene revisarlo con más frases.'),
  vineta('No lo probé en Safari real (Mac o iPhone).'),
  vineta('Live-Avatar queda como trabajo futuro, si el proyecto llega a tener acceso a GPU.'),

  h1('10. Trazabilidad y conclusión'),
  leyenda('Tabla 7. De cada corrección a su código y su prueba'),
  tabla([2800, 3838, 3000], ['Corrección', 'Código', 'Prueba'], [
    ['La cabeza no cambia de tamaño', 'Capas *-cabeza.webp; loadFace en simulacion.js; generar-bocas.py', 'medir_antes_y_despues.py; «las capas ocupan exactamente el rectángulo de la imagen»'],
    ['Boca por sílaba', 'labios.js (syllables, plan); followVoice y setMouth en simulacion.js', 'labios.test.mjs; probar_labios.cjs (ritmo, formas, silencio)'],
    ['Balanceo leve (0,4)', 'SWAY_INTENSITY, swayTick y setTalking en simulacion.js', 'probar_labios.cjs (balanceo, giro máximo, fin del turno)'],
    ['Reducir movimiento', 'setTalking y reducedMotion en simulacion.js', '04_chrome_reducir_movimiento'],
    ['Sin capas', 'Las capas son opcionales sobre la imagen quieta', '06_chrome_capas_bloqueadas'],
    ['Nada más cambia', 'Commit e50a4d5 (solo frontend)', 'Regresión de la TA-020 y suite del backend'],
  ]),
  h2('10.1 Conclusión'),
  p(`Con esta corrección los avatares ya no «saltan» de tamaño al hablar, porque la cara es siempre la misma imagen quieta y solo cambian la boca y una inclinación suave de la cabeza. La boca ahora acompaña las sílabas de lo que se dice, con cuatro formas y a un ritmo de ${ritmo} cambios por segundo, y se cierra en las pausas. Lo probé en Chrome, Edge y Firefox, en escritorio y en celular, con «reducir movimiento» y sin las capas, y la consulta sigue funcionando en todos los casos. Además, la página carga ${kbCapas} KB de imágenes en lugar de 1,1 MB de video.`),

  new Paragraph({ children: [new PageBreak()] }),
  h1('Anexo. Fotos de la terminal'),
  p('Cada prueba se ejecutó en una ventana de PowerShell titulada con el commit evaluado; la salida completa está en el .txt del mismo nombre en la carpeta ejecucion.'),
  ...figura(e('00_medicion_antes_y_despues'), 'Medición antes y después.', 600, 400),
  ...figura(e('01_chrome'), 'Prueba en Google Chrome.', 600, 420),
  ...figura(e('02_edge'), 'Prueba en Microsoft Edge.', 600, 420),
  ...figura(e('03_firefox'), 'Prueba en Firefox.', 600, 420),
  ...figura(e('04_chrome_reducir_movimiento'), 'Chrome con «reducir movimiento».', 600, 420),
  ...figura(e('05_chrome_celular'), 'Chrome con la pantalla de un celular.', 600, 420),
  ...figura(e('06_chrome_capas_bloqueadas'), 'Chrome con las capas de boca y cabeza bloqueadas.', 600, 420),
  ...figura(e('07_pruebas_unitarias_silabas'), 'Pruebas unitarias de la lógica de sílabas.', 600, 420),
  ...figura(e('08_regresion_ta020'), 'Regresión de la prueba de la TA-020.', 600, 420),
  ...figura(e('09_suite_backend'), 'Suite completa del backend.', 600, 420),
];

const doc = new Document({
  creator: 'James Bryam Gutiérrez Rubio',
  title: 'TA-020 (correctivo): Boca por sílaba y balanceo de la cabeza',
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
      children: [t('Consulta Médica Virtual · Informe correctivo TA-020 · Página ', { size: 17, color: GRIS }), new TextRun({ children: [PageNumber.CURRENT], size: 17, color: GRIS })] })] }) },
    children: [...portada, ...cuerpo],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(salida, buffer);
  console.log(`Informe en ${salida}`);
});
