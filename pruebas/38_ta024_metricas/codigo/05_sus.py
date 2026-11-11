"""TA-024 · Usabilidad percibida con la escala SUS (System Usability Scale, Brooke 1996).

Cada participante responde 10 afirmaciones de 1 (totalmente en desacuerdo) a 5 (totalmente de acuerdo). El
cuestionario en español está en datos/cuestionario_sus.md. Las respuestas se anotan en datos/sus_respuestas.csv
(una fila por participante: participante,rol,p1,...,p10).

Puntaje por participante = 2,5 × [ Σ(impares − 1) + Σ(5 − pares) ]   → 0 a 100
Interpretación (Bangor, Kortum y Miller 2009; Sauro 2011): 68 = promedio; ≥ 70 aceptable; ≥ 80,3 = «A».

Uso:
  python 05_sus.py                                  # lee datos/sus_respuestas.csv
  python 05_sus.py --archivo otra_ruta.csv
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

from comun import CARPETA, RESULTADOS, ahora, escribir_csv, escribir_json, ic_media, leer_csv


def adjetivo(p):
    for limite, nombre in ((85.5, "Excelente"), (72.6, "Bueno"), (52.0, "Aceptable (OK)"), (39.2, "Pobre")):
        if p >= limite:
            return nombre
    return "Muy pobre"


def nota(p):
    for limite, letra in ((80.3, "A"), (68.0, "B/C"), (51.0, "D")):
        if p >= limite:
            return letra
    return "F"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archivo", type=Path, default=CARPETA / "datos" / "sus_respuestas.csv")
    args = ap.parse_args()
    filas = [f for f in leer_csv(args.archivo) if f.get("participante") and not f["participante"].startswith("#")]
    if not filas:
        sys.exit(f"Sin respuestas en {args.archivo}")
    puntajes = []
    for f in filas:
        try:
            r = [int(f[f"p{i}"]) for i in range(1, 11)]
        except (KeyError, ValueError):
            sys.exit(f"Fila incompleta o no numérica: {f}")
        if any(v < 1 or v > 5 for v in r):
            sys.exit(f"Valores fuera de 1-5 en el participante {f['participante']}")
        impares = sum(r[i] - 1 for i in range(0, 10, 2))
        pares = sum(5 - r[i] for i in range(1, 10, 2))
        p = 2.5 * (impares + pares)
        puntajes.append({"participante": f["participante"], "rol": f.get("rol", ""), **{f"p{i+1}": r[i] for i in range(10)},
                         "sus": p, "adjetivo": adjetivo(p), "nota": nota(p)})
    valores = [p["sus"] for p in puntajes]
    bajo, alto = ic_media(valores)
    resumen = {"fecha": ahora(), "n": len(valores), "media": statistics.fmean(valores),
               "de": statistics.stdev(valores) if len(valores) > 1 else 0.0,
               "mediana": statistics.median(valores), "min": min(valores), "max": max(valores),
               "ic95": [bajo, alto], "adjetivo_media": adjetivo(statistics.fmean(valores)),
               "nota_media": nota(statistics.fmean(valores)),
               "sobre_68": sum(v >= 68 for v in valores),
               "por_rol": {rol: statistics.fmean([p["sus"] for p in puntajes if p["rol"] == rol])
                           for rol in sorted({p["rol"] for p in puntajes})},
               "media_por_item": {f"p{i}": statistics.fmean(int(f[f"p{i}"]) for f in filas) for i in range(1, 11)}}
    escribir_csv(RESULTADOS / "sus_puntajes.csv", puntajes)
    escribir_json(RESULTADOS / "sus_resumen.json", resumen)
    ic = f"IC95 {bajo:.1f}–{alto:.1f}" if bajo is not None else "IC95 n/d (n<2)"
    print(f"SUS n={resumen['n']}: media {resumen['media']:.1f} ± {resumen['de']:.1f} ({ic}) → "
          f"{resumen['adjetivo_media']}, nota {resumen['nota_media']}; {resumen['sobre_68']} de {resumen['n']} sobre 68")


if __name__ == "__main__":
    main()
