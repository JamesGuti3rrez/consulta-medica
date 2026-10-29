"""GET /api/voz: el audio (mp3) de una frase del simulador con la voz neuronal de su personaje.

El audio se transmite a medida que edge-tts lo genera: el navegador lo pone como src de un <audio> y
empieza a sonar con el primer trozo. Responde 503 si la voz está apagada (TTS_PROVIDER distinto de edge)
o falta edge-tts, y 502 si el servicio falla dos veces antes del primer trozo: en ambos casos el navegador usa su
propia voz. GET /api/voz/estado le dice de antemano si la voz está activa.
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..config import settings
from ..voice import tts

router = APIRouter(prefix="/api")

MAX_TEXT = 600
ATTEMPTS = 2
logger = logging.getLogger(__name__)


def _active() -> bool:
    return settings.tts_provider == "edge" and tts.available()


@router.get("/voz/estado")
def voice_status():
    return {"activa": _active()}


@router.get("/voz", response_class=StreamingResponse, responses={200: {"content": {"audio/mpeg": {}}}})
async def speak(
    texto: Annotated[str, Query(max_length=MAX_TEXT)],
    personaje: Literal[tts.SPEAKERS],
    sexo: str | None = None,
):
    texto = texto.strip()
    if not texto:
        raise HTTPException(status_code=422, detail="El texto está vacío.")
    if not _active():
        raise HTTPException(status_code=503, detail="La voz neuronal no está activada.")
    voice = tts.choose_voice(personaje, sexo)
    # Se espera el primer trozo antes de responder: si el servicio falla ahí, todavía se puede reintentar
    # o dar 502. edge-tts falla de vez en cuando sin motivo (No audio was received): se reintenta una vez.
    for attempt in range(1, ATTEMPTS + 1):
        chunks = tts.stream(texto, voice)
        try:
            first = await anext(chunks)
            break
        except tts.VoiceError as exc:
            logger.warning("edge-tts falló (intento %d de %d, %s): %s", attempt, ATTEMPTS, voice, exc)
            if attempt == ATTEMPTS:
                raise HTTPException(status_code=502, detail="No se pudo generar la voz.") from exc

    async def body():
        yield first
        try:
            async for chunk in chunks:
                yield chunk
        except tts.VoiceError:
            return  # El audio queda cortado; el navegador termina la frase con lo que recibió.

    return StreamingResponse(body(), media_type="audio/mpeg")
