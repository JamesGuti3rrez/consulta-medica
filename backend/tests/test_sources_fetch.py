from __future__ import annotations

import hashlib
import json

import pytest

from case_preparation.sources import fetch
from case_preparation.sources.registry import SourceDefinition, SourceFile


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _install_source(monkeypatch, content: bytes, expected_sha: str) -> None:
    source = SourceDefinition(
        name="Demo",
        url="https://example.org/demo",
        version="1",
        license="MIT",
        files=(SourceFile(name="demo.zip", url="https://example.org/demo.zip", sha256=expected_sha, description="Demo"),),
        obtained_by="Equipo de pruebas",
    )
    monkeypatch.setitem(fetch.SOURCE_DEFINITIONS, "demo", source)
    monkeypatch.setattr(fetch, "_download_file", lambda url, destination: destination.write_bytes(content))


def test_fetch_downloads_verifies_hash_and_records_each_file(tmp_path, monkeypatch):
    content = b"contenido original"
    _install_source(monkeypatch, content, _sha(content))

    manifest = fetch.fetch_dataset("demo", raw_root=tmp_path)

    assert (tmp_path / "demo" / "demo.zip").read_bytes() == content
    [entry] = manifest["files"]
    assert entry["url"] == "https://example.org/demo.zip"
    assert entry["sha256"] == _sha(content)
    assert entry["sha256_verified"] is True
    assert entry["status"] == "downloaded"
    saved = json.loads((tmp_path / "demo" / "source_manifest.json").read_text(encoding="utf-8"))
    assert saved["files"][0]["name"] == "demo.zip"


def test_fetch_rejects_download_with_unexpected_hash(tmp_path, monkeypatch):
    _install_source(monkeypatch, b"contenido alterado", _sha(b"contenido original"))

    with pytest.raises(ValueError, match="Huella SHA-256 inesperada"):
        fetch.fetch_dataset("demo", raw_root=tmp_path)

    assert not (tmp_path / "demo" / "demo.zip").exists()


def test_fetch_reverification_keeps_original_obtained_at(tmp_path, monkeypatch):
    content = b"contenido original"
    _install_source(monkeypatch, content, _sha(content))
    first = fetch.fetch_dataset("demo", raw_root=tmp_path)

    second = fetch.fetch_dataset("demo", raw_root=tmp_path)

    assert second["files"][0]["status"] == "existing"
    assert second["files"][0]["obtained_at"] == first["files"][0]["obtained_at"]
    assert second["verified_at"] >= first["verified_at"]
