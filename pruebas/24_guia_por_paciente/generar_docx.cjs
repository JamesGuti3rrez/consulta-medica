// Convierte resultados/guia.json (de generar_guia.py) en el documento Word «Guiones de prueba por paciente».
// Formato de los entregables: A4, márgenes de 2 cm, Arial 10,5 pt, títulos en negro, encabezados de tabla en gris.
// Requiere el paquete docx: npm install --no-save docx@9.5.1
// Uso, desde la raíz:
//   node pruebas/24_guia_por_paciente/generar_docx.cjs <salida.docx>
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, Footer, PageNumber, LevelFormat, BorderStyle, PageBreak,
} = require('docx');

const guia = JSON.parse(fs.readFileSync(path.join(__dirname, 'resultados', 'guia.json'), 'utf8'));
const salida = process.argv[2] || 'Guiones de prueba por paciente.docx';
const FECHA = new Date(`${guia.fecha}T12:00:00`).toLocaleDateString('es-PE', { day: 'numeric', month: 'long', year: 'numeric' });
const ANCHO = 9638; // A4 (11906) menos márgenes de 1134 a cada lado

const p = (children, options = {}) => new Paragraph({ spacing: { after: 100 }, ...options, children });
const t = (text, options = {}) => new TextRun({ text, ...options });
const campo = (etiqueta, valor) => p([t(`${etiqueta}: `, { bold: true }), t(valor)]);
const vineta = (children) => new Paragraph({ numbering: { reference: 'vinetas', level: 0 }, spacing: { after: 60 }, children });
const lista = (nombres) => (nombres.length ? nombres.join('; ') : 'ninguna');

const celda = (text, ancho, cabecera = false) => new TableCell({
  width: { size: ancho, type: WidthType.DXA },
  shading: cabecera ? { type: ShadingType.CLEAR, color: 'auto', fill: 'F2F2F2' } : undefined,
  margins: { top: 60, bottom: 60, left: 100, right: 100 },
  children: [new Paragraph({ children: [t(text, { bold: cabecera, size: 19 })] })],
});
const tabla = (anchos, cabecera, filas) => new Table({
  width: { size: ANCHO, type: WidthType.DXA },
  columnWidths: anchos,
  rows: [
    new TableRow({ tableHeader: true, children: cabecera.map((texto, i) => celda(texto, anchos[i], true)) }),
    ...filas.map(fila => new TableRow({ children: fila.map((texto, i) => celda(texto, anchos[i])) })),
  ],
});

const estadoTexto = (queda) => {
  const partes = [`Posibles: ${lista(queda.posibles)}.`];
  if (queda['menos probables'].length) partes.push(`Menos probables: ${lista(queda['menos probables'])}.`);
  if (queda.descartadas.length) partes.push(`Descartadas: ${lista(queda.descartadas)}.`);
  return partes.join(' ');
};

const cuerpo = [];
cuerpo.push(new Paragraph({ heading: HeadingLevel.TITLE, spacing: { after: 120 }, children: [t('Guiones de prueba por paciente')] }));
cuerpo.push(p([t('Consulta Médica Virtual · Qué preguntar, por qué, y por qué se va descartando cada enfermedad', { italics: true })]));
cuerpo.push(campo('Responsable', 'James Bryam Gutiérrez Rubio'));
cuerpo.push(campo('Versión', `3.0 · ${FECHA}`));
cuerpo.push(campo('Complementa', 'Guía de pruebas del simulador (misma carpeta)'));
cuerpo.push(campo('Verificación', `Los ${guia.casos.length} guiones se recorrieron con el modelo real (Groq): ${guia.pedidos_correctos} de ${guia.pedidos} pedidos correctos. En los ${guia.casos.length} casos queda un solo diagnóstico al terminar.`));

cuerpo.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t('Cómo usar estos guiones')] }));
[
  'Abrir el caso con su enlace de prueba (está en cada guion) en Google Chrome o Microsoft Edge, y pulsar «Iniciar simulación».',
  'Cada guion empieza con las enfermedades que podrían explicar el motivo de consulta.',
  `En cada paso se indica qué decir, por qué se pregunta, quién responde, qué contestó el simulador en la verificación del ${FECHA}, qué enfermedades cambian (y por qué) y qué queda después.`,
  'Estados de cada enfermedad: «posible» mientras no aparezca ningún dato en su contra; «menos probable» con el primer dato en contra; «descartada» cuando aparecen todos los datos que la excluyen. El diagnóstico del caso nunca se descarta.',
  'Al final de cada guion, «Por qué se descarta cada una» resume el razonamiento de todas las enfermedades alternativas.',
  'Qué no preguntar: cosas que el caso no tiene o que un estudiante no debe hacer. Sirven para comprobar que el simulador no inventa, no revela el diagnóstico y responde con naturalidad.',
  'Las palabras de las respuestas pueden cambiar entre intentos, pero el contenido y las cifras deben ser los mismos.',
].forEach(texto => cuerpo.push(vineta([t(texto)])));

cuerpo.push(p([t(`Tabla 1. Los ${guia.casos.length} pacientes`, { bold: true })], { spacing: { before: 160, after: 80 } }));
cuerpo.push(tabla([600, 1200, 2800, 3438, 1600], ['#', 'Caso', 'Paciente', 'Especialidad', 'Pasos'],
  guia.casos.map((c, i) => [String(i + 1), c.case_id, c.paciente, c.especialidad, `${c.pasos.length} + ${c.no_preguntar.length}`])));
