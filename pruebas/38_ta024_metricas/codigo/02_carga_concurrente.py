"""TA-024 · Throughput y latencia bajo carga: varios alumnos simulados conversando al mismo tiempo.

Para cada nivel de concurrencia c (por defecto 1, 2, 4 y 8) lanza c «alumnos» en paralelo. Cada alumno abre su
propia consulta de invitado y envía --turnos preguntas del conjunto de evaluación de su caso. Se mide:
  - throughput     = turnos respondidos con 200 / segundos de la ronda (turnos por segundo y por minuto)
  - latencia       = p50 / p95 / p99 de cada turno en esa ronda
  - tasa de error  = turnos con status distinto de 200 (429/503 del proveedor, timeouts...)

Resultados: resultados/carga_peticiones.csv (cada turno) y resultados/carga_resumen.csv (una fila por nivel).

Ojo con el plan gratuito de Groq: con 8 alumnos en paralelo es normal ver 429/503; eso también es un resultado
(el gateway rota claves y luego avisa). Use --pausa-rondas para dejar enfriar el proveedor entre niveles.

Uso:
  python 02_carga_concurrente.py
  python 02_carga_concurrente.py --concurrencias 1 2 4 8 16 --turnos 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict

import httpx

from comun import DATASET, RESULTADOS, ahora, entorno, escribir_csv, escribir_json, resumen, wilson


async def alumno(cliente, nivel, idx, caso, preguntas, turnos, registros):
    r = await cliente.post("/api/ai/sessions", json={"case_id": caso})
    if r.status_code != 200:
        registros.append({"concurrencia": nivel, "alumno": idx, "case_id": caso, "turno": 0,
                          "status": r.status_code, "latencia_ms": None, "t_inicio": None, "t_fin": None})
        return
    datos = r.json()
    sid = datos["session"]["session_id"] if "session" in datos else datos["session_id"]
    cab = {"X-Session-Token": datos.get("session_token", "")}
    for n, p in enumerate(preguntas[:turnos], 1):
        t0 = time.perf_counter()
        try:
            r = await cliente.post(f"/api/ai/sessions/{sid}/message", json={"message": p["query"]}, headers=cab)
            status = r.status_code
        except httpx.TimeoutException:
            status = 0
        except httpx.HTTPError:
            status = -1
        t1 = time.perf_counter()
        registros.append({"concurrencia": nivel, "alumno": idx, "case_id": caso, "turno": n, "status": status,
                          "latencia_ms": round((t1 - t0) * 1000, 1), "t_inicio": t0, "t_fin": t1})


async def ronda(base_url, nivel, turnos, por_caso, timeout):
    casos = sorted(por_caso)
    registros = []
    limites = httpx.Limits(max_connections=nivel * 2, max_keepalive_connections=nivel * 2)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, limits=limites) as cliente:
        inicio = time.perf_counter()
        await asyncio.gather(*(alumno(cliente, nivel, i, casos[i % len(casos)], por_caso[casos[i % len(casos)]],
                                      turnos, registros) for i in range(nivel)))
        duracion = time.perf_counter() - inicio
    return registros, duracion


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://localhost:3000")
    ap.add_argument("--concurrencias", type=int, nargs="+", default=[1, 2, 4, 8])
    ap.add_argument("--turnos", type=int, default=5, help="turnos que envía cada alumno por ronda")
    ap.add_argument("--pausa-rondas", type=float, default=20.0, help="segundos de espera entre niveles")
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--etiqueta", default="local")
    args = ap.parse_args()

    por_caso = defaultdict(list)
    for p in json.loads(DATASET.read_text(encoding="utf-8")):
        por_caso[p["case_id"]].append(p)
    base = args.base_url.rstrip("/")
    try:
        estado = httpx.get(base + "/api/ai/status", timeout=args.timeout).json()
    except Exception as exc:
        sys.exit(f"No responde {base} ({type(exc).__name__}). ¿Está corriendo `npm start`?")

    todas, resumenes = [], []
    for i, nivel in enumerate(args.concurrencias):
        if i and args.pausa_rondas:
            print(f"  esperando {args.pausa_rondas:.0f} s antes del siguiente nivel...")
            time.sleep(args.pausa_rondas)
        registros, duracion = asyncio.run(ronda(base, nivel, args.turnos, por_caso, args.timeout))
        turnos = [r for r in registros if r["turno"] > 0]
        ok = [r for r in turnos if r["status"] == 200]
        enviados = nivel * args.turnos
        errores = enviados - len(ok)
        lat = resumen([r["latencia_ms"] for r in ok])
        bajo, alto = wilson(errores, enviados)
        fila = {"etiqueta": args.etiqueta, "concurrencia": nivel, "turnos_enviados": enviados,
                "turnos_ok": len(ok), "errores": errores, "tasa_error": errores / enviados if enviados else None,
                "tasa_error_ic95_bajo": bajo, "tasa_error_ic95_alto": alto,
                "duracion_s": round(duracion, 2),
                "throughput_turnos_s": round(len(ok) / duracion, 4) if duracion else None,
                "throughput_turnos_min": round(60 * len(ok) / duracion, 2) if duracion else None,
                **{f"lat_{k}_ms": round(v, 1) for k, v in lat.items() if k != "n"},
                "status": json.dumps({str(s): sum(r["status"] == s for r in turnos)
                                      for s in sorted({r["status"] for r in turnos})})}
        resumenes.append(fila)
        t0 = min((r["t_inicio"] for r in turnos if r["t_inicio"]), default=0)
        for r in registros:
            todas.append({**r, "etiqueta": args.etiqueta,
                          "t_inicio": round(r["t_inicio"] - t0, 3) if r["t_inicio"] else None,
                          "t_fin": round(r["t_fin"] - t0, 3) if r["t_fin"] else None})
        print(f"c={nivel:>2}: {len(ok)}/{enviados} OK en {duracion:6.1f} s · "
              f"{fila['throughput_turnos_min']} turnos/min · p50 {lat.get('p50', 0):.0f} ms · "
              f"p95 {lat.get('p95', 0):.0f} ms · errores {errores}")

    sufijo = "" if args.etiqueta == "local" else f"_{args.etiqueta}"
    escribir_csv(RESULTADOS / f"carga_peticiones{sufijo}.csv", todas)
    escribir_csv(RESULTADOS / f"carga_resumen{sufijo}.csv", resumenes)
    escribir_json(RESULTADOS / f"carga_meta{sufijo}.json", {"fecha": ahora(), "base_url": base, "servidor": estado,
                                                            "entorno_cliente": entorno(), "turnos": args.turnos,
                                                            "concurrencias": args.concurrencias})
    print(f"Guardado en {RESULTADOS}")


if __name__ == "__main__":
    main()
