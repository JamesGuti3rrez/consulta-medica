"""POST /api/voz: devuelve el audio de una frase con la voz del personaje, o 503 si la voz está apagada.

El sintetizador real (edge-tts) se reemplaza por uno simulado: estas pruebas no usan internet.
"""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from server.api import voice as voice_api
from server.main import app
from server.voice import tts

client = TestClient(app)
FAKE_MP3 = b"ID3-audio-simulado"


@pytest.fixture
def voice_on(monkeypatch):
    calls = []

    async def fake_synthesize(text, voice):
        calls.append((text, voice))
        return FAKE_MP3

    monkeypatch.setattr(voice_api, "settings", replace(voice_api.settings, tts_provider="edge"))
    monkeypatch.setattr(tts, "synthesize", fake_synthesize)
    monkeypatch.setattr(tts, "available", lambda: True)
    return calls


def test_returns_mp3_with_the_voice_of_the_speaker(voice_on):
    response = client.post("/api/voz", json={"texto": "Me duele la barriga.", "personaje": "patient", "sexo": "femenino"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == FAKE_MP3
    assert voice_on == [("Me duele la barriga.", "es-PE-CamilaNeural")]


def test_unknown_speaker_is_rejected(voice_on):
    response = client.post("/api/voz", json={"texto": "Hola", "personaje": "student"})

    assert response.status_code == 422
    assert voice_on == []


@pytest.mark.parametrize("texto", ["", "   ", "a" * 601])
def test_empty_or_too_long_text_is_rejected(voice_on, texto):
    response = client.post("/api/voz", json={"texto": texto, "personaje": "doctor"})

    assert response.status_code == 422
    assert voice_on == []


def test_voice_off_answers_503_so_the_browser_uses_its_own_voice(monkeypatch):
    monkeypatch.setattr(voice_api, "settings", replace(voice_api.settings, tts_provider=""))

    response = client.post("/api/voz", json={"texto": "Hola", "personaje": "doctor"})

    assert response.status_code == 503


def test_missing_library_answers_503(monkeypatch):
    monkeypatch.setattr(voice_api, "settings", replace(voice_api.settings, tts_provider="edge"))
    monkeypatch.setattr(tts, "available", lambda: False)

    response = client.post("/api/voz", json={"texto": "Hola", "personaje": "doctor"})

    assert response.status_code == 503


def test_synthesis_failure_answers_502(voice_on, monkeypatch):
    async def failing_synthesize(text, voice):
        raise tts.VoiceError("sin conexión")

    monkeypatch.setattr(tts, "synthesize", failing_synthesize)

    response = client.post("/api/voz", json={"texto": "Hola", "personaje": "doctor"})

    assert response.status_code == 502
