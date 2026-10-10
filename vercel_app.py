"""Punto de entrada en Vercel: el servidor vive en backend/ y sus módulos se importan como server.*."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from server.main import app  # noqa: E402

__all__ = ["app"]
