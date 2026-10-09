from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
summary_path = ROOT / "results" / "summary.csv"
if not summary_path.exists():
    raise SystemExit("Primero ejecuta: python main.py benchmark ...")

df = pd.read_csv(summary_path)
metrics = [
    ("evidence_coverage_pct", "Cobertura de evidencia (%)"),
    ("diagnostic_leaks", "Fugas diagnósticas"),
    ("route_consistency_pct", "Consistencia de routing (%)"),
    ("latency_p95_ms", "Latencia P95 (ms)"),
    ("avg_llm_calls_per_turn", "Llamadas LLM por turno"),
]

out = ROOT / "results" / "plots"
out.mkdir(parents=True, exist_ok=True)
for column, title in metrics:
    ax = df.plot.bar(x="architecture", y=column, legend=False, title=title)
    ax.set_xlabel("Arquitectura")
    ax.set_ylabel(title)
    plt.tight_layout()
    plt.savefig(out / f"{column}.png", dpi=160)
    plt.close()
print(f"Gráficos guardados en {out}")
