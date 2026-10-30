"""Genera el Word de TA-012 a partir de resultados verificados, sin depender de servicios externos."""
from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pruebas'))
from codigos_documentacion import align_document, destination as report_destination
HERE = Path(__file__).resolve().parent
OUTPUT = report_destination('TA-012')
DATE = "28 de octubre de 2026"
TEAL = "176B75"
DARK = "183E49"


def main():
    root = ET.parse(HERE / "pytest.xml").getroot()
    tests = list(root.iter("testcase"))
    if root.findall(".//failure") or root.findall(".//error"):
        raise SystemExit("Hay pruebas fallidas: no se emite un informe de tarea terminada.")
    specific = [test for test in tests if any(name in test.get("classname", "") for name in
                ("test_final_diagnosis", "test_ta012_diagnosis"))]
    samples = [json.loads((HERE / "resultados" / (name + ".json")).read_text(encoding="utf-8"))
               for name in ("correcto", "incorrecto", "sinonimo", "vacio", "ambiguo")]
    browser = json.loads((HERE / "navegador.json").read_text(encoding="utf-8"))
    if len(browser["casos"]) != 5 or any(row["interfaz"] != "PASA" for row in browser["casos"]):
        raise SystemExit("Falta la verificación de los cinco escenarios en el navegador.")
    if any(not row["persistido_en_sesion"] or not row["persistido_en_intentos"] for row in samples):
        raise SystemExit("La evidencia no confirma la persistencia.")
    remote = json.loads((HERE / "supabase_real.json").read_text(encoding="utf-8"))
    if remote["resultado"] != "PASA" or len(remote["casos"]) != 5:
        raise SystemExit("Falta la validación de los cinco escenarios en Supabase real.")
    for row in remote["casos"]:
        if not all(row[key] for key in ("sesion_real", "evento_real", "sin_fuga_previa",
                                       "lectura_nueva_instancia", "reintento_inmutable")):
            raise SystemExit("La comprobación remota está incompleta.")
    cleanup = remote["limpieza"]
    if not cleanup["cuenta_eliminada"] or cleanup["sesiones_eliminadas"] != 5 or not cleanup["eventos_eliminados"]:
        raise SystemExit("No se confirmó la limpieza de los datos temporales.")
    terminal = json.loads((HERE / "terminal/capturas.json").read_text(encoding="utf-8"))
    if len(terminal) != 3:
        raise SystemExit("Faltan las tres capturas de terminal.")
    for capture in terminal:
        source = ROOT / capture["registro"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != capture["sha256_registro"]:
            raise SystemExit("El registro de terminal cambió después de la captura.")
        if not (ROOT / capture["captura"]).exists():
            raise SystemExit("Falta la captura de un registro de terminal.")
    catalog = [json.loads(path.read_text(encoding="utf-8")) for path in (ROOT / "data/cases/curated").glob("*.json")]
    labels = sum(1 + len(case["protected"]["diagnosis"]["synonyms"]) for case in catalog)
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(1.9)
    section.left_margin = section.right_margin = Cm(2)
    section.header_distance = section.footer_distance = Cm(.9)
    normal = doc.styles["Normal"]
    normal.font.name = "Arial"; normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.12
    for name, size in (("Title", 28), ("Heading 1", 17), ("Heading 2", 12)):
        style = doc.styles[name]
        style.font.name = "Arial"; style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(DARK if name == "Title" else TEAL)
        style.paragraph_format.keep_with_next = True
    header = section.header.paragraphs[0]
    header.text = "CONSULTA MÉDICA VIRTUAL  /  TA-012"
    header.style = doc.styles["Caption"]
    for run in header.runs:
        run.font.name = "Arial"; run.font.size = Pt(8); run.font.color.rgb = RGBColor.from_string(TEAL)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run("TA-012 · Implementación y evidencia | Página ").font.size = Pt(8)
    field = OxmlElement("w:fldSimple"); field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)

    def p(text="", bold=False):
        paragraph = doc.add_paragraph()
        run = paragraph.add_run(text); run.bold = bold
        return paragraph
    def h(text, level=1):
        doc.add_heading(text, level=level)
    def page(title):
        doc.add_page_break(); h(title)
    def bullet(text):
        return doc.add_paragraph(text, style="List Bullet")
    def code(text):
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(6)
        paragraph.paragraph_format.space_after = Pt(8)
        paragraph.paragraph_format.line_spacing = 1
        run = paragraph.add_run(text)
        run.font.name = "Consolas"; run.font.size = Pt(8)
        shade = OxmlElement("w:shd"); shade.set(qn("w:fill"), "F2F6F7")
        paragraph._p.get_or_add_pPr().append(shade)
    def table(headers, rows):
        result = doc.add_table(rows=1, cols=len(headers))
        result.style = "Table Grid"
        for cell, text in zip(result.rows[0].cells, headers):
            cell.text = str(text)
            shade = OxmlElement("w:shd"); shade.set(qn("w:fill"), "EAF2F3")
            cell._tc.get_or_add_tcPr().append(shade)
            for run in cell.paragraphs[0].runs:
                run.bold = True
        repeat = OxmlElement("w:tblHeader")
        result.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row in rows:
            cells = result.add_row().cells
            for cell, text in zip(cells, row):
                cell.text = str(text)
        for row in result.rows:
            no_split = OxmlElement("w:cantSplit")
            row._tr.get_or_add_trPr().append(no_split)
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_after = Pt(4)
                    for run in paragraph.runs:
                        run.font.name = "Arial"; run.font.size = Pt(9)
        p()
    def image(name, caption):
        path = HERE / "capturas" / (name + ".png")
        if not path.exists():
            raise SystemExit("Falta captura: " + str(path))
        doc.add_picture(str(path), width=Cm(16.4))
        paragraph = p(caption)
        paragraph.style = doc.styles["Caption"]

    doc.core_properties.title = "TA-012 — Calificación del diagnóstico final"
    doc.core_properties.subject = "Desarrollo, criterios de aceptación y evidencia de verificación"
    doc.core_properties.author = "Equipo de Consulta Médica Virtual"
    doc.core_properties.keywords = "TA-012, diagnóstico final, evaluación, Supabase, seguridad"
    p("INFORME DE IMPLEMENTACIÓN", True)
    doc.add_heading("TA-012", 0)
    doc.add_heading("Calificación del diagnóstico final", 1)
    p("Consulta Médica Virtual", True)
    p("Versión 1.1 · " + DATE)
    p("Estado: implementada; verificada localmente y con persistencia en Supabase real.", True)
    p("La tarea incorpora una calificación determinística de la respuesta final del alumno. "
      "Se compara con el diagnóstico y los sinónimos del caso únicamente durante el cierre autorizado de la consulta, "
      "se conserva el resultado y se explica el motivo en la hoja de evaluación.")
    h("Criterio de aceptación recibido", 2)
    p("«Normaliza entrada, compara con diagnóstico/sinónimos solo tras /finish; casos correcto, incorrecto, "
      "sinónimo, vacío y ambigüedad. Persistir puntuación/motivo; impedir fuga pre-cierre.»")
    h("Resultado comprobado", 2)
    bullet(f"{len(tests)} pruebas aprobadas, incluidas {len(specific)} pruebas específicas de TA-012.")
    bullet("5 de 5 escenarios aprobados en navegador contra la API local real de /finish.")
    bullet(f"Diagnóstico y sinónimos verificados en los {len(catalog)} casos curados del catálogo.")
    bullet("5 de 5 escenarios verificados con sesiones y eventos persistidos en Supabase real; sin recalificación al consultar.")
    bullet("8 capturas incluidas: los cinco resultados visuales y tres ventanas nativas de PowerShell con los registros de pruebas.")
    h("Alcance de la evidencia", 2)
    p("El servidor y el navegador se probaron localmente. Después se utilizó el .env proporcionado para "
      "comprobar sesiones y eventos contra Supabase real, incluida la lectura desde una instancia nueva del "
      "servicio. Las cinco sesiones y la cuenta creadas para esta prueba se eliminaron al terminar. "
      "No se incluyen claves ni tokens en este documento.")
    p("El historial de alumnos está desactivado y la tabla intentos no está instalada en esta base. Su "
      "adaptador se verificó mediante transporte HTTP simulado; no se afirma una escritura real en esa tabla. "
      "La puntuación y el motivo sí se comprobaron remotamente en sma_sesiones y sma_eventos.")

    page("1. Alcance y criterios de aceptación")
    p("Antes de TA-012, /finish conservaba el texto del diagnóstico y devolvía el puntaje de anamnesis. "
      "El reporte permitía compararlo visualmente con la referencia, pero no asignaba una nota al diagnóstico.")
    table(["Criterio", "Implementación y comprobación"], [
        ("Normalizar la entrada", "Unicode NFKD, minúsculas, tildes, espacios, signos y encabezados reconocidos."),
        ("Comparar únicamente al cerrar", "El motor exige phase=finalizada y finished_at antes de leer la referencia para calificar."),
        ("Cubrir los cinco escenarios", "Casos HTTP parametrizados y recorrido real de interfaz para correcto, incorrecto, sinónimo, vacío y ambiguo."),
        ("Persistir puntuación y motivo", "Guardado real de diagnosis_evaluation en sesión y evento. Ruta opcional intentos.reporte validada con transporte simulado."),
        ("Evitar fuga previa", "Pruebas de sesión, mensajes, eventos, reporte, credenciales y filtrado de la vista pública."),
    ])
    h("Política de puntuación", 2)
    table(["Resultado", "Puntos", "Interpretación"], [
        ("correct / reference_match", "100/100", "La etiqueta completa coincide con la referencia normalizada."),
        ("correct / synonym_match", "100/100", "Coincide con un sinónimo registrado para ese caso."),
        ("incorrect", "0/100", "No hay coincidencia exacta admitida."),
        ("empty", "0/100", "Diagnóstico ausente, null, espacios o solo signos."),
        ("ambiguous", "0/100 automático", "No se concede acierto; requires_review=true."),
    ])
    p("La nota del diagnóstico es independiente de la nota de anamnesis. No se incorporó una ponderación "
      "no especificada en la tarea. El campo intentos.puntaje y report.score conservan su significado anterior.")
    p("Ambiguous no equivale a incorrect. Su estado y motivo permiten distinguir una entrega no concluyente. "
      "La tarea marca la necesidad de revisión; no incorpora una pantalla nueva para adjudicar manualmente la nota.")

    page("2. Diseño y desarrollo")
    h("Recorrido de la información", 2)
    for text in [
        "El alumno escribe un único diagnóstico final y solicita finalizar la consulta.",
        "La API aplica la autorización de sesión de TA-011 antes de ejecutar el cierre.",
        "El servicio conserva la entrega original y el puntaje clínico, establece fase y fecha de cierre y llama al evaluador.",
        "El evaluador lee solo la referencia, los sinónimos y los diferenciales del caso correspondiente.",
        "Se normaliza la entrada y se obtiene estado, puntuación y motivo mediante reglas determinísticas.",
        "El resultado se guarda antes de responder y se reutiliza para el reporte, el historial y la interfaz.",
    ]:
        bullet(text)
    h("Normalización", 2)
    p("normalize_diagnosis convierte la entrada mediante NFKD y casefold; elimina marcas diacríticas y caracteres "
      "invisibles de formato, reconoce encabezados como «Mi diagnóstico final es:» y «Dx:», obtiene tokens "
      "alfanuméricos y une los espacios. También normaliza la referencia y cada sinónimo con la misma función.")
    code('Entrada:  "  Mi diagnóstico final es: MIGRAÑA.  "\nNormalizada: "migrana"\nEtiqueta admitida: "migraña"\nResultado: correct · synonym_match · 100/100')
    p("Se exige igualdad de toda la etiqueta normalizada. No se usa comparación por subcadenas, corrección "
      "ortográfica, embeddings ni un modelo de lenguaje para decidir la nota. «No es migraña» no recibe acierto "
      "por contener una etiqueta admitida.")
    h("Ambigüedad", 2)
    bullet("Se detectan varias alternativas separadas por o, y, barras, comas, punto y coma u otros delimitadores.")
    bullet("Se detectan preguntas y expresiones de incertidumbre, como «¿Migraña?» o «posible migraña».")
    bullet("Una etiqueta normalizada compartida con un diferencial requiere revisión.")
    bullet("Una etiqueta completa expresamente registrada prevalece sobre palabras aisladas de duda; por ejemplo, un sinónimo oficial que contiene «probable» sigue siendo admitido.")

    page("3. Contrato HTTP y protección del cierre")
    p("No se creó un endpoint de calificación anticipada. La operación continúa siendo:")
    code('POST /api/ai/sessions/{session_id}/finish\nContent-Type: application/json\nAuthorization: Bearer [TOKEN DEL DUEÑO]\n\n{"diagnosis": "CEFALEA MIGRAÑOSA", "hypotheses": []}')
    p("Para invitados se utiliza X-Session-Token, generado al iniciar la consulta. No se registra la credencial "
      "completa en la evidencia de esta tarea.")
    h("Ejemplo de resultado persistido", 2)
    code(json.dumps({"diagnosis_evaluation": samples[2]["resultado"]}, ensure_ascii=False, indent=2))
    p("El mismo objeto se devuelve en report.diagnosis.grading. El reporte conserva la referencia y sus sinónimos "
      "exclusivamente después del cierre. GET /report reutiliza el resultado guardado y no vuelve a comparar.")
    h("Controles de seguridad", 2)
    bullet("Una consulta abierta devuelve 409 al solicitar /report, sin referencia, sinónimos ni nota del diagnóstico.")
    bullet("El motor rechaza la calificación si faltan la fase finalizada o la fecha de cierre, antes de leer protected.")
    bullet("La vista pública filtra diagnosis_evaluation cuando la consulta todavía está abierta.")
    bullet("Sin credenciales se mantiene 401; una sesión ajena se trata como inexistente mediante 404.")
    bullet("Los valores score, reference o synonyms enviados por el cliente no sustituyen la referencia ni la puntuación calculadas en el servidor.")
    bullet("La nota no entra al contexto conversacional de los agentes ni al índice RAG.")

    page("4. Persistencia e integridad del resultado")
    table(["Destino", "Ruta del dato", "Condición"], [
        ("Sesión", "sma_sesiones.state.diagnosis_evaluation", "SESSION_STORE=supabase; en desarrollo se conserva en memoria."),
        ("Evento de cierre", "sma_eventos.payload.diagnosis_evaluation", "Se incorpora al evento session_finished."),
        ("Historial del alumno", "intentos.reporte.diagnosis_evaluation", "Historial habilitado y usuario propietario autenticado."),
        ("Respuesta HTTP", "diagnosis_evaluation y report.diagnosis.grading", "Solo tras el cierre autorizado."),
    ])
    p("El objeto incluye score, max_score, status, reason, reason_code, normalized_input, matched_term, "
      "requires_review y version. Los JSONB existentes admiten esta información; no se necesita una migración "
      "ni una columna nueva.")
    h("Reintentos y entrega original", 2)
    p("Un segundo /finish de una sesión finalizada devuelve la evaluación original sin recalcularla ni emitir "
      "otro evento de cierre. Si el historial ya se guardó, se reutiliza attempt_id para no duplicarlo.")
    p("Se corrigió también el caso en que Supabase falla al guardar el intento: al reintentar con un payload "
      "diferente, final_submission recupera la entrega original persistida. La columna diagnostico, las hipótesis "
      "y la calificación quedan coherentes entre sí.")
    h("Consultas de comprobación en Supabase", 2)
    code("select session_id,\n       state -> 'diagnosis_evaluation' as calificacion\nfrom public.sma_sesiones\nwhere phase = 'finalizada'\norder by updated_at desc\nlimit 10;")
    code("select caso_id,\n       reporte -> 'diagnosis_evaluation' ->> 'score' as nota,\n       reporte -> 'diagnosis_evaluation' ->> 'reason' as motivo\nfrom public.intentos\norder by creado_en desc\nlimit 10;")
    p("Estas consultas se proporcionan para inspección administrativa. La comprobación real de esta entrega "
      "leyó los registros por la API de Supabase, usando identificadores exclusivos de prueba. La consulta "
      "de intentos requiere que esa tabla esté instalada; actualmente no lo está. No se modificó el esquema.")
    p("Las sesiones históricas sin diagnosis_evaluation siguen siendo legibles y no se recalifican automáticamente.")

    page("5. Archivos y cambios principales")
    table(["Archivo", "Responsabilidad"], [
        ("backend/server/engine/evaluation/diagnosis.py", "Nuevo normalizador y clasificador determinístico."),
        ("backend/server/engine/evaluation/service.py", "Barrera de cierre antes de calificar y de construir el reporte."),
        ("backend/server/orchestration/service.py", "Integración en finish, snapshot, evento, filtro público y entrega original."),
        ("backend/server/engine/evaluation/report.py", "Incluye la calificación ya persistida en diagnosis.grading."),
        ("backend/server/api/ai.py", "Guarda el historial usando final_submission, no el payload de un reintento."),
        ("backend/server/persistence/attempts.py", "Conserva puntuación y motivo dentro de reporte JSONB."),
        ("frontend/public/js/simulacion.js", "Muestra estado, nota y motivo recibidos del servidor."),
        ("frontend/public/simulacion.html y css/simulacion.css", "Panel de diagnóstico, vacío admitido y estados visuales diferenciados."),
        ("backend/tests/unit/test_final_diagnosis.py", "Normalización, reglas, cierre y etiquetas de todo el catálogo."),
        ("backend/tests/integration/test_ta012_diagnosis.py", "Contrato HTTP, persistencia, reintentos, manipulación y aislamiento."),
        ("frontend/tests/ta012.mjs", "Cinco escenarios contra /finish real en el navegador."),
    ])
    h("Ajuste de aislamiento de pruebas", 2)
    p("Se detectó una prueba del panel docente que dependía de un .env presente en el equipo. Se configuró "
      "con URL y clave ficticias dentro de su fixture y transporte HTTP simulado. No se añadieron secretos "
      "al proyecto ni se cambió el comportamiento productivo del panel.")

    page("6. Verificación y resultados")
    h("Resumen de ejecución", 2)
    p(f"Resultado final: {len(tests)} pruebas aprobadas; {len(specific)} específicas de TA-012. "
      "No se registraron fallos ni errores en el XML final. Tres pruebas de seguridad marcadas para "
      "servicios reales se deseleccionaron por la configuración local.")
    p(f"Se comprobaron las etiquetas de referencia y los sinónimos de {len(catalog)} casos curados: "
      f"{labels} etiquetas en conjunto. Las variantes en mayúsculas se calificaron de forma consistente.")
    table(["Escenario HTTP", "Entrada", "Estado", "Nota", "Motivo"], [
        (row["criterio"], row["entrada"] or "(vacío)", row["resultado"]["status"],
         str(row["resultado"]["score"]) + "/100", row["resultado"]["reason_code"]) for row in samples
    ])
    p("En esta matriz de pruebas automatizadas se comprobó el resultado en la sesión y en intentos.reporte "
      "mediante transporte HTTP simulado, además de la coincidencia entre el reporte consultado después y "
      "el devuelto por /finish. La prueba adicional contra Supabase real se detalla en la sección 9; "
      "allí se verificaron sesiones y eventos, con el historial desactivado.")
    h("Pruebas adicionales relevantes", 2)
    for text in [
        "Entrada ausente, null, solo espacios y solo signos: nota 0 y estado empty.",
        "Comparación completa: entradas negadas, parciales o con errores no obtienen acierto por subcadena.",
        "Respuestas dudosas y etiquetas compartidas: estado ambiguous y requiere revisión.",
        "Propuesta de diagnóstico durante la conversación: no se califica antes de /finish.",
        "GET de sesión, eventos y reporte: no revela la nota ni la referencia antes del cierre.",
        "Cierres repetidos y reintento tras un fallo de historial: mantienen la entrega original.",
        "Persistencia con SupabaseSessionStore y lectura desde un servicio nuevo: conserva el mismo resultado.",
        "Otro usuario, otro invitado y un cliente sin credenciales: no obtienen la calificación ajena.",
        "Intento del cliente de imponer score=100 o una referencia propia: se calcula con el caso del servidor.",
    ]:
        bullet(text)
    h("Artefactos de evidencia", 2)
    p("pruebas/TA-012/pytest.xml; resultados/*.json; navegador.json; supabase_real.json; capturas/*.png; "
      "terminal/*.txt y terminal/capturas.json. Los resultados de navegador proceden de la API local real "
      "y no de un mock de /finish. Las capturas de terminal conservan el hash SHA-256 de su registro original.")

    page("7. Resultado visible para el alumno")
    p("La hoja final muestra la propuesta, la referencia del caso y un bloque con estado, puntos y motivo. "
      "Los colores diferencian acierto, error, vacío y ambigüedad. El alumno puede cerrar sin diagnóstico; "
      "el formulario explica previamente que se registrará sin respuesta y con cero puntos.")
    for index, (name, caption) in enumerate([
        ("correcto", "Diagnóstico de referencia: 100/100 y coincidencia exacta tras normalizar."),
        ("incorrecto", "Respuesta incorrecta: 0/100 y explicación de la falta de coincidencia."),
        ("sinonimo", "Sinónimo admitido: 100/100 y explicación de la coincidencia."),
        ("vacio", "Entrega vacía: 0/100 y motivo explícito."),
        ("ambiguo", "Varias alternativas: 0/100 automático y marca para revisión docente."),
    ], start=1):
        if index > 1:
            doc.add_page_break()
        image(name, f"Figura {index}. {caption}")
    p("Las cinco capturas se generaron con el caso CIR-101 y el servidor local. El audio se aceleró "
      "únicamente para automatizar el recorrido; el resultado de evaluación provino del backend real.")
    h("Pasos de comprobación manual", 2)
    for text in ["Abrir la simulación e iniciar una consulta.", "Pulsar Realizar Diagnóstico.",
                 "Escribir un único diagnóstico o dejar el campo vacío.",
                 "Guardar y finalizar: revisar el estado, los puntos y el motivo en la hoja.",
                 "Reabrir la hoja o consultar /report: comprobar que la nota permanece igual."]:
        bullet(text)

    page("8. Reproducción, decisiones y límites")
    h("Entorno y comandos", 2)
    p("Validación realizada en Windows con Python 3.12.10, Node.js v24.9.0, pytest 8.3.4 y Microsoft Edge "
      "en modo headless mediante Playwright. La comparación no requiere Groq ni otro proveedor de IA.")
    code("npm run setup -- --extras dev\n$env:TA012_EVIDENCIA = (Join-Path (Get-Location) 'pruebas/TA-012/resultados')\nnpm run test:diagnosis -- --junitxml=../pruebas/TA-012/pytest.xml")
    p("Para repetir el navegador, levantar el servidor en 3017 con casos locales, sesiones en memoria, "
      "RAG local sin índice embebido y sin servicios externos; en otra terminal ejecutar:")
    code("node frontend/tests/ta012.mjs")
    p("Para generar de nuevo este Word se requiere python-docx como herramienta documental, sin añadirla "
      "a las dependencias de ejecución del simulador:")
    code(".\\backend\\.venv\\Scripts\\python.exe -m pip install python-docx\n.\\backend\\.venv\\Scripts\\python.exe pruebas/TA-012/generar_informe.py")
    h("Decisiones explícitas", 2)
    bullet("Se conserva el puntaje de anamnesis y se añade una nota independiente de diagnóstico.")
    bullet("Solo se aceptan la referencia y los sinónimos registrados; no se infiere equivalencia clínica libre.")
    bullet("Una respuesta ambigua no obtiene puntos automáticamente y queda identificada para revisión.")
    bullet("La calificación guardada es la que muestra el reporte; consultarlo no ejecuta otra comparación.")
    bullet("La propuesta y sus hipótesis se toman de la entrega original en los reintentos de guardado.")
    h("Límites y despliegue", 2)
    p("No se incluyó corrección de errores tipográficos, expansión de abreviaturas no registradas, "
      "adjudicación manual de ambigüedades, combinación de notas por pesos ni recalificación histórica. "
      "Esas funciones requieren reglas adicionales fuera del criterio recibido.")
    p("El .env proporcionado utiliza CASE_STORE=supabase, SESSION_STORE=supabase y RAG_BACKEND=supabase_pgvector. "
      "La calificación no depende de generar texto ni de consultar el RAG. El historial de alumnos está "
      "desactivado: para usar su ruta opcional se necesita instalar la tabla intentos y habilitar la función.")
    p("No se ejecutaron cambios de esquema ni despliegues. La validación remota creó únicamente una cuenta "
      "y sesiones temporales de prueba y confirmó su eliminación, sin modificar los casos curados, "
      "el archivo .env ni los roles de usuarios existentes.")

    page("9. Validación con Supabase real")
    p("Se ejecutó verificar_supabase_real.py utilizando las credenciales del .env, sin imprimirlas. "
      f"Fecha UTC del registro: {remote['fecha_utc']}. Se comprobaron casos_curados, sma_sesiones y sma_eventos; "
      "luego se autenticó una cuenta temporal propia y se ejecutaron los cinco cierres sobre el caso CIR-101.")
    table(["Escenario", "Estado", "Nota", "Sesión real", "Evento real"], [
        (row["caso"], row["estado"], str(row["puntuacion"]) + "/100",
         "PASA" if row["sesion_real"] else "FALLA", "PASA" if row["evento_real"] else "FALLA")
        for row in remote["casos"]
    ])
    h("Comprobaciones realizadas por escenario", 2)
    bullet("/report antes del cierre devuelve 409; sin credenciales devuelve 401.")
    bullet("/finish devuelve 200 y el estado, puntuación y motivo esperados.")
    bullet("Lectura directa por la API de Supabase: el JSONB de la sesión y del evento contiene la misma calificación.")
    bullet("Un servicio nuevo recupera la sesión remota y devuelve la misma nota sin recalificar.")
    bullet("Un segundo cierre con otra respuesta conserva la entrega y la puntuación originales.")
    h("Limpieza y límite del historial", 2)
    p("Resultado final: PASA, 5/5. Al terminar se confirmó la eliminación de la cuenta temporal, las cinco "
      "sesiones y sus eventos. Los identificadores quedan en supabase_real.json para trazabilidad; los datos "
      "de prueba ya no permanecen en las tablas.")
    p("La API respondió 404/PGRST205 para intentos: la tabla no está instalada en esta base. HISTORIAL_ALUMNOS "
      "permanece desactivado. No se creó ni migró el historial para esta prueba; sus pruebas automatizadas "
      "con transporte simulado se reportan por separado. Esta limitación no impide persistir el resultado "
      "de TA-012 en la sesión y su evento de cierre.")
    h("Repetir la comprobación remota", 2)
    code(".\\backend\\.venv\\Scripts\\python.exe pruebas/TA-012/verificar_supabase_real.py")
    p("Este comando requiere las claves configuradas y crea datos temporales de prueba con limpieza al "
      "finalizar. Nunca debe registrarse el contenido del .env como evidencia.")

    page("10. Capturas de los registros del terminal")
    p("Las figuras siguientes son capturas de ventanas nativas propias de PowerShell que muestran la salida "
      "original guardada al ejecutar las pruebas. No son capturas de la terminal integrada de VS Code ni "
      "salidas reconstruidas manualmente. El script mostrar_registro.ps1 muestra cada archivo sin modificarlo; "
      "capturar_terminal.py captura exclusivamente esa ventana. No se incluye el escritorio ni ventanas con secretos.")
    for index, (capture, title, explanation) in enumerate(zip(terminal, [
        "Batería automatizada", "Persistencia en Supabase real", "Cinco recorridos en navegador",
    ], [
        "566 pruebas aprobadas y tres deseleccionadas; XML de resultados generado correctamente.",
        "Cinco cierres aprobados, puntuación persistida en sesiones y eventos y limpieza confirmada. La ausencia de intentos queda indicada en la salida.",
        "Cinco respuestas HTTP 200 y resultados visuales correctos contra el endpoint real de cierre.",
    ]), start=6):
        if index > 6:
            doc.add_page_break()
        h(title, 2)
        p(explanation)
        image(Path(capture["captura"]).stem, f"Figura {index}. Ventana de PowerShell con el registro original: {Path(capture['registro']).name}.")
        p("Registro: " + capture["registro"])
        code("SHA-256: " + capture["sha256_registro"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    align_document(doc, 'TA-012')
    doc.save(OUTPUT)
    # Validación del paquete y lectura posterior: detectar archivos incompletos o XML corrupto.
    with ZipFile(OUTPUT) as archive:
        if archive.testzip() is not None:
            raise SystemExit("El paquete Word no superó la validación ZIP.")
        for name in archive.namelist():
            if name.endswith(".xml"):
                ET.fromstring(archive.read(name))
    check = Document(OUTPUT)
    text = "\n".join(paragraph.text for paragraph in check.paragraphs)
    if "TA-021" not in text or "10. Capturas" not in text or len(check.inline_shapes) != 8:
        raise SystemExit("La validación de contenido del Word falló.")
    summary = {"tarea": "TA-021", "codigo_evidencia": "TA-012", "fecha": DATE, "pruebas_aprobadas": len(tests),
               "pruebas_ta012": len(specific), "navegador": "5/5", "casos_curados": len(catalog),
               "etiquetas_comprobadas": labels, "word": str(OUTPUT.relative_to(ROOT)),
               "supabase_real": "5/5 sesiones y eventos", "historial_real_disponible": remote["historial_real_disponible"],
               "limpieza_remota_verificada": True, "capturas_terminal": len(terminal),
               "word_zip_xml_validos": True, "capturas_incluidas": len(check.inline_shapes)}
    (HERE / "resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