cuerpo.push(p([t('Pasos: los que hay que hacer + los que no hay que hacer. Los casos van en el orden de su número (por especialidad). EME-101, EME-102 y EME-103 forman la familia de dolor torácico: llegan con el mismo motivo y se separan según lo que se pregunte. El diagnóstico de cada caso está en el anexo final.', { size: 19 })], { spacing: { before: 80 } }));

guia.casos.forEach((c, i) => {
  cuerpo.push(new Paragraph({ children: [new PageBreak()] }));
  cuerpo.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(`${i + 1}. ${c.case_id} · ${c.paciente}`)] }));
  cuerpo.push(campo('Especialidad', c.especialidad));
  cuerpo.push(campo('Motivo de consulta', c.motivo));
  cuerpo.push(campo('Enlace de prueba', c.enlace));
  cuerpo.push(campo('Qué puede ser al empezar (solo con el motivo de consulta y la ficha)', estadoTexto(c.al_empezar)));

  cuerpo.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t('Qué preguntar, en este orden')] }));
  c.pasos.forEach(paso => {
    cuerpo.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: [t(`Paso ${paso.numero}. «${paso.pedido}»`)] }));
    if (paso.por_que) cuerpo.push(campo('Por qué se pregunta', paso.por_que));
    const responde = paso.medico_tratante
      ? `${paso.agente}. El médico tratante le pregunta «${paso.medico_tratante}». Respuesta: ${paso.respuesta}`
      : `${paso.agente}. Respuesta: ${paso.respuesta}`;
    cuerpo.push(campo('Responde', responde));
    if (paso.cambios.length) {
      cuerpo.push(p([t('Qué cambia y por qué:', { bold: true })], { spacing: { after: 40 } }));
      paso.cambios.forEach(cambio => cuerpo.push(vineta([
        t(`${cambio.enfermedad} pasa a ${cambio.pasa_a}. `, { bold: true }), t(cambio.por_que),
      ])));
    } else {
      cuerpo.push(campo('Qué cambia', 'ninguna enfermedad; el dato completa la historia o apoya lo que ya se sospechaba.'));
    }
    cuerpo.push(campo('Qué queda', estadoTexto(paso.queda)));
  });

  cuerpo.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t('Al terminar el guion')] }));
  cuerpo.push(p([t(estadoTexto(c.al_terminar))]));
  cuerpo.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t('Por qué se descarta cada una')] }));
  c.descartes.forEach(d => cuerpo.push(vineta([t(`${d.enfermedad}: `, { bold: true }), t(d.por_que)])));

  cuerpo.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t('Qué no preguntar')] }));
  cuerpo.push(tabla([2600, 3200, 3838], ['Qué decir', 'Por qué no', 'Respuesta del simulador'],
    c.no_preguntar.map(n => [n.pedido, n.motivo, n.respuesta])));
  if (c.nota) cuerpo.push(p([t('Para tener en cuenta: ', { bold: true }), t(c.nota)], { spacing: { before: 120 } }));
});

cuerpo.push(new Paragraph({ children: [new PageBreak()] }));
cuerpo.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t('Lo que todavía no hace el simulador')] }));
[
  'Al cerrar la consulta muestra la hoja de evaluación (datos clave obtenidos y omisiones), pero no califica el diagnóstico escrito ni la lista de hipótesis: las listas de este documento son la referencia para quien prueba.',
  'Ante un tratamiento contraindicado muestra una alerta de seguridad, sin nombrar el fármaco ni el motivo.',
  'Si se pide un examen sin nombrarlo («unos análisis de sangre»), el laboratorio o radiología preguntan cuál; si se nombra uno que el caso no tiene, responden que no se realizó.',
  'EME-001 y EME-002: el paciente llega con la conciencia alterada y aun así responde; tómese como la información de quienes lo acompañan.',
  'Algunos datos (por ejemplo, el dosaje de factores en CIR-005 o la tomografía en EME-002) los agregó el equipo, con fuente clínica, para que cada caso llegue a un solo diagnóstico (decisión 0002).',
].forEach(texto => cuerpo.push(vineta([t(texto)])));

cuerpo.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t('Anexo · Diagnósticos (solo para quien evalúa)')] }));
cuerpo.push(tabla([1100, 3100, 5438], ['Caso', 'Diagnóstico', 'Enfermedades que el caso permite descartar'],
  guia.casos.map(c => [c.case_id, c.diagnostico, c.descartes.map(d => d.enfermedad).join('; ')])));

const doc = new Document({
  creator: 'James Bryam Gutiérrez Rubio',
  title: 'Guiones de prueba por paciente',
  styles: {
    default: { document: { run: { font: 'Arial', size: 21 } } },
    paragraphStyles: [
      { id: 'Title', name: 'Title', basedOn: 'Normal', run: { size: 52, bold: true, color: '17365D', font: 'Arial' } },
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 30, bold: true, color: '000000', font: 'Arial' }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 25, bold: true, color: '000000', font: 'Arial' }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 22, bold: true, color: '000000', font: 'Arial' }, paragraph: { spacing: { before: 160, after: 60 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [{ reference: 'vinetas', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] }],
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      border: { top: { style: BorderStyle.SINGLE, size: 4, color: 'D9D9D9', space: 4 } },
      children: [t('Guiones de prueba por paciente · página ', { size: 17, color: '595959' }),
        new TextRun({ children: [PageNumber.CURRENT], size: 17, color: '595959' })] })] }) },
    children: cuerpo,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(salida, buffer);
  console.log(`Documento guardado: ${salida} (${guia.casos.length} casos, ${(buffer.length / 1024).toFixed(0)} KB)`);
});
