#!/usr/bin/env python3
"""Genera las capturas PNG de la evidencia de TA-011 y el índice evidencia.html.

Uso, desde la raíz del repositorio:
    backend\\.venv\\Scripts\\python.exe pruebas\\25_autorizacion_sesiones\\generar_capturas.py

Qué hace:
1. Por cada fase de resultados/<fase>/logs/TA011-XX.json arma una tarjeta HTML (encabezado con id, criterio
   y resultado; petición a la izquierda y respuesta a la derecha) y la fotografía en
   resultados/<fase>/capturas/TA011-XX_<nombre>.png.
2. Renderiza en HTML monoespaciado las salidas de texto (pytest, regresión, git diff) y los documentos .md, y
   los fotografía en capturas/.
3. Escribe evidencia.html (índice filtrable por criterio CA1-CA4 y por fase) y
   resultados/verificacion_capturas.txt (un PNG por caso ejecutado; casos sin JSON; secretos sin enmascarar).

Las fotos las toma fotografiar.cjs con el Chromium de Playwright ya instalado. Los JSON ya vienen con los
tokens enmascarados; este script vuelve a buscar secretos por si acaso y lo informa.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTADOS = HERE / "resultados"
CAPTURAS = HERE / "capturas"
CASOS = [f"TA011-{n:02d}" for n in range(1, 41)]

FASES = {
    "local_antes": "Local, antes del cambio (código vulnerable)",
    "local_despues": "Local, después del cambio",
    "vivo_antes": "En vivo, antes del cambio (servidor y Supabase reales)",
    "vivo_despues": "En vivo, después del cambio (servidor y Supabase reales)",
    "vercel_preview": "Vercel preview, después del cambio",
}

CSS = """
:root { --ok:#137333; --ok-bg:#e6f4ea; --bad:#b3261e; --bad-bg:#fce8e6; --muted:#5f6368; --line:#dadce0;
        --ink:#202124; --soft:#f8f9fa; --na:#5f6368; --na-bg:#eceff1; }
* { box-sizing: border-box; }
body { margin:0; background:#fff; color:var(--ink); font:15px/1.45 "Segoe UI", Arial, sans-serif; }
.wrap { width:1440px; padding:28px 32px; }
header.card { border:1px solid var(--line); border-radius:10px; padding:18px 22px; margin-bottom:18px; }
.top { display:flex; align-items:center; gap:16px; }
.id { font:700 28px/1 Consolas, monospace; }
.titulo { font-size:22px; font-weight:600; flex:1; }
.badge { font-weight:700; font-size:18px; padding:8px 18px; border-radius:8px; }
.PASA { color:var(--ok); background:var(--ok-bg); border:2px solid var(--ok); }
.FALLA { color:var(--bad); background:var(--bad-bg); border:2px solid var(--bad); }
.NA { color:var(--na); background:var(--na-bg); border:2px solid var(--na); }
.meta { margin-top:10px; color:var(--muted); font-size:13.5px; display:flex; flex-wrap:wrap; gap:6px 22px; }
.chip { display:inline-block; background:#e8f0fe; color:#1a4fb4; border-radius:12px; padding:1px 10px;
        font-weight:600; font-size:13px; margin-right:4px; }
.esperado { margin-top:10px; font-size:15px; }
.paso { border:1px solid var(--line); border-radius:10px; margin-bottom:14px; overflow:hidden; }
.paso h3 { margin:0; padding:9px 14px; font-size:15px; background:var(--soft); border-bottom:1px solid var(--line);
           display:flex; justify-content:space-between; }
.cols { display:grid; grid-template-columns:1fr 1fr; }
.cols > div { padding:10px 14px; min-width:0; }
.cols > div + div { border-left:1px solid var(--line); }
.lbl { font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); margin:6px 0 2px; }
pre { margin:0; font:12.5px/1.4 Consolas, monospace; white-space:pre-wrap; word-break:break-all;
      background:var(--soft); border-radius:6px; padding:7px 9px; }
.code { font:700 20px Consolas, monospace; }
.code.ok { color:var(--ok); } .code.bad { color:var(--bad); }
ul.checks { list-style:none; padding:0; margin:0; }
ul.checks li { padding:5px 0; border-bottom:1px dashed var(--line); font-size:14px; }
.tag { font:700 12px Consolas, monospace; padding:1px 7px; border-radius:4px; margin-right:8px; }
.tag.PASA { border-width:1px; } .tag.FALLA { border-width:1px; }
section.box { border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin-bottom:14px; }
section.box h2 { margin:0 0 8px; font-size:16px; }
.err pre { background:var(--bad-bg); }
.texto pre { font-size:13px; background:#fff; padding:0; }
table { border-collapse:collapse; width:100%; margin:8px 0 14px; font-size:14px; }
th, td { border:1px solid var(--line); padding:6px 9px; text-align:left; vertical-align:top; }
th { background:var(--soft); }
code { font-family:Consolas, monospace; font-size:.93em; background:var(--soft); padding:0 4px; border-radius:3px; }
.doc h1 { font-size:26px; } .doc h2 { font-size:20px; margin-top:24px; } .doc h3 { font-size:17px; }
"""


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def pretty(text) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        return json.dumps(text, ensure_ascii=False, indent=2)
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except (ValueError, TypeError):
        return text


def clip(text: str, lines: int = 40) -> str:
    rows = text.splitlines()
    if len(rows) <= lines:
        return text
    return "\n".join(rows[:lines]) + f"\n… ({len(rows) - lines} líneas más en el JSON del caso)"


def page(title: str, body: str) -> str:
    return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>{esc(title)}</title>"
            f"<style>{CSS}</style></head><body><div class='wrap'>{body}</div></body></html>")


def tarjeta(data: dict, fase: str) -> str:
    chips = "".join(f"<span class='chip'>{esc(c.strip())}</span>" for c in data["criterio"].split(","))
    res = data["resultado"]
    head = f"""
<header class='card'>
  <div class='top'><span class='id'>{esc(data['id'])}</span><span class='titulo'>{esc(data['titulo'])}</span>
  <span class='badge {res}'>{esc(res)}</span></div>
  <div class='meta'><span>Criterio: {chips}</span><span>Fase: <b>{esc(FASES.get(fase, fase))}</b></span>
  <span>Servidor: {esc(data['servidor'])}</span><span>Commit: <code>{esc(data['commit'])}</code></span>
  <span>Fecha: {esc(data['fecha'])}</span></div>
  <div class='esperado'><b>Resultado esperado:</b> {esc(data['resultado_esperado'])}</div>
</header>"""
    parts = [head]
    for note in data.get("notas", []):
        parts.append(f"<section class='box'><h2>Nota</h2><pre>{esc(note)}</pre></section>")
    for i, paso in enumerate(data["pasos"], 1):
        ok = paso["resultado"] == "PASA"
        headers = "\n".join(f"{k}: {v}" for k, v in paso["cabeceras"].items()) or "(ninguna)"
        resp_headers = "\n".join(f"{k}: {v}" for k, v in paso.get("cabeceras_respuesta", {}).items()) or "(ninguna)"
        sent = pretty(paso["cuerpo_enviado"]) if paso["cuerpo_enviado"] is not None else "(sin cuerpo)"
        parts.append(f"""
<div class='paso'>
  <h3><span>Paso {i}: {esc(paso['descripcion'])}</span><span class='tag {paso['resultado']}'>{paso['resultado']}</span></h3>
  <div class='cols'>
    <div><div class='lbl'>Petición - identidad</div><div><b>{esc(paso['identidad'])}</b></div>
      <div class='lbl'>Método y URL</div><pre>{esc(paso['metodo'])} {esc(paso['url'][:300])}</pre>
      <div class='lbl'>Cabeceras (tokens enmascarados)</div><pre>{esc(headers)}</pre>
      <div class='lbl'>Cuerpo enviado</div><pre>{esc(clip(sent, 14))}</pre></div>
    <div><div class='lbl'>Respuesta - código recibido / esperado</div>
      <div><span class='code {"ok" if ok else "bad"}'>{paso['codigo_recibido']}</span>
      &nbsp; esperado: <code>{esc(", ".join(map(str, paso['codigo_esperado'])))}</code></div>
      <div class='lbl'>Cabeceras de respuesta</div><pre>{esc(resp_headers)}</pre>
      <div class='lbl'>Cuerpo recibido</div><pre>{esc(clip(pretty(paso['cuerpo_recibido']), 30))}</pre></div>
  </div>
</div>""")
    if data.get("comprobaciones"):
        items = "".join(
            f"<li><span class='tag {c['resultado']}'>{c['resultado']}</span>{esc(c['descripcion'])}"
            f"{(' <span style=color:var(--muted)>- ' + esc(c['detalle']) + '</span>') if c['detalle'] else ''}</li>"
            for c in data["comprobaciones"])
        parts.append(f"<section class='box'><h2>Comprobaciones</h2><ul class='checks'>{items}</ul></section>")
    if data.get("error"):
        parts.append(f"<section class='box err'><h2>Detalle del fallo (pytest)</h2><pre>{esc(data['error'])}</pre></section>")
    return page(f"{data['id']} {data['titulo']}", "".join(parts))


def texto(title: str, subtitle: str, content: str) -> str:
    return page(title, f"<header class='card'><div class='top'><span class='titulo'>{esc(title)}</span></div>"
                       f"<div class='meta'>{esc(subtitle)}</div></header>"
                       f"<section class='box texto'><pre>{esc(content)}</pre></section>")


def _inline(text: str) -> str:
    text = esc(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    return text


def markdown(md: str) -> str:
    """Conversor mínimo de Markdown (títulos, tablas, listas, citas, código y párrafos)."""
    # Las líneas de continuación de un párrafo o de un elemento de lista se unen a la anterior.
    lines, in_code = [], False
    block_start = re.compile(r"\s*([-*]|\d+\.) |#|\||>|```")
    for raw in md.splitlines():
        if raw.startswith("```"):
            in_code = not in_code
        joinable = (not in_code and raw.strip() and not block_start.match(raw) and lines and lines[-1].strip()
                    and not lines[-1].startswith(("#", "|", "```")))
        if joinable:
            lines[-1] = lines[-1].rstrip() + " " + raw.strip()
        else:
            lines.append(raw)
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            out.append(f"<pre>{esc(chr(10).join(block))}</pre>")
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{_inline(line[level:].strip())}</h{level}>")
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            i -= 1
            head, *body = rows
            out.append("<table><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</table>")
        elif re.match(r"\s*([-*]|\d+\.) ", line):
            items = []
            while i < len(lines) and re.match(r"\s*([-*]|\d+\.) ", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.) ", "", lines[i]))
                i += 1
            i -= 1
            out.append("<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + "</ul>")
        elif line.startswith(">"):
            out.append(f"<blockquote>{_inline(line.lstrip('> '))}</blockquote>")
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
        i += 1
    return "\n".join(out)


def documento(md_path: Path) -> str:
    return page(md_path.stem, f"<div class='doc'>{markdown(md_path.read_text(encoding='utf-8'))}</div>")


SOSPECHOSOS = [
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # JWT completo
    re.compile(r"sb_(secret|publishable)_[A-Za-z0-9_-]{12,}"),  # clave de Supabase completa
    re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])"),  # credencial de capacidad
]


def secretos(text: str) -> list[str]:
    found = []
    for pattern in SOSPECHOSOS:
        for match in pattern.finditer(text):
            value = match.group(0)
            if len(set(value)) <= 2:  # relleno como "aaaa…" o "xxxx…": no es un secreto
                continue
            found.append(value[:6] + "…")
    return found


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="ta011_capturas_"))
    manifest: list[dict] = []
    resumen: dict[str, dict] = {}
    verificacion: list[str] = []

    def add(html_text: str, png: Path) -> None:
        png.parent.mkdir(parents=True, exist_ok=True)
        source = work / f"{len(manifest):04d}.html"
        source.write_text(html_text, encoding="utf-8")
        manifest.append({"html": str(source), "png": str(png)})

    for fase in FASES:
        logs = RESULTADOS / fase / "logs"
        if not logs.is_dir():
            continue
        resumen[fase] = {}
        for path in sorted(logs.glob("TA011-*.json")):
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            png = RESULTADOS / fase / "capturas" / f"{data['id']}_{data['nombre']}.png"
            add(tarjeta(data, fase), png)
            resumen[fase][data["id"]] = {"resultado": data["resultado"], "titulo": data["titulo"],
                                         "criterio": data["criterio"], "png": png, "json": path}
            leaks = secretos(raw)
            if leaks:
                verificacion.append(f"[{fase}] {path.name}: posibles secretos sin enmascarar: {leaks}")

    textos = [
        ("01_regresion_antes.txt", "pytest_resumen_antes.png", "Regresión completa ANTES de los cambios"),
        ("05_regresion_despues.txt", "pytest_resumen_despues.png", "Regresión completa DESPUÉS de los cambios"),
        ("local_antes_pytest.txt", "pytest_local_antes.png", "Suite TA-011, local, antes"),
        ("local_despues_pytest.txt", "pytest_local_despues.png", "Suite TA-011, local, después"),
        ("vivo_antes_pytest.txt", "pytest_vivo_antes.png", "Suite TA-011, en vivo, antes"),
        ("vivo_despues_pytest.txt", "pytest_vivo_despues.png", "Suite TA-011, en vivo, después"),
        ("vercel_preview_pytest.txt", "pytest_vercel_preview.png", "Suite TA-011, Vercel preview"),
        ("06_git_diff_cambios.txt", "git_diff_cambios.png", "git diff de los cambios de código de TA-011"),
        ("07_recorrido_scripts.txt", "recorrido_scripts.png", "Scripts del recorrido completo con la credencial"),
        ("07b_bateria_13_casos.txt", "bateria_13_casos.png", "Batería de la fase 18 con los 13 casos con guion"),
        ("09_preview_protegido.txt", "preview_vercel_protegido.png", "Preview de Vercel protegido por Vercel Authentication"),
    ]
    for name, png, title in textos:
        source = HERE / "ejecucion" / name
        if source.exists():
            content = source.read_text(encoding="utf-8-sig", errors="replace")
            add(texto(title, f"ejecucion/{name}", content), CAPTURAS / png)
            leaks = secretos(content)
            if leaks:
                verificacion.append(f"[texto] {name}: posibles secretos sin enmascarar: {leaks}")

    for md in ("01_inventario_rutas.md", "02_politica_acceso.md", "INFORME_TA-011.md"):
        source = HERE / md
        if source.exists():
            add(documento(source), HERE / md.replace(".md", ".png"))

    manifest_path = work / "manifiesto.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    subprocess.run(["node", str(HERE / "fotografiar.cjs"), str(manifest_path)], check=True, cwd=ROOT)

    # Verificación: un PNG por caso ejecutado y casos sin JSON en cada fase.
    lines = ["Verificación de capturas de TA-011", ""]
    for fase, casos in resumen.items():
        sin_png = [cid for cid, info in casos.items() if not info["png"].exists()]
        sin_json = [cid for cid in CASOS if cid not in casos]
        cuenta = {k: sum(1 for c in casos.values() if c["resultado"] == k) for k in ("PASA", "FALLA")}
        lines.append(f"[{fase}] JSON: {len(casos)} | PNG: {len(casos) - len(sin_png)} | PASA {cuenta['PASA']} | "
                     f"FALLA {cuenta['FALLA']}")
        lines.append(f"    casos sin PNG: {', '.join(sin_png) or 'ninguno'}")
        lines.append(f"    casos sin JSON en esta fase (no ejecutados): {', '.join(sin_json) or 'ninguno'}")
    lines.append("")
    lines.append("Secretos sin enmascarar: " + ("ninguno" if not verificacion else ""))
    lines.extend(verificacion)
    (RESULTADOS / "verificacion_capturas.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    escribir_indice(resumen)
    return 1 if verificacion else 0


def escribir_indice(resumen: dict[str, dict]) -> None:
    fases = list(resumen)
    filas = []
    for cid in CASOS:
        info = next((resumen[f][cid] for f in fases if cid in resumen[f]), None)
        if not info:
            continue
        celdas = "".join(
            f"<td><span class='tag {resumen[f][cid]['resultado']}'>{resumen[f][cid]['resultado']}</span></td>"
            if cid in resumen[f] else "<td><span class='tag NA'>NO EJECUTADA</span></td>" for f in fases)
        filas.append(f"<tr data-ca='{esc(info['criterio'])}'><td><code>{cid}</code></td><td>{esc(info['titulo'])}</td>"
                     f"<td>{esc(info['criterio'])}</td>{celdas}</tr>")
    tarjetas = []
    for fase in fases:
        for cid, info in sorted(resumen[fase].items()):
            rel = info["png"].relative_to(HERE).as_posix()
            tarjetas.append(
                f"<figure data-ca='{esc(info['criterio'])}' data-fase='{fase}'>"
                f"<figcaption><code>{cid}</code> {esc(info['titulo'])} - <span class='tag {info['resultado']}'>"
                f"{info['resultado']}</span> <small>{esc(FASES[fase])} | {esc(info['criterio'])} | "
                f"<a href='{info['json'].relative_to(HERE).as_posix()}'>JSON</a></small></figcaption>"
                f"<a href='{rel}'><img loading='lazy' src='{rel}' alt='{cid}'></a></figure>")
    otros = [p for p in sorted(CAPTURAS.glob("*.png"))] + [HERE / f for f in
             ("01_inventario_rutas.png", "02_politica_acceso.png") if (HERE / f).exists()]
    otras = "".join(f"<figure data-ca='todos' data-fase='todas'><figcaption>{esc(p.name)}</figcaption>"
                    f"<a href='{p.relative_to(HERE).as_posix()}'><img loading='lazy' src='{p.relative_to(HERE).as_posix()}'></a></figure>"
                    for p in otros)
    botones = "".join(f"<button data-ca='{c}'>{c}</button>" for c in ("Todos", "CA1", "CA2", "CA3", "CA4"))
    botones_fase = "<button data-fase='todas'>Todas las fases</button>" + "".join(
        f"<button data-fase='{f}'>{esc(FASES[f])}</button>" for f in fases)
    body = f"""
<h1>TA-011 - Autorización de sesiones y eventos: evidencia</h1>
<p>Una tarjeta por caso y por fase: petición y respuesta reales, con los tokens enmascarados. El detalle completo
de cada caso está en su JSON. Informe: <a href='INFORME_TA-011.md'>INFORME_TA-011.md</a>.</p>
<h2>Resultado por caso y fase</h2>
<table id='matriz'><tr><th>Caso</th><th>Título</th><th>Criterio</th>{''.join(f'<th>{esc(FASES[f])}</th>' for f in fases)}</tr>
{''.join(filas)}</table>
<h2>Capturas</h2>
<div class='filtros'>Criterio: {botones}</div><div class='filtros'>Fase: {botones_fase}</div>
<div id='galeria'>{''.join(tarjetas)}</div>
<h2>Ejecuciones, documentos y diff</h2><div>{otras}</div>
<script>
let ca = 'Todos', fase = 'todas';
function aplicar() {{
  document.querySelectorAll('#galeria figure').forEach(f => {{
    const okCa = ca === 'Todos' || f.dataset.ca.split(',').map(s => s.trim()).includes(ca);
    const okFase = fase === 'todas' || f.dataset.fase === fase;
    f.style.display = okCa && okFase ? '' : 'none';
  }});
  document.querySelectorAll('#matriz tr[data-ca]').forEach(r => {{
    r.style.display = ca === 'Todos' || r.dataset.ca.split(',').map(s => s.trim()).includes(ca) ? '' : 'none';
  }});
  document.querySelectorAll('button[data-ca]').forEach(b => b.classList.toggle('on', b.dataset.ca === ca));
  document.querySelectorAll('button[data-fase]').forEach(b => b.classList.toggle('on', b.dataset.fase === fase));
}}
document.querySelectorAll('button[data-ca]').forEach(b => b.onclick = () => {{ ca = b.dataset.ca; aplicar(); }});
document.querySelectorAll('button[data-fase]').forEach(b => b.onclick = () => {{ fase = b.dataset.fase; aplicar(); }});
aplicar();
</script>"""
    extra_css = """
.wrap { width:auto; max-width:1500px; }
.filtros { margin:6px 0; } .filtros button { margin:3px; padding:6px 12px; border:1px solid var(--line);
  border-radius:16px; background:#fff; cursor:pointer; font:inherit; }
.filtros button.on { background:#1a4fb4; color:#fff; border-color:#1a4fb4; }
figure { margin:14px 0 26px; } figcaption { margin-bottom:6px; font-size:15px; }
figure img { max-width:100%; border:1px solid var(--line); border-radius:8px; }
"""
    html_text = page("TA-011 evidencia", body).replace("</style>", extra_css + "</style>", 1)
    (HERE / "evidencia.html").write_text(html_text, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
