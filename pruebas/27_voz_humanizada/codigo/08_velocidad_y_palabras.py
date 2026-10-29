"""Muestras de velocidad y marcas de tiempo por palabra de edge-tts.

1. El mismo párrafo del doctor a +0 %, +10 %, +20 % y +30 % (resultados/velocidad/*.mp3), con su duración.
2. Las marcas WordBoundary: en qué milisegundo empieza cada palabra, para mostrar el texto al ritmo de la voz.
"""

import asyncio
import sys
from pathlib import Path

import edge_tts

SALIDA = Path(__file__).resolve().parent.parent / "resultados" / "velocidad"
VOZ = "es-MX-JorgeNeural"
PARRAFO = ("Martín Rojas, de 28 años, sexo masculino. Motivo de consulta: ingresó por dolor abdominal intenso; "
           "se diagnosticó apendicitis y se le realizó una apendicectomía de urgencia.")
TICKS_POR_MS = 10_000  # edge-tts da los tiempos en unidades de 100 nanosegundos


async def muestra(rate: str) -> None:
    audio = bytearray()
    palabras = []
    async for chunk in edge_tts.Communicate(PARRAFO, VOZ, rate=rate, boundary="WordBoundary").stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            palabras.append((chunk["offset"] // TICKS_POR_MS, chunk["duration"] // TICKS_POR_MS, chunk["text"]))
    destino = SALIDA / f"08_velocidad_{rate.replace('+', 'mas').replace('%', '')}.mp3"
    destino.write_bytes(audio)
    fin = palabras[-1][0] + palabras[-1][1]
    print(f"rate {rate:>4}: {fin / 1000:.1f} s de voz, {len(palabras)} palabras con marca -> {destino.name}")
    return palabras


async def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    resultados = {}
    for rate in ("+0%", "+10%", "+20%", "+30%"):
        resultados[rate] = await muestra(rate)
    print("\nMarcas por palabra a +0 % (inicio en ms, palabra) y silencio antes de cada una:")
    anterior_fin = 0
    for inicio, duracion, texto in resultados["+0%"]:
        hueco = inicio - anterior_fin
        print(f"  {inicio:>6} ms  {texto:<16} {'<- pausa de ' + str(hueco) + ' ms' if hueco > 150 else ''}")
        anterior_fin = inicio + duracion
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
