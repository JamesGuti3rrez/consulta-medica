#!/usr/bin/env python3
"""Lista data/raw/medqa/ y compara cada archivo registrado con su huella SHA-256 esperada."""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from case_preparation.adapters.medqa import _is_allowed_source  # noqa: E402
from case_preparation.sources.registry import SOURCE_DEFINITIONS  # noqa: E402

RAW_DIR = REPO_ROOT / "data" / "raw" / "medqa"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


print(f"Contenido de {RAW_DIR.relative_to(REPO_ROOT)} (no se versiona en Git):")
for path in sorted(RAW_DIR.iterdir()):
    kind = "dir " if path.is_dir() else "file"
    size = "" if path.is_dir() else f"{path.stat().st_size:>12,} B"
    print(f"  {kind}  {path.name:<28} {size}")

source = SOURCE_DEFINITIONS["medqa"]
print(f"\nArchivos registrados para {source.name} ({source.url}, licencia {source.license}):")
failed = 0
for source_file in source.files:
    path = RAW_DIR / source_file.name
    actual = sha256(path) if path.exists() else "(no existe)"
    ok = actual == source_file.sha256
    failed += not ok
    print(f"  [{'OK' if ok else 'FALLA'}] {source_file.name}")
    print(f"        origen:   {source_file.url}")
    print(f"        esperado: {source_file.sha256}")
    print(f"        obtenido: {actual}")
    print(f"        {source_file.description}")

zip_path = RAW_DIR / "data_clean.zip"
if zip_path.exists():
    names = [n for n in zipfile.ZipFile(zip_path).namelist() if n.endswith(".jsonl") and "__MACOSX" not in n]
    admitted = [n for n in names if _is_allowed_source(n)]
    print(f"\ndata_clean.zip (se lee sin descomprimir): {len(names)} archivos .jsonl; "
          f"{len(admitted)} admitidos por la decisión 0001 §1:")
    for name in admitted:
        print(f"  {name}")
sys.exit(1 if failed else 0)
