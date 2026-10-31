"""¿Cuánto se acortan las pausas si la voz lee el texto sin signos de puntuación?

Compara, a velocidad normal y con la misma voz, tres versiones de cada texto:
  original     tal como se muestra en pantalla
  sin_signos   sin ningún signo de puntuación
  con_pregunta sin signos, pero conservando ¿ ? (entonación de pregunta)
Los decimales (9.8) se conservan: el punto entre dígitos no se quita.
Guarda los .mp3 en resultados/sin_puntuacion/ e imprime la duración y las pausas mayores de 150 ms.
"""

import asyncio
import re
import sys
from pathlib import Path

import edge_tts

SALIDA = Path(__file__).resolve().parent.parent / "resultados" / "sin_puntuacion"
TICKS_POR_MS = 10_000
TEXTOS = {
    "presentacion": ("es-MX-JorgeNeural",
                     "Martín Rojas, de 28 años, sexo masculino. Motivo de consulta: ingresó por dolor abdominal intenso; "
                     "se diagnosticó apendicitis y se le realizó una apendicectomía de urgencia."),
    "laboratorio": ("es-MX-DaliaNeural", "Hemoglobina: 9.8 g/dL. Leucocitos: 14 500, con predominio de neutrófilos."),
    "pregunta": ("es-MX-JorgeNeural", "¿Desde cuándo tiene el dolor, y hacia dónde se va?"),
}
# Signos que se quitan; el punto y la coma entre dígitos se respetan.
SIGNOS = re.compile(r"(?<!\d)[.,](?!\d)|[.,](?=\s|$)|[;:¡!«»\"()…—–-]")


def sin_signos(texto: str, preguntas: bool) -> str:
    limpio = SIGNOS.sub(" ", texto)
    if not preguntas:
        limpio = limpio.replace("¿", " ").replace("?", " ")
    return re.sub(r"\s+", " ", limpio).strip()


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
            "sin_signos": sin_signos(original, preguntas=False),
            "con_pregunta": sin_signos(original, preguntas=True),
        }
        for version, texto in versiones.items():
            if version == "con_pregunta" and texto == versiones["sin_signos"]:
                continue
            segundos, pausas = await medir(voz, texto, SALIDA / f"09_{nombre}_{version}.mp3")
            print(f"  {version:<13} {segundos:>5.1f} s  texto leído: {texto}")
            print(f"  {'':<13} pausas: {', '.join(pausas) if pausas else 'ninguna mayor de 150 ms'}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
