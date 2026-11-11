"""TA-024 · Latencia de la voz neuronal (edge-tts) a través de GET /api/voz.

Mide para cada frase:
  - primer trozo (TTFB): desde que se pide hasta que llega el primer byte de audio → lo que el alumno espera
                         antes de oír al personaje
  - total              : hasta recibir el mp3 completo
La primera petición incluye la importación de edge_tts y la primera conexión (arranque en frío) y se marca.

Requiere TTS_PROVIDER=edge en .env y el extra «voz» (npm run setup -- --extras voz).

Uso:
  python 03_latencia_voz.py                 # 8 frases x 3 repeticiones x 2 personajes = 48 peticiones
  python 03_latencia_voz.py --repeticiones 5
"""
from __future__ import annotations

import argparse
import sys
import time

import httpx

from comun import RESULTADOS, ahora, entorno, escribir_csv, escribir_json, resumen

FRASES = [
    "Doctor, me duele la barriga desde ayer.",
    "Sí, he tenido fiebre y escalofríos por la noche.",
    "No tomo ningún medicamento de forma habitual.",
    "El dolor empezó alrededor del ombligo y luego se fue hacia la derecha.",
    "Mi madre tiene diabetes y mi padre es hipertenso.",
    "Le comento el caso: paciente de treinta y cuatro años que acude por dolor abdominal.",
    "Los resultados del hemograma muestran leucocitosis con desviación a la izquierda.",
    "No, no he vomitado, pero sí tengo náuseas desde la mañana.",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://localhost:3000")
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--personajes", nargs="+", default=["patient", "doctor"])
    ap.add_argument("--etiqueta", default="local")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    try:
        activa = httpx.get(base + "/api/voz/estado", timeout=30).json().get("activa")
    except Exception as exc:
        sys.exit(f"No responde {base} ({type(exc).__name__}). ¿Está corriendo `npm start`?")
    if not activa:
        sys.exit("La voz neuronal está apagada: ponga TTS_PROVIDER=edge en .env, instale el extra voz y reinicie.")

    filas, orden = [], 0
    with httpx.Client(base_url=base, timeout=60) as cliente:
        for rep in range(1, args.repeticiones + 1):
            for personaje in args.personajes:
                for frase in FRASES:
                    orden += 1
                    t0 = time.perf_counter()
                    primero, total_bytes = None, 0
                    with cliente.stream("GET", "/api/voz", params={"texto": frase, "personaje": personaje}) as r:
                        status = r.status_code
                        for trozo in r.iter_bytes():
                            if primero is None and trozo:
                                primero = time.perf_counter()
                            total_bytes += len(trozo)
                    fin = time.perf_counter()
                    filas.append({"etiqueta": args.etiqueta, "orden": orden, "repeticion": rep,
                                  "personaje": personaje, "caracteres": len(frase), "status": status,
                                  "primer_trozo_ms": round((primero - t0) * 1000, 1) if primero else None,
                                  "total_ms": round((fin - t0) * 1000, 1), "bytes": total_bytes,
                                  "arranque_en_frio": orden == 1})
                    print(f"  {orden:>3} {personaje:<8} {status} primer trozo "
                          f"{filas[-1]['primer_trozo_ms']} ms · total {filas[-1]['total_ms']} ms")

    ok = [f for f in filas if f["status"] == 200]
    caliente = [f for f in ok if not f["arranque_en_frio"]]
    salida = {"fecha": ahora(), "base_url": base, "entorno_cliente": entorno(), "peticiones": len(filas),
              "ok": len(ok), "arranque_en_frio": filas[0] if filas else None,
              "primer_trozo_ms": resumen([f["primer_trozo_ms"] for f in caliente]),
              "total_ms": resumen([f["total_ms"] for f in caliente]),
              "por_personaje_primer_trozo_ms": {p: resumen([f["primer_trozo_ms"] for f in caliente
                                                            if f["personaje"] == p]) for p in args.personajes}}
    sufijo = "" if args.etiqueta == "local" else f"_{args.etiqueta}"
    escribir_csv(RESULTADOS / f"voz_latencia{sufijo}.csv", filas)
    escribir_json(RESULTADOS / f"voz_resumen{sufijo}.json", salida)
    pt = salida["primer_trozo_ms"]
    print(f"\nPrimer trozo (sin arranque en frío): p50 {pt.get('p50', 0):.0f} ms · p95 {pt.get('p95', 0):.0f} ms")
    print(f"Guardado en {RESULTADOS}")


if __name__ == "__main__":
    main()
