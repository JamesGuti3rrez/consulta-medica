"""¿Cuánto se acortan las pausas si la voz conserva los signos, pero cambia los que pausan más por una coma?

La medición 09 (intentos/03_lectura_sin_signos/) mostró que el punto dentro del texto pausa ~860 ms y la coma, los dos puntos y el punto y coma
entre 240 y 310 ms. Compara, a velocidad normal y con la misma voz, tres versiones de cada texto:
  original      tal como se muestra en pantalla
  punto_a_coma  el punto seguido de más texto se lee como coma
  todo_a_coma   el punto, los dos puntos y el punto y coma seguidos de más texto se leen como coma
El signo final (. ? !), los ¿ ? y los decimales (9.8) no cambian.
Los textos son los que el simulador envió a la voz en la prueba de navegador (resultados/signos_antes/).
Guarda los .mp3 en resultados/pausas_cortas/ e imprime la duración y las pausas mayores de 150 ms.
"""

import asyncio
import re
import sys
from pathlib import Path

import edge_tts

SALIDA = Path(__file__).resolve().parent.parent / "resultados" / "pausas_cortas"
TICKS_POR_MS = 10_000
TEXTOS = {
    "presentacion": ("es-MX-JorgeNeural",
                     "Martín Rojas, de 28 años, sexo masculino. Motivo de consulta: Ingresó por dolor abdominal intenso; "
                     "se diagnosticó apendicitis y se le realizó una apendicectomía de urgencia."),
    "evolucion": ("es-MX-JorgeNeural",
                  "Evolución quirúrgica: Durante la intervención presentó un sangrado masivo y persistente que requirió "
                  "transfusión de sangre."),
    "laboratorio": ("es-MX-DaliaNeural", "Hemoglobina: 9.8 g/dL. Leucocitos: 14 500, con predominio de neutrófilos."),
    "pregunta": ("es-MX-JorgeNeural", "¿Desde cuándo tiene el dolor, y hacia dónde se va?"),
}
# Un signo seguido de espacio y más texto; el punto entre dígitos (9.8) no lleva espacio y no se toca.
PUNTO = re.compile(r"\.(?=\s+\S)")
PAUSA_LARGA = re.compile(r"[.:;](?=\s+\S)")


async def medir(voz: str, texto: str, destino: Path):
    audio = bytearray()
    palabras = []
    async for chunk in edge_tts.Communicate(texto, voz, boundary="WordBoundary").stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            palabras.append((chunk["offset"] // TICKS_POR_MS, chunk["duration"] // TICKS_POR_MS, chunk["text"]))
    destino.write_bytes(audio)
    pausas, fin_anterior = [], palabras[0][0]
    for inicio, duracion, palabra in palabras:
        if inicio - fin_anterior > 150:
            pausas.append(f"{inicio - fin_anterior} ms antes de «{palabra}»")
        fin_anterior = inicio + duracion
    return (palabras[-1][0] + palabras[-1][1]) / 1000, pausas


async def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, (voz, original) in TEXTOS.items():
        print(f"=== {nombre} ({voz})")
        versiones = {
            "original": original,
            "punto_a_coma": PUNTO.sub(",", original),
            "todo_a_coma": PAUSA_LARGA.sub(",", original),
        }
        vistos = set()
        for version, texto in versiones.items():
            if texto in vistos:
                print(f"  {version:<13} igual a una versión anterior")
                continue
            vistos.add(texto)
            segundos, pausas = await medir(voz, texto, SALIDA / f"17_{nombre}_{version}.mp3")
            print(f"  {version:<13} {segundos:>5.1f} s  texto leído: {texto}")
            print(f"  {'':<13} pausas: {', '.join(pausas) if pausas else 'ninguna mayor de 150 ms'}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
