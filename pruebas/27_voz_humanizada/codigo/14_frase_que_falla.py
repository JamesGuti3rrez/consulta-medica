"""¿Falla edge-tts con ciertos textos sin punto final, o falla al azar?

Pide 6 veces cada variante de la frase que falló dos veces seguidas en el navegador y cuenta los fallos.
"""

import asyncio
import sys

import edge_tts

VOZ = "es-PE-AlexNeural"
VARIANTES = [
    "No recuerdo haber tenido fiebre",
    "No recuerdo haber tenido fiebre.",
    "No recuerdo con precisión cuándo empezó el dolor",
    "¿Desde cuándo tiene el dolor?",
]
INTENTOS = 6


async def una(texto: str) -> bool:
    try:
        async for chunk in edge_tts.Communicate(texto, VOZ).stream():
            if chunk["type"] == "audio":
                return True
    except edge_tts.exceptions.NoAudioReceived:
        return False
    return False


async def main() -> int:
    for texto in VARIANTES:
        resultados = [await una(texto) for _ in range(INTENTOS)]
        print(f"{resultados.count(False)} fallos de {INTENTOS}  «{texto}»")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
