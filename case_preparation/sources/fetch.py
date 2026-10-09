from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from .registry import SOURCE_DEFINITIONS, SourceFile


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW_ROOT = REPO_ROOT / "data" / "raw"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "consulta-medica/case-preparation"})
    with urlopen(request) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _check_hash(source_file: SourceFile, actual: str, path: Path) -> None:
    if actual != source_file.sha256:
        raise ValueError(
            f"Huella SHA-256 inesperada para {path.name}: se esperaba {source_file.sha256}, se obtuvo {actual}."
        )


def _previous_obtained_at(manifest_path: Path) -> dict[str, str]:
    """Conserva la fecha real de obtención al volver a verificar archivos ya descargados."""
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        item["name"]: item.get("obtained_at") or manifest.get("obtained_at")
        for item in manifest.get("files", [])
    }


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def fetch_dataset(dataset: str, raw_root: Path | None = None) -> dict:
    if dataset not in SOURCE_DEFINITIONS:
        raise ValueError(f"Dataset no soportado: {dataset}")

    source = SOURCE_DEFINITIONS[dataset]
    dataset_dir = (raw_root or DATA_RAW_ROOT) / dataset
    dataset_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = dataset_dir / "source_manifest.json"
    previous = _previous_obtained_at(manifest_path)
    now = datetime.now(timezone.utc).isoformat()

    downloaded_files: list[dict] = []
    for source_file in source.files:
        file_path = dataset_dir / source_file.name
        if file_path.exists():
            status = "existing"
            current_hash = _sha256(file_path)
            _check_hash(source_file, current_hash, file_path)
            obtained_at = previous.get(source_file.name) or _mtime_iso(file_path)
        else:
            status = "downloaded"
            temp_file = dataset_dir / f".{source_file.name}.part"
            if temp_file.exists():
                temp_file.unlink()
            _download_file(source_file.url, temp_file)
            current_hash = _sha256(temp_file)
            # Una descarga con huella distinta no reemplaza nada en data/raw/.
            _check_hash(source_file, current_hash, file_path)
            temp_file.replace(file_path)
            obtained_at = now
        downloaded_files.append({
            "name": source_file.name,
            "url": source_file.url,
            "description": source_file.description,
            "path": _display_path(file_path),
            "sha256": current_hash,
            "sha256_verified": True,
            "status": status,
            "obtained_at": obtained_at,
        })

    manifest = {
        "name": source.name,
        "url": source.url,
        "version": source.version,
        "license": source.license,
        "files": downloaded_files,
        "obtained_at": min(item["obtained_at"] for item in downloaded_files),
        "obtained_by": source.obtained_by,
        "verified_at": now,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga y registra datasets fuente para el pipeline.")
    parser.add_argument("--dataset", required=True, choices=sorted(SOURCE_DEFINITIONS.keys()))
    args = parser.parse_args()
    fetch_dataset(args.dataset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
