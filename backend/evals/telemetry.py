"""Configuración de trazas del benchmark, independiente de la telemetría de RAGAS."""
from __future__ import annotations

from contextlib import contextmanager
import os


def configure_external_tracing(enabled):
    for name in ("LANGSMITH_TRACING", "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2"):
        os.environ[name] = "true" if enabled else "false"
    # Analytics de RAGAS no es el trazado que el usuario solicita a LangSmith.
    os.environ["RAGAS_DO_NOT_TRACK"] = "true"


def disable_external_tracing():
    configure_external_tracing(False)


@contextmanager
def evaluation_tracing(*, enabled, project_name=None):
    configure_external_tracing(enabled)
    try:
        from langsmith import tracing_context
    except ImportError:
        yield
    else:
        # El valor explícito vence un contexto heredado o variables cacheadas.
        # asyncio.to_thread propaga este contexto a las llamadas del juez.
        with tracing_context(enabled=enabled, parent=False, project_name=project_name):
            yield


@contextmanager
def local_tracing_only():
    with evaluation_tracing(enabled=False):
        yield
