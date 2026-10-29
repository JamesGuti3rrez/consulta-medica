"""Hipótesis: el primer trozo de audio llega mucho antes que el mp3 completo, sobre todo en frases largas.

Mide, para una frase corta y una larga, cuándo llega el primer trozo y cuándo termina el audio.
"""

import asyncio
import time

import edge_tts

FRASES = {
    "corta": "Doctor, me duele la barriga.",
    "larga": "Martín Rojas, de 28 años, sexo masculino. Motivo de consulta: ingresó por dolor abdominal intenso; "
             "se diagnosticó apendicitis y se le realizó una apendicectomía de urgencia. Durante la intervención "
             "presentó un sangrado masivo y persistente que requirió transfusión de sangre.",
}


async def medir(nombre, texto):
    inicio = time.perf_counter()
    primero = None
    total = 0
    async for chunk in edge_tts.Communicate(texto, "es-MX-JorgeNeural").stream():
        if chunk["type"] == "audio":
            primero = primero or time.perf_counter() - inicio
            total += len(chunk["data"])
    print(f"{nombre:<6} ({len(texto):>3} caracteres): primer trozo {primero:.2f} s, audio completo {time.perf_counter() - inicio:.2f} s, {total} bytes")


async def main():
    for _ in range(2):
        for nombre, texto in FRASES.items():
            await medir(nombre, texto)


asyncio.run(main())
