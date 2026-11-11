"""TA-024 · Latencia por turno de la consulta, medida de punta a punta sobre la API real.

Para cada caso del conjunto de evaluación (backend/evals/datasets/clinical_v1.json: 10 casos, 10 preguntas
cada uno, de 10 escenarios distintos) abre una consulta de invitado y envía sus preguntas en orden, como lo
haría un alumno. Mide:
  - inicio de consulta  : POST /api/ai/sessions
  - turno               : POST /api/ai/sessions/{id}/message (enrutador + política + RAG + LLM + guardia)

El servidor debe estar corriendo (npm start). Se guarda cada medición en resultados/latencia_turnos.csv y el
resumen (p50/p90/p95/p99) en resultados/latencia_resumen.json.

Uso:
  python 01_latencia_turnos.py                          # 1 repetición de los 10 casos = 100 turnos
  python 01_latencia_turnos.py --repeticiones 3         # 300 turnos
  python 01_latencia_turnos.py --base-url https://<tu-app>.vercel.app --etiqueta vercel
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict

import httpx

from comun import DATASET, RESULTADOS, ahora, entorno, escribir_csv, escribir_json, fmt_ms, resumen


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://localhost:3000")
    ap.add_argument("--repeticiones", type=int, default=1, help="veces que se recorre cada caso")
    ap.add_argument("--casos", nargs="*", help="limitar a estos case_id (por defecto, los 10 del conjunto)")
    ap.add_argument("--pausa", type=float, default=0.0, help="segundos entre turnos (evita el límite de Groq)")
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--etiqueta", default="local", help="nombre del entorno medido (local, vercel...)")
    args = ap.parse_args()

    preguntas = json.loads(DATASET.read_text(encoding="utf-8"))
    por_caso = defaultdict(list)
    for p in preguntas:
        por_caso[p["case_id"]].append(p)
    casos = args.casos or sorted(por_caso)

    cliente = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=args.timeout)
    try:
        estado = cliente.get("/api/ai/status").json()
    except Exception as exc:
        sys.exit(f"No responde {args.base_url} ({type(exc).__name__}). ¿Está corriendo `npm start`?")
    print(f"Servidor: llm_mode={estado.get('llm_mode')} · recuperación={estado.get('retrieval_mode')} · "
          f"sesiones={estado.get('session_store')}")
    if estado.get("llm_mode") != "groq-pool":
        print("AVISO: el LLM está en modo local (sin GROQ_API_KEYS); la latencia no incluye al modelo.")

    filas, orden = [], 0
    for rep in range(1, args.repeticiones + 1):
        for caso in casos:
            t0 = time.perf_counter()
            r = cliente.post("/api/ai/sessions", json={"case_id": caso})
            ms = (time.perf_counter() - t0) * 1000
            orden += 1
            filas.append({"etiqueta": args.etiqueta, "repeticion": rep, "orden": orden, "tipo": "inicio_sesion",
                          "case_id": caso, "escenario": "", "status": r.status_code, "latencia_ms": round(ms, 1),
                          "agente": "", "proveedor": "", "bloqueado": "", "caracteres_respuesta": ""})
            if r.status_code != 200:
                print(f"  {caso}: no se pudo abrir la consulta (HTTP {r.status_code})")
                continue
            datos = r.json()
            sid = datos["session"]["session_id"] if "session" in datos else datos["session_id"]
            cabeceras = {"X-Session-Token": datos.get("session_token", "")}
            for p in por_caso[caso]:
                if args.pausa:
                    time.sleep(args.pausa)
                t0 = time.perf_counter()
                try:
                    r = cliente.post(f"/api/ai/sessions/{sid}/message", json={"message": p["query"]},
                                     headers=cabeceras)
                    status = r.status_code
                except httpx.TimeoutException:
                    status, r = 0, None
                ms = (time.perf_counter() - t0) * 1000
                cuerpo = r.json() if r is not None and status == 200 else {}
                orden += 1
                filas.append({"etiqueta": args.etiqueta, "repeticion": rep, "orden": orden, "tipo": "turno",
                              "case_id": caso, "escenario": p["scenario"], "status": status,
                              "latencia_ms": round(ms, 1), "agente": cuerpo.get("agent", ""),
                              "proveedor": cuerpo.get("provider") or "", "bloqueado": cuerpo.get("blocked", ""),
                              "caracteres_respuesta": len(cuerpo.get("response") or "")})
                print(f"  [{rep}] {p['test_id']:<28} {status} {ms:8.0f} ms  {cuerpo.get('agent', '')}")

    turnos = [f for f in filas if f["tipo"] == "turno"]
    ok = [f["latencia_ms"] for f in turnos if f["status"] == 200]
    # El primer turno de la corrida carga modelos de embeddings y conexiones: se informa aparte.
    sin_primero = [f["latencia_ms"] for f in turnos[1:] if f["status"] == 200]
    por_agente = defaultdict(list)
    for f in turnos:
        if f["status"] == 200:
            por_agente[f["agente"]].append(f["latencia_ms"])
    salida = {"fecha": ahora(), "base_url": args.base_url, "etiqueta": args.etiqueta, "servidor": estado,
              "entorno_cliente": entorno(), "repeticiones": args.repeticiones, "casos": casos,
              "turnos_enviados": len(turnos), "turnos_ok": len(ok),
              "errores_por_status": {str(s): sum(f["status"] == s for f in turnos)
                                     for s in sorted({f["status"] for f in turnos}) if s != 200},
              "inicio_sesion_ms": resumen([f["latencia_ms"] for f in filas
                                           if f["tipo"] == "inicio_sesion" and f["status"] == 200]),
              "turno_ms": resumen(ok), "turno_sin_primero_ms": resumen(sin_primero),
              "turno_por_agente_ms": {k: resumen(v) for k, v in sorted(por_agente.items())}}
    sufijo = "" if args.etiqueta == "local" else f"_{args.etiqueta}"
    escribir_csv(RESULTADOS / f"latencia_turnos{sufijo}.csv", filas)
    escribir_json(RESULTADOS / f"latencia_resumen{sufijo}.json", salida)
    t = salida["turno_ms"]
    print(f"\nTurnos OK {len(ok)}/{len(turnos)} · p50 {fmt_ms(t.get('p50'))} ms · p90 {fmt_ms(t.get('p90'))} ms · "
          f"p95 {fmt_ms(t.get('p95'))} ms · p99 {fmt_ms(t.get('p99'))} ms")
    print(f"Guardado en {RESULTADOS}")


if __name__ == "__main__":
    main()
