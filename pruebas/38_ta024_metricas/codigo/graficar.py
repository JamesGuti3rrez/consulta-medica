"""TA-024 · Genera los gráficos (graficos/*.png) y el resumen en tablas (resultados/resumen_metricas.md).

Lee lo que haya en resultados/; cada gráfico se omite si su medición todavía no se ha ejecutado.

Uso:
  python graficar.py
  python graficar.py --rag ../../../backend/evals/results/20261110-153000     # otra corrida de TA-023
  python graficar.py --etiqueta vercel                                         # archivos *_vercel
"""
from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ta024-matplotlib"))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from comun import GRAFICOS, RESULTADOS, ahora, fmt_ms, leer_csv, percentil, resumen, wilson  # noqa: E402

# Paleta categórica validada (orden fijo) y tinta de texto.
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
TINTA, TINTA2, REJILLA, FONDO = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SECUENCIAL = ["#c6dbf5", "#7fb0ea", "#2a78d6", "#174a8c"]  # una sola tonalidad, claro → oscuro

plt.rcParams.update({
    "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 10,
    "axes.edgecolor": REJILLA, "axes.labelcolor": TINTA2, "axes.titlecolor": TINTA,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": REJILLA, "grid.linewidth": 0.8,
    "xtick.color": TINTA2, "ytick.color": TINTA2, "legend.frameon": False,
    "lines.linewidth": 2,
})

NOMBRES_AGENTE = {"paciente": "Paciente", "medico_asistente": "Médico asistente", "laboratorio": "Laboratorio",
                  "radiologia": "Radiología", "especialista": "Especialista"}
NOMBRES_ESCENARIO = {"patient": "Pregunta al paciente", "examination": "Examen físico", "study": "Estudio",
                     "multiple": "Pedido múltiple", "ambiguous": "Ambigua", "absent": "Dato ausente",
                     "protected": "Dato protegido", "cross_case": "Otro caso", "public_context": "Contexto público",
                     "wrong_permission": "Rol equivocado"}
generados, md = [], []


def guardar(fig, nombre, nota=None):
    if nota:
        fig.text(0.01, -0.02, nota, fontsize=8, color=TINTA2, ha="left", va="top", transform=fig.transFigure)
    GRAFICOS.mkdir(parents=True, exist_ok=True)
    ruta = GRAFICOS / nombre
    fig.savefig(ruta, dpi=160, bbox_inches="tight")
    plt.close(fig)
    generados.append(nombre)
    print("  ✓", nombre)


def num(v):
    try:
        x = float(v)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def tabla(cabecera, filas):
    md.append("| " + " | ".join(cabecera) + " |")
    md.append("|" + "|".join("---" if i == 0 else "---:" for i in range(len(cabecera))) + "|")
    md.extend("| " + " | ".join(str(c) for c in f) + " |" for f in filas)
    md.append("")


def boxplot_h(ax, grupos, color):
    etiquetas = list(grupos)
    datos = [grupos[k] for k in etiquetas]
    bp = ax.boxplot(datos, orientation="horizontal", patch_artist=True, widths=0.5, showfliers=True,
                    medianprops={"color": TINTA, "linewidth": 2},
                    boxprops={"facecolor": color + "55", "edgecolor": color},
                    whiskerprops={"color": color}, capprops={"color": color},
                    flierprops={"marker": "o", "markersize": 4, "markerfacecolor": color, "markeredgecolor": FONDO})
    ax.set_yticks(range(1, len(etiquetas) + 1), [f"{e}  (n={len(grupos[e])})" for e in etiquetas])
    ax.grid(axis="y", visible=False)
    return bp


