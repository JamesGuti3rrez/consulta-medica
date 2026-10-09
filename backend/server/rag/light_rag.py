from __future__ import annotations

import hashlib
import math
import re
from typing import Any

LIGHTRAG_VERSION = "1.5.7"
EMBEDDING_DIMENSION = 256
TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


async def local_embedding(texts: list[str]) -> Any:
    import numpy as np

    vectors = np.zeros((len(texts), EMBEDDING_DIMENSION), dtype=np.float32)
    for row, text in enumerate(texts):
        for token in TOKEN_PATTERN.findall(text.casefold()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
            sign = 1.0 if digest[4] & 1 else -1.0
            vectors[row, slot] += sign
        norm = math.sqrt(float(np.dot(vectors[row], vectors[row])))
        if norm:
            vectors[row] /= norm
    return vectors


async def no_entity_extraction(*_args: Any, **_kwargs: Any) -> str:
    return "<|COMPLETE|>"
