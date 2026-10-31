"""Adaptadores RAGAS modernos sobre el gateway y embeddings existentes.

Se importan solo cuando se solicita evaluar respuestas con el juez Groq.
"""
from __future__ import annotations

import asyncio
import json

from ragas.embeddings.base import BaseRagasEmbedding
from ragas.llms.base import InstructorBaseRagasLLM

from server.ai.embeddings import get_embedding_provider


class GroqPoolJudge(InstructorBaseRagasLLM):
    def __init__(self, gateway, usage):
        self.gateway = gateway
        self.usage = usage

    def generate(self, prompt, response_model):
        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        reply = self.gateway.generate_json([
            {"role": "system", "content": "Devuelve exclusivamente un objeto JSON válido "
             "que cumpla este esquema JSON:\n" + schema},
            {"role": "user", "content": prompt},
        ], temperature=0)
        # Solo se contabiliza uso reportado por respuestas exitosas del gateway.
        # Los intentos fallidos del pool pueden tener consumo no observable.
        self.usage["successful_gateway_calls"] += 1
        self.usage["input_tokens"] += reply.input_tokens
        self.usage["output_tokens"] += reply.output_tokens
        if reply.input_tokens or reply.output_tokens:
            self.usage["gateway_calls_with_usage"] += 1
        return response_model.model_validate_json(reply.text)

    async def agenerate(self, prompt, response_model):
        return await asyncio.to_thread(self.generate, prompt, response_model)


class LocalSemanticEmbeddings(BaseRagasEmbedding):
    """Usa el proveedor semántico del proyecto, sin llamar embeddings en Groq."""

    def __init__(self, model):
        super().__init__()
        self.model = model

    def embed_texts(self, texts, **kwargs):
        provider = get_embedding_provider("sentence_transformers", model=self.model)
        return provider.embed_sync(texts).tolist()

    def embed_text(self, text, **kwargs):
        return self.embed_texts([text], **kwargs)[0]

    async def aembed_text(self, text, **kwargs):
        return await asyncio.to_thread(self.embed_text, text, **kwargs)

    async def aembed_texts(self, texts, **kwargs):
        return await asyncio.to_thread(self.embed_texts, texts, **kwargs)
