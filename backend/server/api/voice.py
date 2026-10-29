"""POST /api/voz: el audio (mp3) de una frase del simulador con la voz neuronal de su personaje.

Responde 503 si la voz está apagada (TTS_PROVIDER distinto de edge) o falta edge-tts, y 502 si el
servicio falla: en ambos casos el navegador usa su propia voz.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from ..config import settings
from ..voice import tts

router = APIRouter(prefix="/api")

MAX_TEXT = 600


class VoiceRequest(BaseModel):
    texto: str = Field(max_length=MAX_TEXT)
    personaje: Literal[tts.SPEAKERS]
    sexo: str | None = None

    @field_validator("texto")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El texto está vacío.")
        return value.strip()


@router.post("/voz", response_class=Response, responses={200: {"content": {"audio/mpeg": {}}}})
async def speak(request: VoiceRequest):
    if settings.tts_provider != "edge" or not tts.available():
        raise HTTPException(status_code=503, detail="La voz neuronal no está activada.")
    voice = tts.choose_voice(request.personaje, request.sexo)
    try:
        audio = await tts.synthesize(request.texto, voice)
    except tts.VoiceError as exc:
        raise HTTPException(status_code=502, detail="No se pudo generar la voz.") from exc
    return Response(content=audio, media_type="audio/mpeg")
