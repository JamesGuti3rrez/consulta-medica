"""SP-006, prueba mínima de voz: mide en este equipo lo que la matriz comparativa necesita.

1. Caracteres que el doctor lee al presentar cada caso (cuánto gasta una consulta del cupo gratuito de Azure).
2. Voces en español de edge-tts: si están las seis que usa el simulador y cuántas hay de Perú y México.
3. Latencia de edge-tts con las voces del simulador: tiempo hasta el primer trozo de audio y hasta el final.
4. Azure AI Speech: si hay clave configurada (todavía no: falta la autorización de GitHub Student).

Uso (desde la raíz):  backend/.venv/Scripts/python.exe pruebas/36_sp006_voz_y_avatar/medir_voz.py <salida.json>
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update({"CASE_STORE": "local", "SESSION_STORE": "memoria", "LANGSMITH_TRACING": "false"})

import edge_tts  # noqa: E402

from server.api.routes import load_curated_cases, to_student_case  # noqa: E402
from server.voice import tts  # noqa: E402

REPETICIONES = 5
FRASES = {
    "corta": "No hay alergias documentadas en la ficha.",
    "larga": "Evolución quirúrgica: Durante la intervención presentó un sangrado masivo y persistente que requirió "
    "transfusión de sangre.",
}
# Las tres voces que más suenan: doctor con paciente hombre, paciente hombre y paciente mujer.
VOCES = {
    "doctor (paciente hombre)": tts.choose_voice("doctor", "masculino"),
    "paciente hombre": tts.choose_voice("patient", "masculino"),
    "paciente mujer": tts.choose_voice("patient", "femenino"),
}


def presentation_text(case: dict) -> str:
    """El mismo texto que lee el doctor en presentCase() de frontend/public/js/simulacion.js."""
    patient = case["patient"]
    parts = [f"{patient['alias']}, de {patient['age_years']} años, sexo {patient['sex']}. "
             f"Motivo de consulta: {case['chief_complaint']['text']}"]
    parts += [f"{item['label']}: {item['text']}" for item in case["items"]]
    parts.append(f"Alergias registradas: {', '.join(case['allergies'])}." if case["allergies_recorded"]
                 else "No hay alergias documentadas en la ficha.")
    parts.append("Doctor, puede comenzar con el interrogatorio.")
    return " ".join(parts)


async def synthesize(text: str, voice: str) -> tuple[float, float, int]:
    start = time.perf_counter()
    first = None
    size = 0
    async for chunk in edge_tts.Communicate(text, voice).stream():
        if chunk["type"] == "audio":
            first = first or time.perf_counter() - start
            size += len(chunk["data"])
    return first, time.perf_counter() - start, size


async def main(output: Path) -> None:
    result: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "edge_tts_version": edge_tts.__version__}

    print("1. Caracteres de la presentación de cada caso")
    lengths = sorted(len(presentation_text(to_student_case(case))) for case in load_curated_cases())
    result["presentacion_caracteres"] = {"casos": len(lengths), "minimo": lengths[0], "mediana": statistics.median(lengths),
                                         "maximo": lengths[-1], "total": sum(lengths)}
    print(f"   {len(lengths)} casos: mínimo {lengths[0]}, mediana {statistics.median(lengths):.0f}, máximo {lengths[-1]}")

    print("\n2. Voces en español de edge-tts")
    voices = await edge_tts.list_voices()
    names = {voice["ShortName"]: voice["Gender"] for voice in voices}
    spanish = [name for name in names if name.startswith("es-")]
    result["voces"] = {
        "espanol": len(spanish),
        "peru": sorted(name for name in spanish if name.startswith("es-PE")),
        "mexico": sorted(name for name in spanish if name.startswith("es-MX")),
        "del_simulador": {voice: names.get(voice, "NO DISPONIBLE") for voice in sorted(tts.VOICES)},
    }
    print(f"   {len(spanish)} voces en español; Perú: {', '.join(result['voces']['peru'])}")
    print(f"   México: {', '.join(result['voces']['mexico'])}")
    for voice, gender in result["voces"]["del_simulador"].items():
        print(f"   simulador: {voice:<24} {gender}")

    print(f"\n3. Latencia de edge-tts ({REPETICIONES} repeticiones por voz y frase)")
    result["latencia"] = []
    for role, voice in VOCES.items():
        for kind, text in FRASES.items():
            runs = [await synthesize(text, voice) for _ in range(REPETICIONES)]
            firsts = [run[0] for run in runs]
            totals = [run[1] for run in runs]
            row = {"personaje": role, "voz": voice, "frase": kind, "caracteres": len(text),
                   "primer_trozo_s": {"min": min(firsts), "mediana": statistics.median(firsts), "max": max(firsts)},
                   "total_s": {"min": min(totals), "mediana": statistics.median(totals), "max": max(totals)},
                   "bytes_mp3": runs[0][2]}
            result["latencia"].append(row)
            print(f"   {role:<26} {kind:<6} primer trozo {min(firsts):.2f}-{max(firsts):.2f} s "
                  f"(mediana {statistics.median(firsts):.2f}), total mediana {statistics.median(totals):.2f} s")

    print("\n4. Azure AI Speech")
    configured = bool(os.getenv("AZURE_SPEECH_KEY") or (ROOT / ".env").read_text(encoding="utf-8").count("AZURE_SPEECH_KEY="))
    result["azure"] = {"clave_configurada": configured}
    print("   clave configurada" if configured else "   sin clave: falta la autorización de GitHub Student (no se puede medir)")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultado en {output.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "pruebas/36_sp006_voz_y_avatar/resultados/voz.json").resolve()))
