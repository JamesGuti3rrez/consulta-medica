"""Utilidades compartidas por los scripts de TA-024: rutas, percentiles, intervalos y escritura de resultados."""
from __future__ import annotations

import csv
import json
import math
import platform
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent.parent          # pruebas/38_ta024_metricas
RESULTADOS = CARPETA / "resultados"
GRAFICOS = CARPETA / "graficos"
RAIZ = CARPETA.parent.parent                              # raíz del repositorio
DATASET = RAIZ / "backend" / "evals" / "datasets" / "clinical_v1.json"
LIMA = timezone(timedelta(hours=-5))


def ahora() -> str:
    return datetime.now(LIMA).isoformat(timespec="seconds")


def percentil(valores, p):
    """Percentil con interpolación lineal (método 'linear' de numpy, el habitual en informes)."""
    datos = sorted(valores)
    if not datos:
        return None
    if len(datos) == 1:
        return datos[0]
    pos = (len(datos) - 1) * p / 100
    bajo, alto = math.floor(pos), math.ceil(pos)
    return datos[bajo] + (datos[alto] - datos[bajo]) * (pos - bajo)


def resumen(valores):
    """n, media, DE, mínimo, p50, p90, p95, p99 y máximo de una lista de números."""
    datos = [v for v in valores if v is not None]
    if not datos:
        return {"n": 0}
    return {"n": len(datos), "media": statistics.fmean(datos),
            "de": statistics.stdev(datos) if len(datos) > 1 else 0.0,
            "min": min(datos), "p50": percentil(datos, 50), "p90": percentil(datos, 90),
            "p95": percentil(datos, 95), "p99": percentil(datos, 99), "max": max(datos)}


def wilson(exitos, n, z=1.96):
    """Intervalo de confianza de Wilson al 95 % para una proporción."""
    if n == 0:
        return (None, None)
    p = exitos / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centro - margen), min(1.0, centro + margen))


def ic_media(valores, z=1.96):
    """IC 95 % aproximado de la media (normal); con n < 30 se usa t de Student si scipy está disponible."""
    datos = [v for v in valores if v is not None]
    if len(datos) < 2:
        return (None, None)
    media, de = statistics.fmean(datos), statistics.stdev(datos)
    try:
        from scipy import stats
        z = stats.t.ppf(0.975, len(datos) - 1)
    except ImportError:
        pass
    margen = z * de / math.sqrt(len(datos))
    return (media - margen, media + margen)


def escribir_csv(ruta: Path, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if not filas:
        ruta.write_text("", encoding="utf-8")
        return
    campos = list(dict.fromkeys(k for fila in filas for k in fila))
    with ruta.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)


def leer_csv(ruta: Path):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def escribir_json(ruta: Path, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def entorno():
    """Datos del equipo para la sección de hardware/entorno del informe."""
    info = {"fecha": ahora(), "python": platform.python_version(), "sistema": platform.platform(),
            "procesador": platform.processor() or platform.machine()}
    try:
        import os
        info["nucleos_logicos"] = os.cpu_count()
    except Exception:
        pass
    try:
        import psutil  # opcional
        info["ram_gb"] = round(psutil.virtual_memory().total / 2**30, 1)
    except ImportError:
        pass
    return info


def fmt_ms(v):
    return "—" if v is None else f"{v:,.0f}".replace(",", " ")