# ---------------------------------------------------------------- latencia por turno
def latencia(suf):
    ruta = RESULTADOS / f"latencia_turnos{suf}.csv"
    if not ruta.exists():
        return None
    filas = leer_csv(ruta)
    turnos = [f for f in filas if f["tipo"] == "turno" and f["status"] == "200"]
    lat = [float(f["latencia_ms"]) for f in turnos]
    if not lat:
        return None
    inicio = [float(f["latencia_ms"]) for f in filas if f["tipo"] == "inicio_sesion" and f["status"] == "200"]
    meta = json.loads((RESULTADOS / f"latencia_resumen{suf}.json").read_text(encoding="utf-8"))
    srv = meta.get("servidor", {})
    nota = (f"Fuente: 01_latencia_turnos.py · {meta['fecha'][:16]} · LLM {srv.get('llm_mode')} · "
            f"recuperación {srv.get('retrieval_mode')} · {meta['base_url']}")

    # G01 distribución
    r = resumen(lat)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.hist([v / 1000 for v in lat], bins=min(30, max(8, len(lat) // 4)), color=S1, edgecolor=FONDO, linewidth=1)
    for p, estilo in (("p50", "-"), ("p90", "--"), ("p99", ":")):
        ax.axvline(r[p] / 1000, color=TINTA, linestyle=estilo, linewidth=1.2)
        ax.text(r[p] / 1000, ax.get_ylim()[1] * 0.97, f" {p} {r[p] / 1000:.2f} s", color=TINTA, fontsize=9, va="top")
    ax.set_title(f"Latencia por turno de la consulta (n = {len(lat)} turnos)")
    ax.set_xlabel("Segundos por turno (petición → respuesta)")
    ax.set_ylabel("Turnos")
    ax.grid(axis="x", visible=False)
    guardar(fig, f"G01_latencia_turno_distribucion{suf}.png", nota)

    # G02 por agente
    por_agente = defaultdict(list)
    for f in turnos:
        por_agente[NOMBRES_AGENTE.get(f["agente"], f["agente"] or "—")].append(float(f["latencia_ms"]) / 1000)
    por_agente = dict(sorted(por_agente.items(), key=lambda kv: percentil(kv[1], 50)))
    fig, ax = plt.subplots(figsize=(9, 0.6 * len(por_agente) + 1.6))
    boxplot_h(ax, por_agente, S1)
    ax.set_title("Latencia por turno según el agente que responde")
    ax.set_xlabel("Segundos por turno")
    guardar(fig, f"G02_latencia_por_agente{suf}.png", nota)

    # G03 por escenario
    por_esc = defaultdict(list)
    for f in turnos:
        por_esc[NOMBRES_ESCENARIO.get(f["escenario"], f["escenario"])].append(float(f["latencia_ms"]) / 1000)
    por_esc = dict(sorted(por_esc.items(), key=lambda kv: percentil(kv[1], 50)))
    fig, ax = plt.subplots(figsize=(9, 0.5 * len(por_esc) + 1.6))
    boxplot_h(ax, por_esc, S1)
    ax.set_title("Latencia por turno según el tipo de pregunta")
    ax.set_xlabel("Segundos por turno")
    guardar(fig, f"G03_latencia_por_escenario{suf}.png", nota)

    # G04 latencia por orden del turno (estabilidad a lo largo de la corrida)
    fig, ax = plt.subplots(figsize=(9, 4))
    xs = list(range(1, len(lat) + 1))
    ax.plot(xs, [v / 1000 for v in lat], color=S1, linewidth=1.2, marker="o", markersize=3)
    ax.axhline(r["p50"] / 1000, color=TINTA2, linestyle="--", linewidth=1)
    ax.text(len(lat), r["p50"] / 1000, f"p50 {r['p50'] / 1000:.2f} s ", ha="right", va="bottom", color=TINTA2, fontsize=9)
    ax.set_title("Latencia de cada turno en el orden en que se envió")
    ax.set_xlabel("Turno n.º")
    ax.set_ylabel("Segundos")
    guardar(fig, f"G04_latencia_secuencia{suf}.png", nota)

    md.append(f"## Latencia por turno ({meta['base_url']})\n")
    md.append(f"Fecha {meta['fecha']}. LLM `{srv.get('llm_mode')}`, recuperación `{srv.get('retrieval_mode')}`, "
              f"sesiones `{srv.get('session_store')}`. Turnos OK {meta['turnos_ok']} de {meta['turnos_enviados']}; "
              f"errores {meta.get('errores_por_status') or 'ninguno'}.\n")
    filas_t = []
    for nombre, clave in (("Inicio de consulta", "inicio_sesion_ms"), ("Turno (todos)", "turno_ms"),
                          ("Turno (sin el primero, en caliente)", "turno_sin_primero_ms")):
        s = meta[clave]
        if s.get("n"):
            filas_t.append([nombre, s["n"], fmt_ms(s["media"]), fmt_ms(s["de"]), fmt_ms(s["p50"]), fmt_ms(s["p90"]),
                            fmt_ms(s["p95"]), fmt_ms(s["p99"]), fmt_ms(s["max"])])
    for ag, s in meta["turno_por_agente_ms"].items():
        filas_t.append([f"Turno · {NOMBRES_AGENTE.get(ag, ag)}", s["n"], fmt_ms(s["media"]), fmt_ms(s["de"]),
                        fmt_ms(s["p50"]), fmt_ms(s["p90"]), fmt_ms(s["p95"]), fmt_ms(s["p99"]), fmt_ms(s["max"])])
    tabla(["Medición (ms)", "n", "Media", "DE", "p50", "p90", "p95", "p99", "Máx."], filas_t)
    return {"inicio": inicio, "turno": lat}


# ---------------------------------------------------------------- voz
def voz(suf):
    ruta = RESULTADOS / f"voz_latencia{suf}.csv"
    if not ruta.exists():
        return None
    filas = [f for f in leer_csv(ruta) if f["status"] == "200" and f["arranque_en_frio"] != "True"]
    if not filas:
        return None
    meta = json.loads((RESULTADOS / f"voz_resumen{suf}.json").read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for color, personaje in zip((S1, S2, S3), sorted({f["personaje"] for f in filas})):
        v = sorted(float(f["primer_trozo_ms"]) / 1000 for f in filas if f["personaje"] == personaje)
        ax.step(v, [(i + 1) / len(v) for i in range(len(v))], where="post", color=color,
                label={"patient": "Paciente", "doctor": "Doctor"}.get(personaje, personaje))
    ax.axvline(1.0, color=TINTA2, linestyle=":", linewidth=1)
    ax.text(1.0, 0.03, " 1 s", color=TINTA2, fontsize=9)
    ax.set_ylim(0, 1.02)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("Voz neuronal: tiempo hasta el primer trozo de audio (distribución acumulada)")
    ax.set_xlabel("Segundos hasta oír el inicio de la frase")
    ax.set_ylabel("Frases ya sonando")
    ax.legend(loc="lower right")
    frio = meta.get("arranque_en_frio") or {}
    guardar(fig, f"G07_voz_primer_trozo{suf}.png",
            f"Fuente: 03_latencia_voz.py · {meta['fecha'][:16]} · sin el arranque en frío "
            f"({frio.get('primer_trozo_ms')} ms, se informa aparte)")
    pt, tt = meta["primer_trozo_ms"], meta["total_ms"]
    md.append("## Voz neuronal (edge-tts por /api/voz)\n")
    md.append(f"Arranque en frío (primera frase): primer trozo {frio.get('primer_trozo_ms')} ms, "
              f"total {frio.get('total_ms')} ms.\n")
    tabla(["Medición (ms)", "n", "Media", "p50", "p90", "p95", "p99", "Máx."],
          [[n, s["n"], fmt_ms(s["media"]), fmt_ms(s["p50"]), fmt_ms(s["p90"]), fmt_ms(s["p95"]), fmt_ms(s["p99"]),
            fmt_ms(s["max"])] for n, s in (("Primer trozo", pt), ("Audio completo", tt))])
    return {"primer": [float(f["primer_trozo_ms"]) for f in filas], "total": [float(f["total_ms"]) for f in filas]}


def percentiles_juntos(lat, vz, suf):
    grupos = {}
    if lat:
        if lat["inicio"]:
            grupos["Inicio de consulta"] = lat["inicio"]
        grupos["Turno de conversación"] = lat["turno"]
    if vz:
        grupos["Voz · primer trozo"] = vz["primer"]
        grupos["Voz · audio completo"] = vz["total"]
    if not grupos:
        return
    fig, ax = plt.subplots(figsize=(9, 0.9 * len(grupos) + 1.6))
    alto = 0.26
    for j, (p, color) in enumerate((("p50", S1), ("p95", S2), ("p99", S3))):
        for i, (nombre, v) in enumerate(grupos.items()):
            valor = percentil(v, int(p[1:])) / 1000
            y = i + (j - 1) * alto
            ax.barh(y, valor, height=alto - 0.04, color=color, label=p if i == 0 else None)
            ax.text(valor, y, f" {valor:.2f}", va="center", fontsize=8, color=TINTA)
    ax.set_yticks(range(len(grupos)), list(grupos))
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Segundos")
    ax.set_title("Percentiles de latencia por operación")
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1.0), ncols=3, fontsize=8)
    guardar(fig, f"G05_percentiles_por_operacion{suf}.png", "Fuente: 01_latencia_turnos.py y 03_latencia_voz.py")


# ---------------------------------------------------------------- carga
def carga(suf):
    ruta = RESULTADOS / f"carga_resumen{suf}.csv"
    if not ruta.exists():
        return
    filas = leer_csv(ruta)
    c = [int(f["concurrencia"]) for f in filas]
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(14, 4.2))
    a1.plot(c, [num(f["throughput_turnos_min"]) for f in filas], color=S1, marker="o", markersize=7)
    for x, f in zip(c, filas):
        a1.annotate(f"{num(f['throughput_turnos_min']):.1f}", (x, num(f["throughput_turnos_min"])),
                    textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8, color=TINTA)
    a1.set_title("Throughput")
    a1.set_ylabel("Turnos respondidos por minuto")
    for clave, color, nombre in (("lat_p50_ms", S1, "p50"), ("lat_p95_ms", S2, "p95")):
        a2.plot(c, [(num(f.get(clave)) or 0) / 1000 for f in filas], color=color, marker="o", markersize=7, label=nombre)
    a2.set_title("Latencia por turno bajo carga")
    a2.set_ylabel("Segundos")
    a2.legend()
    tasa = [num(f["tasa_error"]) * 100 for f in filas]
    err_bajo = [t - num(f["tasa_error_ic95_bajo"]) * 100 for t, f in zip(tasa, filas)]
    err_alto = [num(f["tasa_error_ic95_alto"]) * 100 - t for t, f in zip(tasa, filas)]
    a3.bar([str(x) for x in c], tasa, color=S2, width=0.5)
    a3.errorbar([str(x) for x in c], tasa, yerr=[err_bajo, err_alto], fmt="none", ecolor=TINTA, capsize=4, linewidth=1)
    a3.set_title("Turnos con error (IC 95 % Wilson)")
    a3.set_ylabel("% de turnos")
    techo = max(t + e for t, e in zip(tasa, err_alto))
    a3.set_ylim(0, min(100, techo + 8))
    for x, t in zip([str(x) for x in c], tasa):
        a3.text(x, t, f"{t:.0f} %", ha="center", va="bottom", fontsize=8, color=TINTA)
    a3.grid(axis="x", visible=False)
    for ax in (a1, a2):
        ax.set_xticks(c)
    for ax in (a1, a2, a3):
        ax.set_xlabel("Alumnos simultáneos")
    fig.tight_layout()
    guardar(fig, f"G06_carga_concurrente{suf}.png", "Fuente: 02_carga_concurrente.py")
    md.append("## Carga concurrente (throughput)\n")
    tabla(["Alumnos simultáneos", "Turnos OK / enviados", "Duración (s)", "Turnos/min", "p50 (ms)", "p95 (ms)",
           "Error % [IC95]", "Status"],
          [[f["concurrencia"], f"{f['turnos_ok']}/{f['turnos_enviados']}", f["duracion_s"], f["throughput_turnos_min"],
            fmt_ms(num(f.get("lat_p50_ms"))), fmt_ms(num(f.get("lat_p95_ms"))),
            f"{num(f['tasa_error']) * 100:.1f} [{num(f['tasa_error_ic95_bajo']) * 100:.1f}–"
            f"{num(f['tasa_error_ic95_alto']) * 100:.1f}]", f["status"].replace("|", "/")] for f in filas])


# ---------------------------------------------------------------- RAG (TA-023)
def rag(carpeta: Path | None):
    if carpeta is None:
        candidatos = sorted((RESULTADOS / "rag").glob("**/summary.csv")) if (RESULTADOS / "rag").exists() else []
        if not candidatos:
            return
        carpeta = candidatos[-1].parent
    if not (carpeta / "summary.csv").exists():
        print(f"  (sin summary.csv en {carpeta})")
        return
    filas = leer_csv(carpeta / "summary.csv")
    run = json.loads((carpeta / "run.json").read_text(encoding="utf-8")) if (carpeta / "run.json").exists() else {}
    ks = sorted({int(f["k"]) for f in filas})
    glob = {int(f["k"]): f for f in filas if f["specialty"] == "ALL"}
    metricas = [("precision_answerable", "Precisión@k"), ("recall", "Recall@k"), ("hit", "Hit@k"),
                ("abstention", "Abstención"), ("ragas_context_precision", "RAGAS ctx. precision"),
                ("ragas_context_recall", "RAGAS ctx. recall"), ("ragas_faithfulness", "RAGAS faithfulness"),
                ("ragas_response_relevancy", "RAGAS answer relevancy")]
    metricas = [(k, n) for k, n in metricas if any(num(glob[x].get(k)) is not None for x in ks)]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ancho = 0.8 / len(ks)
    for j, (k, color) in enumerate(zip(ks, (S1, S2, S3))):
        xs = [i + (j - (len(ks) - 1) / 2) * ancho for i in range(len(metricas))]
        vals = [num(glob[k].get(m)) or 0 for m, _ in metricas]
        ax.bar(xs, vals, width=ancho - 0.03, color=color, label=f"k = {k}")
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.01, f"{v:.2f}", ha="center", fontsize=8, color=TINTA)
    ax.set_xticks(range(len(metricas)), [n for _, n in metricas], rotation=15, ha="right")
    ax.set_ylim(0, 1.22)
    ax.grid(axis="x", visible=False)
    ax.set_title("Recuperación de evidencia (RAG): métricas globales")
    ax.legend(loc="upper left", ncols=len(ks))
    retr = run.get("retriever", {}).get("class", "?")
    nota = f"Fuente: python -m evals (TA-023) · {run.get('started_at', '')[:16]} · recuperador {retr} · RAGAS {run.get('ragas', {}).get('mode', 'off')}"
    guardar(fig, "G08_rag_metricas_globales.png", nota)

    kmax = max(ks)
    esp = [f for f in filas if int(f["k"]) == kmax and f["specialty"] != "ALL"]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ancho = 0.27
    for j, (m, n, color) in enumerate((("precision_answerable", "Precisión", S1), ("recall", "Recall", S2), ("hit", "Hit", S3))):
        xs = [i + (j - 1) * ancho for i in range(len(esp))]
        ax.bar(xs, [num(f.get(m)) or 0 for f in esp], width=ancho - 0.03, color=color, label=f"{n}@{kmax}")
    ax.set_xticks(range(len(esp)), [f["specialty"].replace("_", " ").capitalize() for f in esp])
    ax.set_ylim(0, 1.22)
    ax.grid(axis="x", visible=False)
    ax.set_title(f"Recuperación de evidencia por especialidad (k = {kmax})")
    ax.legend(loc="upper left", ncols=3)
    guardar(fig, "G09_rag_por_especialidad.png", nota)

    md.append("## Recuperación de evidencia (RAG, TA-023)\n")
    md.append(f"Corrida `{carpeta.name}`, recuperador `{retr}`, estado `{run.get('status')}`, "
              f"{len(run.get('selected_test_ids', []))} consultas.\n")
    def f4(v):
        return "N/A" if num(v) is None else f"{num(v):.3f}"
    tabla(["Especialidad", "k", "Consultas", "P@k (con ref.)", "Recall@k", "Hit@k", "Abstención", "Fallos seguridad",
           "RAGAS ctx P", "RAGAS ctx R", "Faithfulness", "Relevancy"],
          [[f["specialty"], f["k"], f["queries"], f4(f["precision_answerable"]), f4(f["recall"]), f4(f["hit"]),
            f4(f["abstention"]), f["security_failures"], f4(f.get("ragas_context_precision")),
            f4(f.get("ragas_context_recall")), f4(f.get("ragas_faithfulness")), f4(f.get("ragas_response_relevancy"))]
           for f in filas])
    # IC de Wilson para Hit@k global (proporción de consultas con al menos una evidencia esperada).
    for k in ks:
        n = int(glob[k].get("recall_n") or 0)
        h = num(glob[k].get("hit"))
        if n and h is not None:
            lo, hi = wilson(round(h * n), n)
            md.append(f"Hit@{k} global = {h:.3f} (n = {n}; IC 95 % Wilson {lo:.3f}–{hi:.3f}).  ")
    md.append("")


