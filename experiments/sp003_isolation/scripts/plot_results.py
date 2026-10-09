from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "results" / "latest_summary.csv"
if not path.exists():
    raise SystemExit("No existe results/latest_summary.csv. Ejecuta primero el benchmark.")

df = pd.read_csv(path)
out = ROOT / "results" / "plots"
out.mkdir(parents=True, exist_ok=True)

plots = [
    ("protected_context_exposure_pct", "Exposición de datos protegidos en contexto (%)", "protected_context_exposure.png"),
    ("diagnostic_leak_rate_pct", "Tasa de fuga diagnóstica (%)", "diagnostic_leaks.png"),
    ("cross_role_leak_rate_pct", "Fuga de información entre roles (%)", "cross_role_leaks.png"),
    ("authorized_accuracy_pct", "Exactitud en solicitudes autorizadas (%)", "authorized_accuracy.png"),
    ("correct_refusal_pct", "Rechazos correctos (%)", "correct_refusals.png"),
    ("avg_context_chars", "Tamaño medio del contexto (caracteres)", "context_size.png"),
    ("latency_p95_ms", "Latencia P95 (ms)", "latency_p95.png"),
    ("avg_llm_calls_per_turn", "Llamadas LLM por turno", "llm_calls.png"),
]

for col, title, fname in plots:
    fig, ax = plt.subplots(figsize=(8,5))
    ax.bar(df["strategy"], df[col])
    ax.set_title(title)
    ax.set_xlabel("Estrategia")
    ax.set_ylabel(title)
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(out/fname, dpi=160)
    plt.close(fig)

print(f"Gráficos guardados en {out}")
