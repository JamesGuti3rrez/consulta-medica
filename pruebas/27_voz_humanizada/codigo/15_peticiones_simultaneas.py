"""Hipótesis: edge-tts falla más cuando se le piden dos audios a la vez (pregunta del doctor y respuesta
adelantada del paciente) que cuando se le piden de uno en uno.

Hace RONDAS rondas de dos peticiones simultáneas y las mismas en secuencia, y cuenta los fallos.
"""

import asyncio
import sys
import time

import edge_tts

PAR = [("¿Ha tenido fiebre o vómitos?", "es-MX-JorgeNeural"), ("No recuerdo haber tenido fiebre", "es-PE-AlexNeural")]
RONDAS = 10


async def una(texto: str, voz: str) -> bool:
    audio = 0
    try:
        async for chunk in edge_tts.Communicate(texto, voz).stream():
            if chunk["type"] == "audio":
                audio += len(chunk["data"])
    except edge_tts.exceptions.NoAudioReceived:
        return False
    return audio > 0


async def main() -> int:
    for modo in ("simultaneas", "en_secuencia"):
        fallos = total = 0
        inicio = time.perf_counter()
        for _ in range(RONDAS):
            if modo == "simultaneas":
                resultados = await asyncio.gather(*(una(t, v) for t, v in PAR))
            else:
                resultados = [await una(t, v) for t, v in PAR]
            fallos += resultados.count(False)
            total += len(resultados)
        print(f"{modo:<13} {fallos} fallos de {total} peticiones ({time.perf_counter() - inicio:.1f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
