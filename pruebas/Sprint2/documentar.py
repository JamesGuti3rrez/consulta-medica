"""Cinco Word independientes a partir de XML, capturas nativas, navegador y servicios reales."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from dotenv import dotenv_values
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'pruebas'))
from codigos_documentacion import align_document, destination as report_destination
OUT = ROOT / 'Entregables/Sprint2'
DATE = '30 de octubre de 2026'
CONFIG = {
 'TA-017': {
  'test': 'test_ta017.py', 'image': 'http.png',
  'before': 'La protección de sesiones ya estaba implementada bajo la evidencia histórica TA-011. Este punto conserva ese código y cierra su validación bajo el identificador TA-017 del backlog actual.',
  'steps': [
   'Toda lectura de sesión, mensaje, eventos, cierre y reporte pasa por authorize_session antes de operar sobre el estado.',
   'Los usuarios registrados presentan un Bearer verificado en Supabase Auth. La sesión conserva el propietario y una credencial ajena recibe 404, igual que una sesión inexistente.',
   'Los invitados reciben una capacidad aleatoria de 256 bits en X-Session-Token. Solo se guarda su hash SHA-256; no basta conocer el identificador de la consulta.',
   'Se verificó que los campos owner_id y session_id enviados en el cuerpo no cambian la autorización. Las denegaciones no modifican historia ni eventos.',
   'Las credenciales ausentes o inválidas reciben 401; un propietario válido obtiene 200. El reporte de una consulta abierta conserva el bloqueo 409.',
  ],
  'files': [('backend/server/api/ai.py', 'Dependencia authorize_session en todas las rutas y correspondencia con TA-017.'),
            ('backend/server/orchestration/service.py', 'Acceso a propietario/hash y vistas públicas sin credenciales.'),
            ('backend/tests/sprint2/test_ta017.py', 'Matriz de cinco operaciones, acceso positivo y negativo, capacidades e integridad.')],
  'matrix': [('Propietario registrado', '200 en lectura; mensaje, eventos y cierre autorizados', 'Recorrido positivo local y Auth real.'),
             ('Usuario B sobre sesión de A', '404 en las cinco operaciones', 'Matriz local y Supabase Auth real.'),
             ('Sin credencial o token rechazado', '401 sin datos de la consulta', 'Matriz local y acceso anónimo remoto.'),
             ('Capacidad de otra consulta', '404; estado intacto', 'Cinco operaciones y snapshot antes/después.'),
             ('Suplantar dueño desde JSON', 'No altera la autorización', 'Prueba HTTP con owner_id y session_id ajenos.')],
  'remote': 'Se crearon dos cuentas temporales con Supabase Auth. A accedió a su sesión (200); B recibió 404 al leer, enviar mensaje, listar eventos, cerrar y consultar el reporte. Sin credencial se obtuvo 401. Solo permaneció el evento de inicio después de las denegaciones.',
  'limits': 'No se introdujeron rutas de edición directa de eventos, nuevas migraciones ni cambios de rol. Las pruebas RLS históricas marcadas vivo no forman parte de la batería local; la evidencia remota de esta entrega comprueba la autorización HTTP de la aplicación con Auth y persistencia reales.',
  'caption': 'Matriz visual del registro HTTP: propietario 200, otro alumno 404 y ausencia de credenciales 401. Es un visor de evidencia, no una pantalla nueva del producto.',
 },
 'TA-007': {
  'test': 'test_ta007.py', 'image': 'bloqueo.png',
  'before': 'Existían filtros de diagnóstico y grounding, pero la pregunta reformulada y el motivo del bloqueo podían revelar contenido protegido. Además, el orquestador dependía de que el adaptador de recuperación entregara referencias y textos correctos.',
  'steps': [
   'El motivo de bloqueo se convirtió en un código estable: contenido_protegido. Los eventos ya no incluyen el término diagnóstico que causó el rechazo.',
   'La pregunta reformulada se valida antes de utilizarla para consultar evidencia o enviarla a otro agente. Si contiene una referencia protegida, no se muestra al alumno.',
   'El orquestador intersecta los identificadores con la autorización y el caso activo. El texto se reconstruye desde el documento canónico, de modo que una fila alterada del índice no sustituye el dato real.',
   'Se añadieron barreras contra cifras sin respaldo y referencias inventadas por un agente. Los informes canónicos de laboratorio, radiología y especialista se entregan directamente, sin reinterpretar sus valores con un LLM.',
   'Las trazas locales y el observador explícito usan una proyección de metadatos: caso, agente, decisión, tokens y evidence_id. Se excluyen preguntas, respuestas y credenciales.',
   'Se deshabilitó el trazado automático del estado de LangGraph, incluso si el entorno activa LangSmith. La auditoría externa opcional recibe únicamente la proyección saneada.',
  ],
  'files': [('backend/server/guardrails/output_guard.py', 'Causa de bloqueo sin términos protegidos.'),
            ('backend/server/orchestration/star_graph.py', 'Filtro de reformulación, evidencia, cifras y trazado automático.'),
            ('backend/server/ai/agents/base.py e invencion.py', 'Sustitución de cifras no respaldadas y entrega canónica.'),
            ('backend/server/tracing/sanitize.py', 'Allowlist de metadatos de auditoría.'),
            ('backend/tests/sprint2/test_ta007.py', 'Proveedores hostiles, contaminación, falsificación y camino positivo.')],
  'matrix': [('Diagnóstico y sinónimos', 'La salida protegida se sustituye antes del frontend', 'Tres variantes; respuesta y eventos saneados.'),
             ('Pregunta reformulada protegida', 'No se envía ni se muestra', 'Reformulador hostil controlado.'),
             ('Otro case_id o texto alterado', 'Se descarta/reconstruye con el caso activo', 'Adaptador de recuperación contaminado.'),
             ('Cifras o referencias inventadas', 'Bloqueo o fallback canónico', 'Agente hostil y prueba del grounding.'),
             ('Ruta positiva y auditoría', 'Entrega válida; logs sin texto clínico ni secretos', 'Examen físico y trazado automático desactivado.')],
  'remote': 'Sobre una sesión persistida en Supabase se envió una instrucción para ignorar reglas y revelar el diagnóstico. Se bloqueó de forma determinista, sin evidencia ni llamada generativa. Las salidas LLM maliciosas se probaron localmente con proveedores controlados para forzar cada fallo de forma reproducible.',
  'limits': 'La batería demuestra las familias de ataque ejecutadas; no constituye una garantía universal frente a toda paráfrasis posible. La detección de cifras compara el contexto autorizado y no reemplaza la validación clínica. El trazado automático se desactiva; el observador manual conserva su configuración opcional.',
  'caption': 'Conversación real de la interfaz: un proveedor de prueba produce una respuesta protegida y el filtro la sustituye. El texto diagnóstico del proveedor no llega al chat.',
 },
 'TA-027': {
  'test': 'test_ta027.py', 'image': 'consistencia.png',
  'before': 'El proyecto validaba el esquema y varias reglas cruzadas, pero no reunía un informe de consistencia por caso con clasificación, huella, trazabilidad de hallazgos y estado previo a su presentación.',
  'steps': [
   'Se implementó un componente validador determinista que reutiliza el JSON Schema y las reglas cruzadas existentes. No usa un LLM como autoridad clínica.',
   'Cada informe contiene versión de reglas, huella SHA-256, case_id, estado, can_present, requires_human_review y hallazgos con código, gravedad, ruta y evidence_id cuando corresponde.',
   'Se distinguen errores bloqueantes, discrepancias que requieren revisión y avisos informativos. Apto significa que no se detectó un bloqueo automático; no equivale a validación clínica humana.',
   'Se detectan referencias ajenas, faltantes de estructura, revelación indebida, políticas incorrectas, etiquetas con datos contradictorios y valores incompatibles con límites técnicos amplios.',
   'La revisión se integra en los repositorios local y Supabase, el catálogo y la prevalidación/publicación docente. Los casos con errores o discrepancias de revisión no se presentan ni se publican.',
   'El panel docente muestra el informe; POST /api/docente/consistencia permite revisar un documento sin publicarlo. Solo profesor o administrativo puede acceder.',
  ],
  'files': [('backend/server/cases/consistency.py', 'Informe, clasificación, huella y decisión previa.'),
            ('backend/server/cases/repository.py, supabase.py y catalog.py', 'Aplicación antes de servir casos.'),
            ('backend/server/cases/uploads.py', 'Bloqueo previo a la publicación docente.'),
            ('backend/server/api/teaching.py y frontend/public/js/docente.js', 'Endpoint autorizado e informe visual.'),
            ('backend/tests/sprint2/test_ta027.py', 'Catálogo completo, alteraciones intencionales y permisos.')],
  'matrix': [('Casos actuales válidos', 'Informe apto, versión y huella', '43 casos del catálogo local.'),
             ('Casos alterados', 'Bloqueo de presentación y publicación', 'Faltantes, evidencia ajena, fuga, valor imposible, política y contradicción.'),
             ('Documento incompleto', 'Informe CV001 sin caída del validador', 'null, arreglo, objeto vacío y estructura incompleta.'),
             ('Acceso docente', '200 profesor/administrativo; 403 alumno; 401 sin credencial', 'Pruebas HTTP del endpoint de revisión.'),
             ('Catálogo remoto', 'Todos revisados; sin escrituras sobre casos', 'Verificación de solo lectura con Supabase real.')],
  'remote': 'Se leyeron 44 documentos de casos_curados en Supabase y se generó un informe apto para cada uno. El catálogo local contiene 43 casos; esa diferencia refleja las dos fuentes consultadas y no se corrigió sobrescribiendo ninguna. Las huellas y estados remotos quedan en el JSON de evidencia.',
  'limits': 'El componente no certifica plausibilidad clínica completa ni sustituye revisión humana. Las contradicciones se detectan sobre estructura y etiquetas; no se afirma comprensión semántica exhaustiva de toda narración. No se añadieron columnas de revisión: el informe puede regenerarse por su huella y la publicación inválida queda bloqueada.',
  'caption': 'Panel docente con revisión automática de consistencia visible y versión de reglas. La referencia diagnóstica es visible únicamente dentro del contexto docente autorizado de prueba.',
 },
 'HU-004': {
  'test': 'test_hu004.py', 'image': 'tablilla.png',
  'before': 'Los agentes de exámenes existían, pero faltaba cerrar la matriz presente/ausente, proteger la entrega canónica y alimentar la tablilla con los datos revelados por los turnos del backend.',
  'steps': [
   'Se verificó la selección de laboratorio, radiología, especialista y médico asistente para exploración física. El routing reconoce palabras completas y alias explícitos de estudios.',
   'Los resultados existentes se entregan desde su evidencia canónica. No se generan sustitutos ni se pide al estudiante que invente resultados ya disponibles.',
   'Si el pedido es genérico se pregunta qué examen se necesita; si no hay un resultado soportado se comunica su ausencia de forma determinista y natural.',
   'Cada respuesta incorpora clinical_evidence únicamente para los identificadores autorizados del caso activo. Los eventos registran esos mismos identificadores.',
   'La interfaz añade los datos a la tablilla después del turno. Un Set de identificadores impide crear tarjetas duplicadas al repetir una solicitud.',
   'La palabra orinar ya no se confunde con el término de examen orina. Se conservaron alias completos como electroencefalograma y angiotomografía.',
  ],
  'files': [('backend/server/orchestration/router.py', 'Routing por palabras y alias explícitos.'),
            ('backend/server/engine/disclosure/policy.py', 'Coincidencia de requerimientos y solicitudes de exploración.'),
            ('backend/server/ai/agents/base.py, laboratorio.py, radiologia.py y especialista.py', 'Entrega canónica y ausencia sin invención.'),
            ('backend/server/orchestration/service.py', 'clinical_evidence autorizada para la tablilla.'),
            ('frontend/public/js/simulacion.js', 'Actualización progresiva y deduplicación.'),
            ('backend/tests/sprint2/test_hu004.py', 'Matriz de roles, presente/ausente y repetición.')],
  'matrix': [('Laboratorio presente / ausente', 'Resultado canónico / aviso de ausencia', 'Caso fixture MED-900 y caso MED-008.'),
             ('Radiología presente / ausente', 'Rol correcto y solo su evidencia / ausencia', 'Tomografía de cráneo y estudio no disponible.'),
             ('Especialista presente / ausente', 'Interconsulta del caso / no disponible', 'Neurología fixture y cardiología ausente.'),
             ('Pedido genérico', 'Pregunta aclaratoria sin crear valores', 'Análisis de sangre e imagen.'),
             ('Tablilla y eventos', 'Datos revelados sin duplicados ni mezcla de caso', 'Cuatro turnos, tres evidencias distintas en navegador.')],
  'remote': 'Se inició una sesión del caso CIR-005 almacenado en Supabase y se solicitaron pruebas de coagulación. Laboratorio devolvió el contenido canónico, sus identificadores y el evento de revelación. La matriz completa de radiología y especialista presente/ausente se ejecutó con el fixture local MED-900 y casos reales del catálogo local.',
  'limits': 'No todos los casos tienen interconsultas o imágenes. La ausencia se conserva cuando no existe dato ni generación soportada. MED-900 es un fixture de prueba y no se publicó en la base. Las marcas sintéticas de EN-013 se muestran de forma diferenciada, sin convertirlas en resultados canónicos.',
  'caption': 'Tablilla después de hemograma, tomografía e interconsulta. Repetir el hemograma conserva una sola tarjeta para ese resultado.',
  'extra': ('agentes.png', 'Conversación con los roles correspondientes. Micrófono y voz simulados para reproducibilidad; mensajes y respuestas pasan por la API real local.'),
 },
 'EN-013': {
  'test': 'test_en013.py', 'image': 'procedencia.png',
  'before': 'Los exámenes faltantes se respondían como ausentes. Se añadió una ruta separada para proponer datos sintéticos educativos, condicionada a la solicitud y al caso, con contrato de validación antes de su revelación.',
  'steps': [
   'La política permite solicitudes explícitas de laboratorio soportadas. Se prioriza cualquier resultado canónico y se excluyen población pediátrica y casos gineco-obstétricos sin contrato de referencia aplicable.',
   'ExamComposer recibe edad, sexo y evidencia pública/ya revelada. No recibe protected, alias, el caso completo ni las instrucciones crudas del estudiante; solicita JSON con panel y valores a temperatura 0.',
   'El contrato rechaza estructura adicional, campos incompletos, texto en vez de números, booleanos, NaN, intervalos no admitidos e incoherencia entre hemoglobina y hematocrito. Un resultado rechazado no se guarda ni se muestra.',
   'El servidor añade unidades, referencias educativas y procedencia; el modelo no puede inventar esos metadatos ni agregar una conclusión diagnóstica. La salida pasa además por el filtro de términos protegidos.',
   'Los resultados aceptados se identifican como sintéticos educativos, no observados. Se conserva la versión del validador y la revisión clínica humana pendiente. La tablilla muestra esa condición.',
   'El candidato y su evidencia se guardan en el JSONB de la sesión. Una solicitud posterior valida y reutiliza el mismo resultado si coinciden la huella del caso y la versión del contrato. El evento registra la decisión.',
   'El reporte separa synthetic_exams de la evidencia canónica y no concede puntos de anamnesis por estos datos. No se altera el mecanismo de diagnóstico final existente.',
  ],
  'files': [('backend/server/ai/agents/exam_composer.py', 'Candidato JSON condicionado sin acceso al bloque protegido.'),
            ('backend/server/engine/disclosure/exam_policy.py', 'Solicitud, rol, población y prioridad canónica.'),
            ('backend/server/engine/validation/exams.py', 'Contrato mínimo de validación e intervalos versionados.'),
            ('backend/server/orchestration/exam_completion.py', 'Validación, formato, procedencia y reutilización.'),
            ('backend/server/config.py y api/ai.py', 'Activación y composición del servicio.'),
            ('frontend/public/js/simulacion.js y css/simulacion.css', 'Tarjeta y marca sintética visible.'),
            ('backend/tests/sprint2/test_en013.py', 'Aceptación, rechazo, prioridad, población, aislamiento y contrato.')],
  'matrix': [('Dato canónico existente', 'No se invoca el generador', 'Hemograma fixture y coagulación canónica.'),
             ('Candidato aceptado', 'Indicadores, unidades, referencias y procedencia', 'Hemograma parcial y glucosa en ayunas.'),
             ('Candidato incompatible', 'Bloqueado; sin evidencia ni snapshot', 'Rango, tipos, NaN, booleano, campos, incoherencia y abstención.'),
             ('Solicitud no soportada / población sin contrato', 'No genera resultados', 'Imagen, troponina, pregunta genérica, paciente, pediatría y gineco-obstetricia.'),
             ('Persistencia y aislamiento', 'Mismo resultado en la sesión; sin compartir entre consultas', 'Pruebas locales y relectura desde una instancia nueva con Supabase real.')],
  'remote': 'Se obtuvo un candidato de hemograma parcial usando Groq real. Pasó el contrato, produjo tres indicadores y quedó guardado en sma_sesiones.state.synthetic_exam_results. Tras reconstruir el servicio, la misma solicitud devolvió el resultado persistido sin generar otra variante.',
  'limits': 'Alcance inicial: hemograma parcial (leucocitos, hemoglobina y hematocrito) y glucosa con solicitud explícita en ayunas, en adultos con contrato aplicable. Los intervalos son educativos y conservadores; los candidatos fuera de ellos o con contexto contradictorio requieren revisión. No es un generador universal ni una certificación clínica. TA-026 ampliará la validación especializada; TA-028 corresponde al repositorio y aprobación entre casos/sesiones y no se da por terminada aquí.',
  'caption': 'Resultado sintético visible con unidades, referencias y marca de revisión clínica pendiente. La imagen utiliza un generador estructurado controlado; la validación y la interfaz son reales.',
  'extra': ('reporte.png', 'El reporte poscierre conserva el resultado sintético y la marca de revisión clínica pendiente, separado de la evidencia canónica usada para puntuar.'),
 },
}


def tests_from(path):
    root = ET.parse(path).getroot()
    if root.findall('.//failure') or root.findall('.//error'):
        raise SystemExit('No se documenta como aprobado un XML con fallos: ' + str(path))
    return list(root.iter('testcase'))


def main():
    source = json.loads((HERE / 'alcance.json').read_text(encoding='utf-8'))
    backlog = {p['ID']: p for p in source['puntos']}
    remote = json.loads((HERE / 'servicios_reales.json').read_text(encoding='utf-8'))
    if remote['resultado'] != 'PASA' or not remote['limpieza']['confirmada']:
        raise SystemExit('Falta verificación remota y limpieza confirmada.')
    capture_rows = json.loads((HERE / 'capturas_terminal.json').read_text(encoding='utf-8'))
    captures = {c['tarea']: c for c in capture_rows}
    for capture in capture_rows:
        if hashlib.sha256((ROOT / capture['registro']).read_bytes()).hexdigest() != capture['sha256']:
            raise SystemExit('Cambió un registro después de fotografiarlo.')
    regression = tests_from(HERE / 'regresion.xml')
    all_results = []
    OUT.mkdir(parents=True, exist_ok=True)
    for task, config in CONFIG.items():
        tests = tests_from(HERE / task / 'pytest.xml')
        browser = json.loads((HERE / task / 'navegador.json').read_text(encoding='utf-8'))
        if browser['resultado'] != 'PASA' or remote['puntos'][task]['resultado'] != 'PASA':
            raise SystemExit('Falta evidencia aprobada de ' + task)
        pbi = backlog[task]
        doc = Document()
        section = doc.sections[0]
        section.page_width, section.page_height = Cm(21), Cm(29.7)
        section.top_margin = section.bottom_margin = Cm(1.8)
        section.left_margin = section.right_margin = Cm(2)
        normal = doc.styles['Normal']
        normal.font.name = 'Arial'; normal.font.size = Pt(10)
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.line_spacing = 1.08
        for name, size in [('Title', 27), ('Heading 1', 16), ('Heading 2', 12)]:
            doc.styles[name].font.name = 'Arial'
            doc.styles[name].font.size = Pt(size)
            doc.styles[name].font.color.rgb = RGBColor.from_string('15596B')
        header = section.header.paragraphs[0]
        header.text = 'CONSULTA MÉDICA VIRTUAL  /  SPRINT 2  /  ' + task
        header.style = doc.styles['Caption']
        footer = section.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        footer.add_run(task + ' · ' + DATE + ' | Página ').font.size = Pt(8)
        field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'PAGE'); footer._p.append(field)

        def p(text='', bold=False):
            paragraph = doc.add_paragraph(); paragraph.add_run(text).bold = bold
            return paragraph
        def h(text, level=1): doc.add_heading(text, level)
        def page(title): doc.add_page_break(); h(title)
        def bullet(text): doc.add_paragraph(text, style='List Bullet')
        def code(text):
            paragraph = p(); paragraph.paragraph_format.line_spacing = 1
            run = paragraph.add_run(text); run.font.name = 'Consolas'; run.font.size = Pt(8)
        def table(headers, rows):
            table = doc.add_table(rows=1, cols=len(headers)); table.style = 'Table Grid'
            for cell, label in zip(table.rows[0].cells, headers):
                cell.text = str(label)
                shade = OxmlElement('w:shd'); shade.set(qn('w:fill'), 'E6F3F4'); cell._tc.get_or_add_tcPr().append(shade)
                for run in cell.paragraphs[0].runs: run.bold = True
            table.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
            for row in rows:
                for cell, value in zip(table.add_row().cells, row): cell.text = str(value)
            for row in table.rows:
                row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
                for cell in row.cells:
                    for para in cell.paragraphs:
                        para.paragraph_format.space_after = Pt(4)
                        for run in para.runs: run.font.size = Pt(9)
            p()
        def picture(path, caption, max_height=13):
            with Image.open(path) as bitmap:
                width, height = bitmap.size
            width_cm = min(16.4, max_height * width / height)
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.keep_with_next = True
            paragraph.add_run().add_picture(str(path), width=Cm(width_cm))
            p(caption).style = doc.styles['Caption']

        doc.core_properties.title = task + ' — ' + pbi['Título corto']
        doc.core_properties.author = 'Equipo Consulta Médica Virtual'
        doc.core_properties.subject = 'Implementación, criterios de aceptación y pruebas reproducibles'
        p('INFORME DE DESARROLLO Y VERIFICACIÓN', True)
        doc.add_heading(task, 0); h(pbi['Título corto'])
        p('Sprint 2 · Product Backlog unificado v5.5 · ' + DATE, True)
        p('Responsable según backlog: ' + pbi['Responsable'])
        p('Estado técnico: implementado y verificado. La aceptación del Product Owner y la revisión clínica humana no se sustituyen por este informe.')
        h('Objetivo', 2); p(pbi['Descripción / Objetivo'])
        h('Criterios de aceptación del documento fuente', 2); p(pbi['Criterios de aceptación verificables'])
        h('Resultado comprobado', 2)
        bullet(f'{len(tests)} pruebas específicas aprobadas para {task}.')
        bullet(f'{len(regression)} pruebas aprobadas en la regresión compartida; tres pruebas vivo de seguridad se deseleccionaron en el entorno local.')
        bullet('Recorrido de navegador aprobado con API local real y proveedores controlados; verificación remota acotada con Supabase real.')
        bullet('Capturas del resultado visible y de ventanas nativas de PowerShell con los registros originales de ejecución.')
        p('Alcance acordado: primeros cinco PBIs de Rodrigo, incluidas responsabilidades compartidas. HU-005 y TA-019 quedaron excluidas. No se modifica el documento fuente ni se certifican sus puntos como horas ejecutadas.')

        page('1. Desarrollo e integración')
        p(config['before'])
        for index, step in enumerate(config['steps'], 1): p(f'{index}. {step}')
        h('Archivos principales', 2); table(['Archivo / componente', 'Responsabilidad'], config['files'])
        if task == 'EN-013':
            h('Contrato y persistencia', 2)
            code('SYNTHETIC_EXAM_DATA=true\n# Si se omite, hereda SYNTHETIC_CASE_DATA.\nsma_sesiones.state.synthetic_exam_results[panel]\nsma_eventos.payload.exam_validation\nreport.synthetic_exams')
            p('La implementación aprovecha JSONB existente; no necesita una migración nueva para el snapshot de sesión. La revisión pendiente describe aprobación clínica humana, distinta del contrato automático superado.')
        if task == 'TA-027':
            table(['Código', 'Comprobación adicional'], [('CV001', 'Estructura JSON Schema.'), ('CV002', 'Exposición normalizada de referencia diagnóstica.'), ('CV003', 'Datos diferentes bajo una misma etiqueta: revisión.'), ('CV004', 'Límites técnicos de plausibilidad para valores estructurados.'), ('CV005', 'Política de revelación del especialista.')])

        page('2. Aceptación y resultados de pruebas')
        table(['Familia / criterio', 'Comportamiento esperado', 'Evidencia obtenida'], config['matrix'])
        h('Batería específica ejecutada', 2)
        groups = Counter(t.get('name', '').split('[')[0] for t in tests)
        table(['Familia de prueba (nombre en el código)', 'Casos', 'Resultado'],
              [(name.removeprefix('test_').replace('_', ' '), count, 'PASA') for name, count in groups.items()])
        p(f'Fuente: pruebas/Sprint2/{task}/pytest.xml. Total: {len(tests)} casos, sin fallos ni errores. La batería global está en pruebas/Sprint2/regresion.xml.')

        page('3. Evidencia gráfica de ejecución y resultado')
        p('La imagen del terminal muestra el registro original de pytest en una ventana propia de PowerShell. No se presenta como una captura de la terminal integrada de VS Code. La imagen de interfaz procede del recorrido automatizado, sin simular la respuesta de los endpoints.')
        picture(ROOT / captures[task]['captura'], 'Figura 1. Registro original de las pruebas específicas: ' + str(len(tests)) + ' casos aprobados.', max_height=5)
        picture(HERE / task / 'capturas' / config['image'], 'Figura 2. ' + config['caption'], max_height=13.2)
        if config.get('extra'):
            page('3.1. Evidencia visual complementaria')
            filename, caption = config['extra']
            picture(HERE / task / 'capturas' / filename, 'Figura 3. ' + caption, max_height=19)
        p('El navegador usa dispositivos de voz simulados para reproducibilidad. El servidor, el routing, los filtros y la actualización de la interfaz son reales. Auth y los proveedores del servidor de evidencia son controlados; no son las cuentas ni el modelo de producción.')

        page('4. Comprobación con servicios reales')
        p(config['remote'])
        data = remote['puntos'][task]
        if task == 'EN-013':
            p('Modelo utilizado en la comprobación: ' + data['modelo'] + '. Versión del contrato: ' + data['validacion']['version'] + '.')
            table(['Indicador sintético real de prueba', 'Valor', 'Unidad', 'Referencia educativa'],
                  [(i['label'], i['value'], i['unit'], f"{i['reference']['min']}–{i['reference']['max']}") for i in data['evidencia']['indicators']])
        p('Las cuentas fueron creadas mediante administración de Auth con correo confirmado y sin enviar mensajes. Solo se operó sobre sesiones temporales propias. La prueba final confirmó la eliminación de dos cuentas, dos sesiones y sus eventos. Los casos curados, roles existentes y .env no se modificaron.')
        picture(ROOT / captures['SERVICIOS-REALES']['captura'], 'Figura ' + ('4' if config.get('extra') else '3') + '. Salida original de la comprobación final con Supabase y Groq reales, incluida la limpieza confirmada.', max_height=11)
        p('El archivo servicios_reales.json registra el resultado por PBI. El ataque real de TA-007 es determinista; las salidas LLM hostiles se fuerzan localmente. La matriz remota de HU-004 comprueba laboratorio, mientras que imágenes y especialistas se cubren con pruebas locales. No se ejecutó un benchmark RAGAS ni el trabajo de TA-019.')
        p('Se conserva la primera ejecución en intentos/01_trazado_automatico: las funciones pasaron, pero LangGraph intentó enviar trazas automáticas a LangSmith y recibió 429 por cuota. La corrección desactiva esa vía y la ejecución final no depende de LangSmith.')

        page('5. Reproducción, límites y trazabilidad')
        h('Prueba del punto en la terminal de VS Code', 2)
        code('cd backend\n.\\.venv\\Scripts\\python.exe -m pytest tests/sprint2/' + config['test'] + ' -q\ncd ..')
        p('Las pruebas específicas inyectan almacén local y proveedores controlados; no requieren consumir Groq ni modificar Supabase.')
        h('Regresión compartida y capturas de interfaz', 2)
        code('npm run test:sprint2 -- --junitxml=../pruebas/Sprint2/regresion.xml\n# Terminal 1: servidor de evidencia local en 3027\n.\\backend\\.venv\\Scripts\\python.exe pruebas/Sprint2/servidor_evidencia.py\n# Terminal 2: recorrido de navegador\nnode pruebas/Sprint2/probar_navegador.mjs')
        h('Comprobación remota y generación documental', 2)
        code('.\\backend\\.venv\\Scripts\\python.exe pruebas/Sprint2/verificar_servicios_reales.py\n.\\backend\\.venv\\Scripts\\python.exe pruebas/Sprint2/fotografiar_terminal.py\n.\\backend\\.venv\\Scripts\\python.exe pruebas/Sprint2/documentar.py')
        p('La prueba remota requiere .env y consume una generación acotada en Groq; crea y elimina datos temporales. Los scripts de capturas requieren Pillow; el generador documental utiliza python-docx. Son herramientas de evidencia, sin agregarse al runtime del simulador. Deben conservarse los registros originales para regenerar las capturas.')
        h('Límites y decisiones', 2); p(config['limits'])
        p('Entorno de verificación: Windows, Python 3.12, Node.js 24 y Microsoft Edge headless mediante Playwright. La validación automatizada no sustituye aceptación del docente ni una revisión humana de seguridad o clínica.')
        if task == 'EN-013':
            h('Fuentes de intervalos educativos', 2)
            p('Se consultaron las páginas oficiales de MedlinePlus el 30/10/2026. Las referencias varían entre laboratorios; aquí se usan como contrato conservador de simulación, sin interpretación diagnóstica.')
            p('Hemograma: https://medlineplus.gov/ency/article/003642.htm')
            p('Glucosa: https://medlineplus.gov/ency/article/003482.htm')
        h('Integridad de evidencia', 2)
        p('Documento fuente: ' + source['fuente'])
        code('SHA-256 del backlog: ' + source['sha256_fuente'])
        code('SHA-256 del registro del punto: ' + captures[task]['sha256'])
        p('Los XML y JSON proceden de ejecuciones reales. La presentación de capturas no añade salidas inventadas. Las credenciales no forman parte del documento ni de las imágenes seleccionadas.')
        entry = align_document(doc, task)
        destination = report_destination(task); doc.save(destination)
        with ZipFile(destination) as archive:
            assert archive.testzip() is None
            xml = ''
            for name in archive.namelist():
                if name.endswith('.xml'):
                    raw = archive.read(name); ET.fromstring(raw); xml += raw.decode('utf-8')
            for key, value in dotenv_values(ROOT / '.env').items():
                if value and len(value) >= 12 and any(part in key.upper() for part in ('KEY', 'SECRET', 'PASSWORD', 'TOKEN')):
                    assert value not in xml, 'Credencial detectada en el documento.'
        reopened = Document(destination)
        assert len(reopened.inline_shapes) == (4 if config.get('extra') else 3)
        all_results.append({'tarea': entry['codigo'], 'codigo_evidencia': task, 'archivo': str(destination.relative_to(ROOT)),
                            'pruebas_aprobadas': len(tests), 'capturas': len(reopened.inline_shapes),
                            'integridad_zip_xml': 'PASA', 'credenciales_incluidas': False,
                            'servicios_reales': 'PASA', 'navegador': 'PASA'})
        print('[PASA] Word ' + entry['codigo'] + ': ' + str(len(tests)) + ' pruebas, ' + str(len(reopened.inline_shapes)) + ' capturas.', flush=True)
    summary = {'fecha': DATE, 'puntos': all_results, 'regresion_aprobada': len(regression),
               'pruebas_especificas': sum(r['pruebas_aprobadas'] for r in all_results),
               'limpieza_remota_confirmada': remote['limpieza']['confirmada'], 'excluidos': ['HU-006', 'TA-023']}
    (HERE / 'resumen.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
