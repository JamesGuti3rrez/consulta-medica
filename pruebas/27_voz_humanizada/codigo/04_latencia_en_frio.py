"""Hipótesis: la primera frase tarda más porque se importa edge_tts y se abre la primera conexión.

Mide, en un proceso nuevo, el tiempo de importar edge_tts y el de tres síntesis seguidas.
"""

import asyncio
import time

inicio = time.perf_counter()
import edge_tts  # noqa: E402

print(f"import edge_tts: {time.perf_counter() - inicio:.2f} s")


async def main():
    for intento in range(1, 4):
        inicio = time.perf_counter()
        audio = b"".join([c["data"] async for c in edge_tts.Communicate("Doctor, me duele la barriga.", "es-PE-AlexNeural").stream() if c["type"] == "audio"])
        print(f"síntesis {intento}: {time.perf_counter() - inicio:.2f} s ({len(audio)} bytes)")


asyncio.run(main())
