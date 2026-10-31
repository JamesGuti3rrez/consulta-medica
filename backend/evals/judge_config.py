"""Configuración del juez; las claves nunca forman parte de los metadatos."""
from __future__ import annotations

import os
from dataclasses import dataclass

from server.config import _split_keys, settings


@dataclass(frozen=True, repr=False)
class JudgeSettings:
    provider: str
    model: str
    base_url: str
    api_keys: tuple[str, ...]
    embedding_backend: str
    embedding_model: str
    timeout_seconds: float


def resolve_judge_settings(environ=None):
    env = os.environ if environ is None else environ
    def value(name, default=""):
        return str(env.get(name) or "").strip() or default

    provider = value("RAGAS_PROVIDER", "groq").lower()
    if provider not in {"groq", "openai"}:
        raise ValueError("RAGAS_PROVIDER debe ser groq u openai")
    if provider == "groq":
        # Mismo pool del simulador. No se envía una clave Groq a otro proveedor.
        keys = _split_keys(value("GROQ_API_KEYS", value("GROQ_API_KEY")))
        model = value("RAGAS_MODEL", value("GROQ_MODEL", settings.groq_model))
        # RAGAS_BASE_URL es solo para el proveedor OpenAI opcional. Su antiguo valor
        # por defecto no debe provocar que claves Groq se envíen a api.openai.com.
        base_url = value("GROQ_BASE_URL", settings.groq_base_url)
        embedding_backend = value("RAGAS_EMBEDDING_BACKEND", "sentence_transformers")
    else:
        keys = _split_keys(value("RAGAS_API_KEY"))
        model = value("RAGAS_MODEL")
        base_url = value("RAGAS_BASE_URL", "https://api.openai.com/v1")
        embedding_backend = value("RAGAS_EMBEDDING_BACKEND", "openai")
    embedding_model = value("RAGAS_EMBEDDING_MODEL")
    if embedding_backend == "sentence_transformers" and not embedding_model:
        embedding_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    timeout = float(value("RAGAS_TIMEOUT", "30"))
    if timeout <= 0:
        raise ValueError("RAGAS_TIMEOUT debe ser positivo")
    return JudgeSettings(provider, model, base_url.rstrip("/"), keys,
                         embedding_backend, embedding_model, timeout)
