from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np

TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
DEFAULT_HASH_DIMENSION = 256
DEFAULT_SENTENCE_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass(frozen=True)
class EmbeddingMetadata:
    backend: str
    model: str
    dimension: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "model": self.model,
            "dimension": self.dimension,
        }


class EmbeddingProvider:
    """Proveedor único de embeddings para indexación y recuperación.

    `local_hash` es determinístico y sirve para pruebas/offline.
    `sentence_transformers` habilita recuperación semántica real cuando se instala
    el extra `semantic` y el modelo está disponible localmente.
    """

    def __init__(
        self,
        backend: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> None:
        selected = (backend or os.getenv("RAG_EMBEDDING_BACKEND", "local_hash")).strip().lower()
        if selected not in {"local_hash", "sentence_transformers"}:
            raise ValueError(f"RAG_EMBEDDING_BACKEND no soportado: {selected!r}")

        self.backend = selected
        self._model_obj = None
        if self.backend == "local_hash":
            self.model = model or "sha256-token-hash"
            self.dimension = dimension or int(
                os.getenv("RAG_HASH_EMBEDDING_DIMENSION", str(DEFAULT_HASH_DIMENSION))
            )
        else:
            self.model = model or os.getenv("RAG_EMBEDDING_MODEL", DEFAULT_SENTENCE_MODEL).strip()
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:  # pragma: no cover - depende del extra opcional
                raise RuntimeError(
                    "Instale el extra semántico: pip install -e \".[semantic]\"."
                ) from error
            self._model_obj = SentenceTransformer(self.model)
            detected = self._model_obj.get_sentence_embedding_dimension()
            if not isinstance(detected, int) or detected <= 0:
                raise RuntimeError("No se pudo determinar la dimensión del modelo de embeddings.")
            self.dimension = detected

    @property
    def metadata(self) -> EmbeddingMetadata:
        return EmbeddingMetadata(self.backend, self.model, self.dimension)

    def embed_sync(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        if self.backend == "local_hash":
            vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
            for row, text in enumerate(texts):
                for token in TOKEN_PATTERN.findall(text.casefold()):
                    digest = hashlib.sha256(token.encode("utf-8")).digest()
                    slot = int.from_bytes(digest[:4], "big") % self.dimension
                    sign = 1.0 if digest[4] & 1 else -1.0
                    vectors[row, slot] += sign
                norm = math.sqrt(float(np.dot(vectors[row], vectors[row])))
                if norm:
                    vectors[row] /= norm
            return vectors

        assert self._model_obj is not None
        vectors = self._model_obj.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)

    async def embed(self, texts: list[str]) -> np.ndarray:
        return self.embed_sync(texts)


@lru_cache(maxsize=4)
def get_embedding_provider(
    backend: str | None = None,
    model: str | None = None,
    dimension: int | None = None,
) -> EmbeddingProvider:
    return EmbeddingProvider(backend=backend, model=model, dimension=dimension)