# ---------------------------------------------------------------- Lighthouse y axe
def frontend(suf):
    ruta = RESULTADOS / f"lighthouse_resumen{suf}.csv"
    if ruta.exists() and leer_csv(ruta):
        filas = leer_csv(ruta)
        modos = [m for m in ("movil", "escritorio") if any(f["modo"] == m for f in filas)]
        cats = (("rendimiento", "Rendimiento", S1), ("accesibilidad", "Accesibilidad", S2),
                ("buenas_practicas", "Buenas prácticas", S3), ("seo", "SEO", S4))
        fig, ejes = plt.subplots(1, len(modos), figsize=(7 * len(modos), 4.5), sharey=True, squeeze=False)
        for ax, modo in zip(ejes[0], modos):
            grupo = [f for f in filas if f["modo"] == modo]
            ancho = 0.2
            for j, (clave, nombre, color) in enumerate(cats):
                xs = [i + (j - 1.5) * ancho for i in range(len(grupo))]
                ax.bar(xs, [int(f[clave]) for f in grupo], width=ancho - 0.03, color=color, label=nombre)
            ax.axhline(90, color=TINTA2, linestyle=":", linewidth=1)
            ax.set_xticks(range(len(grupo)), [f["pagina"].capitalize() for f in grupo])
            ax.set_ylim(0, 105)
            ax.grid(axis="x", visible=False)
            ax.set_title(f"Lighthouse · {'móvil' if modo == 'movil' else 'escritorio'}")
        ejes[0][0].set_ylabel("Puntaje (0–100; ≥ 90 = bueno)")
        ejes[0][-1].legend(loc="lower right", bbox_to_anchor=(1, 1.0), ncols=4, fontsize=8)
        fig.tight_layout()
        guardar(fig, f"G10_lighthouse_puntajes{suf}.png", "Fuente: 04_frontend_lighthouse_axe.mjs")

        fig, ejes = plt.subplots(1, 3, figsize=(14, 4.2))
        for ax, (clave, nombre, umbral, escala) in zip(ejes, (("lcp_ms", "LCP (s)", 2.5, 1000),
                                                             ("tbt_ms", "TBT (ms)", 200, 1), ("cls", "CLS", 0.1, 1))):
            for j, (modo, color) in enumerate(zip(modos, (S1, S2))):
                grupo = [f for f in filas if f["modo"] == modo]
                xs = [i + (j - (len(modos) - 1) / 2) * 0.36 for i in range(len(grupo))]
                ax.bar(xs, [float(f[clave]) / escala for f in grupo], width=0.33, color=color,
                       label="Móvil" if modo == "movil" else "Escritorio")
            ax.axhline(umbral, color=TINTA2, linestyle=":", linewidth=1)
            ax.text(len(grupo) - 0.5, umbral, f"umbral «bueno» {umbral}", ha="right", va="bottom", fontsize=8, color=TINTA2)
            ax.set_xticks(range(len(grupo)), [f["pagina"].capitalize() for f in grupo], rotation=20)
            ax.set_title(nombre)
            ax.grid(axis="x", visible=False)
        ejes[0].legend()
        fig.tight_layout()
        guardar(fig, f"G11_core_web_vitals{suf}.png", "Fuente: Lighthouse (laboratorio, red simulada)")
        md.append("## Frontend: Lighthouse\n")
        tabla(["Página", "Modo", "Rend.", "Acces.", "B. prácticas", "SEO", "FCP (ms)", "LCP (ms)", "TBT (ms)", "CLS",
               "Peso (KB)"],
              [[f["pagina"], f["modo"], f["rendimiento"], f["accesibilidad"], f["buenas_practicas"], f["seo"], f["fcp_ms"],
                f["lcp_ms"], f["tbt_ms"], f["cls"], f["peso_total_kb"]] for f in filas])

    ruta = RESULTADOS / f"axe_resumen{suf}.csv"
    if ruta.exists() and leer_csv(ruta):
        filas = leer_csv(ruta)
        etiquetas = [f"{f['pagina'].capitalize()} · {'móvil' if f['modo'] == 'movil' else 'escritorio'}" for f in filas]
        fig, ax = plt.subplots(figsize=(9, 0.45 * len(filas) + 1.8))
        izquierda = [0] * len(filas)
        for clave, nombre, color in (("nodos_critical", "Crítico", SECUENCIAL[3]), ("nodos_serious", "Grave", SECUENCIAL[2]),
                                     ("nodos_moderate", "Moderado", SECUENCIAL[1]), ("nodos_minor", "Menor", SECUENCIAL[0])):
            v = [int(f[clave]) for f in filas]
            ax.barh(etiquetas, v, left=izquierda, color=color, label=nombre, edgecolor=FONDO, linewidth=2)
            izquierda = [a + b for a, b in zip(izquierda, v)]
        for i, total in enumerate(izquierda):
            ax.text(total, i, f" {total}", va="center", fontsize=8, color=TINTA)
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("Elementos con incumplimiento (WCAG 2.1 A/AA)")
        ax.set_title("Accesibilidad automática (axe-core) por página")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.set_xlim(0, max(izquierda) * 1.12 + 1)
        ax.legend(loc="lower right", bbox_to_anchor=(1, 1.0), ncols=4, fontsize=8)
        guardar(fig, f"G12_axe_violaciones{suf}.png", "Fuente: 04_frontend_lighthouse_axe.mjs · axe-core, etiquetas wcag2a/aa y wcag21a/aa")
        md.append("## Frontend: accesibilidad (axe-core, WCAG 2.1 AA)\n")
        tabla(["Página", "Modo", "Reglas violadas", "Reglas superadas", "Crítico", "Grave", "Moderado", "Menor", "Reglas"],
              [[f["pagina"], f["modo"], f["reglas_violadas"], f["reglas_superadas"], f["nodos_critical"],
                f["nodos_serious"], f["nodos_moderate"], f["nodos_minor"], f["reglas"] or "—"] for f in filas])


