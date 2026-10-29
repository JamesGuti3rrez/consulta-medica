"""Prueba de factibilidad: edge-tts genera voz neuronal en español sin clave.

Lista las voces es-* disponibles y sintetiza una frase de paciente con dos voces
peruanas. Los .mp3 quedan en pruebas/27_voz_humanizada/resultados/.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import edge_tts

SALIDA = Path(__file__).resolve().parent.parent / "resultados"
FRASE = "Doctor, desde ayer tengo un dolor fuerte en la barriga, aquí abajo a la derecha, y no he podido comer nada."
VOCES = ("es-PE-CamilaNeural", "es-PE-AlexNeural")


async def main() -> int:
    voces = await edge_tts.list_voices()
    espanol = sorted(v["ShortName"] for v in voces if v["Locale"].startswith("es-"))
    print(f"Voces en español disponibles: {len(espanol)}")
    for nombre in espanol:
        print(f"  {nombre}")

    SALIDA.mkdir(parents=True, exist_ok=True)
    for voz in VOCES:
        destino = SALIDA / f"01_{voz}.mp3"
        inicio = time.perf_counter()
        await edge_tts.Communicate(FRASE, voz).save(str(destino))
        segundos = time.perf_counter() - inicio
        print(f"{voz}: {destino.stat().st_size} bytes en {segundos:.2f} s -> {destino.name}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
