#!/usr/bin/env python3
"""Herramienta para generar evidencias de artefactos del sprint.

Uso principal:
  python pruebas/_herramientas/evidencia.py codigo <archivo> --lineas 1-40 --salida salida.png
  python pruebas/_herramientas/evidencia.py ejecutar "python -V" --cwd backend --salida salida.png
  python pruebas/_herramientas/evidencia.py archivo archivo.json --salida salida.png
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import guess_lexer_for_filename
from pygments.util import ClassNotFound


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# Ancho de escritorio/PC: todas las evidencias se generan en vista de PC.
PNG_WIDTH = 1440
MAX_LINES = 400
FONT_CANDIDATES = (
    "C:/Windows/Fonts/consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
)


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _render_text_png(title: str, body: str, output: Path) -> None:
    font = _font(15)
    title_font = _font(17)
    line_height = 20
    columns = int((PNG_WIDTH - 60) / max(1.0, font.getlength("M")))
    wrapped: list[str] = []
    for line in body.splitlines() or [""]:
        line = line.expandtabs(4)
        wrapped.extend(line[i : i + columns] for i in range(0, max(len(line), 1), columns))
    if len(wrapped) > MAX_LINES:
        omitted = len(wrapped) - MAX_LINES
        wrapped = wrapped[:MAX_LINES] + [f"... ({omitted} líneas más; ver el .txt completo)"]
    image = Image.new("RGB", (PNG_WIDTH, max(320, 100 + len(wrapped) * line_height)), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, PNG_WIDTH, 56), fill=(30, 41, 59))
    draw.text((30, 18), title[:150], font=title_font, fill=(241, 245, 249))
    for idx, line in enumerate(wrapped):
        draw.text((30, 76 + idx * line_height), line, font=font, fill=(30, 30, 30))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def _render_code_png(file_path: Path, output: Path, line_range: str | None = None) -> None:
    source = _read_text(file_path)
    if line_range:
        start_text, end_text = line_range.split("-", 1)
        start = int(start_text)
        end = int(end_text)
        lines = source.splitlines()
        source = "\n".join(lines[start - 1 : end])

    try:
        lexer = guess_lexer_for_filename(str(file_path), source)
    except ClassNotFound:
        from pygments.lexers import TextLexer
        lexer = TextLexer()

    formatter = ImageFormatter(font_name="Consolas", image_format="png", line_numbers=True, style="default")
    png = highlight(source, lexer, formatter)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(png)


def _render_json_or_csv_png(file_path: Path, output: Path) -> None:
    if file_path.suffix.lower() == ".csv":
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        text = "\n".join(", ".join(row) for row in rows[:40])
    else:
        data = json.loads(file_path.read_text(encoding="utf-8-sig"))
        text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    _render_text_png(f"Archivo: {file_path}", text, output)


def cmd_codigo(args: argparse.Namespace) -> int:
    _render_code_png(Path(args.archivo), Path(args.salida), args.lineas)
    return 0


def cmd_ejecutar(args: argparse.Namespace) -> int:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    result = subprocess.run(
        args.comando,
        shell=True,
        cwd=args.cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output_txt = Path(str(args.salida).rsplit(".", 1)[0] + ".txt")
    output_txt.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        f"DIRECTORIO: {Path(args.cwd or Path.cwd()).resolve()}\n"
        f"COMANDO: {args.comando}\n"
        f"FECHA: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"CODIGO_SALIDA: {result.returncode}\n\n"
        f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n"
    )
    output_txt.write_text(payload, encoding="utf-8")
    _render_text_png(f"Ejecución: {args.comando}", payload, Path(args.salida))
    return result.returncode


def cmd_archivo(args: argparse.Namespace) -> int:
    _render_json_or_csv_png(Path(args.archivo), Path(args.salida))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera evidencias reales en PNG para el sprint.")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    codigo = subparsers.add_parser("codigo", help="Genera una captura de código.")
    codigo.add_argument("archivo")
    codigo.add_argument("--lineas", default=None)
    codigo.add_argument("--salida", required=True)
    codigo.set_defaults(func=cmd_codigo)

    ejecutar = subparsers.add_parser("ejecutar", help="Genera una captura de una ejecución.")
    ejecutar.add_argument("comando")
    ejecutar.add_argument("--cwd", default=None, help="Directorio de trabajo del comando (evita depender de 'cd').")
    ejecutar.add_argument("--salida", required=True)
    ejecutar.set_defaults(func=cmd_ejecutar)

    archivo = subparsers.add_parser("archivo", help="Genera una captura de un archivo JSON o CSV.")
    archivo.add_argument("archivo")
    archivo.add_argument("--salida", required=True)
    archivo.set_defaults(func=cmd_archivo)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(args.func(args))
