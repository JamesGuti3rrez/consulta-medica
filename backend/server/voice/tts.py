"""Texto a voz con edge-tts: las voces neuronales de Microsoft Edge, sin clave.

Es una prueba local (rama James). Si edge-tts no está instalado o falla, la ruta /api/voz responde
con error y el navegador vuelve a su propia voz.
"""

from __future__ import annotations

PATIENT_VOICES = {"masculino": "es-PE-AlexNeural", "femenino": "es-PE-CamilaNeural"}
# El doctor nunca comparte la voz del paciente: con un paciente hombre habla otra voz masculina.
DOCTOR_VOICES = {"masculino": "es-MX-JorgeNeural", "femenino": "es-PE-AlexNeural"}
SERVICE_VOICES = {
    "laboratorio": "es-MX-DaliaNeural",
    "radiologia": "es-CO-GonzaloNeural",
    "especialista": "es-CL-CatalinaNeural",
}
SPEAKERS = ("doctor", "patient", *SERVICE_VOICES)
VOICES = frozenset({*PATIENT_VOICES.values(), *DOCTOR_VOICES.values(), *SERVICE_VOICES.values()})


class VoiceError(RuntimeError):
    """No se pudo generar el audio (sin conexión, servicio caído o respuesta vacía)."""


def choose_voice(speaker: str, sex: str | None) -> str:
    if speaker == "patient":
        return PATIENT_VOICES.get(sex or "", PATIENT_VOICES["femenino"])
    if speaker == "doctor":
        return DOCTOR_VOICES.get(sex or "", DOCTOR_VOICES["femenino"])
    if speaker in SERVICE_VOICES:
        return SERVICE_VOICES[speaker]
    raise ValueError(f"Personaje sin voz: {speaker}")


def available() -> bool:
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return False
    return True


async def synthesize(text: str, voice: str) -> bytes:
    import edge_tts

    audio = bytearray()
    try:
        async for chunk in edge_tts.Communicate(text, voice).stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
    except Exception as exc:  # edge-tts lanza errores de red y de su propio protocolo
        raise VoiceError(str(exc)) from exc
    if not audio:
        raise VoiceError("El servicio de voz no devolvió audio.")
    return bytes(audio)
