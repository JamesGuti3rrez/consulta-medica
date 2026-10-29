"""GET /api/voz: transmite el audio de una frase con la voz del personaje a medida que se genera.

El navegador lo reproduce mientras llega, sin esperar el mp3 completo. GET /api/voz/estado le dice si la
voz neuronal está activa. El sintetizador real (edge-tts) se reemplaza por uno simulado: sin internet.
"""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from server.api import voice as voice_api
from server.main import app
from server.voice import tts

client = TestClient(app)
CHUNKS = [b"ID3-trozo-1", b"-trozo-2", b"-trozo-3"]


@pytest.fixture
def voice_on(monkeypatch):
    calls = []

    async def fake_stream(text, voice):
        calls.append((text, voice))
        for chunk in CHUNKS:
            yield chunk

    monkeypatch.setattr(voice_api, "settings", replace(voice_api.settings, tts_provider="edge"))
    monkeypatch.setattr(tts, "stream", fake_stream)
    monkeypatch.setattr(tts, "available", lambda: True)
    return calls


def say(texto, personaje="doctor", sexo=None):
    params = {"texto": texto, "personaje": personaje}
    if sexo:
        params["sexo"] = sexo
    return client.get("/api/voz", params=params)


def test_streams_the_whole_mp3_with_the_voice_of_the_speaker(voice_on):
    response = say("Me duele la barriga.", "patient", "femenino")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"".join(CHUNKS)
    assert voice_on == [("Me duele la barriga.", "es-PE-CamilaNeural")]


def test_unknown_speaker_is_rejected(voice_on):
    assert say("Hola", "student").status_code == 422
    assert voice_on == []


@pytest.mark.parametrize("texto", ["", "   ", "a" * 601])
def test_empty_or_too_long_text_is_rejected(voice_on, texto):
    assert say(texto).status_code == 422
    assert voice_on == []


def test_voice_off_answers_503_so_the_browser_uses_its_own_voice(monkeypatch):
    monkeypatch.setattr(voice_api, "settings", replace(voice_api.settings, tts_provider=""))

    assert say("Hola").status_code == 503


def test_missing_library_answers_503(monkeypatch):
    monkeypatch.setattr(voice_api, "settings", replace(voice_api.settings, tts_provider="edge"))
    monkeypatch.setattr(tts, "available", lambda: False)

    assert say("Hola").status_code == 503


def test_failure_before_the_first_chunk_answers_502(voice_on, monkeypatch):
    async def failing_stream(text, voice):
        raise tts.VoiceError("sin conexión")
        yield b""  # pragma: no cover - lo vuelve generador

    monkeypatch.setattr(tts, "stream", failing_stream)

    assert say("Hola").status_code == 502


def test_status_reports_whether_the_voice_is_on(voice_on, monkeypatch):
    assert client.get("/api/voz/estado").json() == {"activa": True}

    monkeypatch.setattr(voice_api, "settings", replace(voice_api.settings, tts_provider=""))
    assert client.get("/api/voz/estado").json() == {"activa": False}