# ---------------------------------------------------------------- SUS
def sus():
    ruta = RESULTADOS / "sus_puntajes.csv"
    if not ruta.exists():
        return
    filas = leer_csv(ruta)
    meta = json.loads((RESULTADOS / "sus_resumen.json").read_text(encoding="utf-8"))
    v = [float(f["sus"]) for f in filas]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bandas = ((0, 39.2, "Muy pobre"), (39.2, 52, "Pobre"), (52, 72.6, "Aceptable"), (72.6, 85.5, "Bueno"), (85.5, 100, "Excelente"))
    for i, (a, b, nombre) in enumerate(bandas):
        ax.axhspan(a, b, color="#f0efec" if i % 2 else FONDO, zorder=0)
        ax.text(len(v) + 0.55, (a + b) / 2, nombre, va="center", fontsize=8, color=TINTA2)
    ax.bar([f["participante"] for f in filas], v, color=S1, width=0.55, zorder=2)
    lo, hi = meta["ic95"]
    ax.axhline(meta["media"], color=TINTA, linewidth=1, linestyle="--", zorder=3)
    if lo is not None:
        ax.errorbar([len(v)], [meta["media"]], yerr=[[meta["media"] - lo], [hi - meta["media"]]], fmt="o",
                    color=S2, markersize=8, capsize=6, linewidth=2, zorder=4)
        ax.text(len(v), hi + 1.5, "Media ± IC95", ha="center", fontsize=8, color=TINTA)
    ax.axhline(68, color=TINTA2, linestyle=":", linewidth=1)
    if lo is not None:
        ax.text(len(v) - 0.25, meta["media"], f"{meta['media']:.1f}\n({lo:.1f}–{hi:.1f})", ha="right",
                va="center", fontsize=8, color=TINTA)
    ax.set_ylim(0, 100)
    ax.set_xlim(-0.6, len(v) + 1.4)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Puntaje SUS (0–100)")
    ax.set_title(f"Usabilidad percibida (SUS), n = {len(v)}")
    guardar(fig, "G13_sus.png", "Fuente: 05_sus.py · línea discontinua = media; punteada = 68, promedio de referencia; "
            "escala de adjetivos de Bangor, Kortum y Miller (2009)")
    md.append("## Usabilidad (SUS)\n")
    md.append(f"n = {meta['n']}; media {meta['media']:.1f} ± {meta['de']:.1f}; mediana {meta['mediana']:.1f}; "
              f"IC 95 % {'n/d' if lo is None else f'{lo:.1f}–{hi:.1f}'}; «{meta['adjetivo_media']}», nota {meta['nota_media']}; "
              f"{meta['sobre_68']} de {meta['n']} sobre 68.\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rag", type=Path, help="carpeta de una corrida de TA-023 (python -m evals)")
    ap.add_argument("--etiqueta", default="local")
    args = ap.parse_args()
    suf = "" if args.etiqueta == "local" else f"_{args.etiqueta}"
    md.extend([f"# TA-024 · Resumen de métricas ({args.etiqueta})", "", f"Generado {ahora()} por graficar.py.", ""])
    print("Generando gráficos en", GRAFICOS)
    lat = latencia(suf)
    vz = voz(suf)
    percentiles_juntos(lat, vz, suf)
    carga(suf)
    rag(args.rag.resolve() if args.rag else None)
    frontend(suf)
    sus()
    if not generados:
        print("No hay resultados todavía: ejecute primero los scripts 01 a 05 (ver README).")
        return
    md.append("## Gráficos\n")
    md.extend(f"- `graficos/{g}`" for g in generados)
    (RESULTADOS / f"resumen_metricas{suf}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(generados)} gráficos · tablas en {RESULTADOS / f'resumen_metricas{suf}.md'}")


if __name__ == "__main__":
    main()
