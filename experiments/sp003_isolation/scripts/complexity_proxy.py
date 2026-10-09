from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / "app" / "strategies"

print("Proxy de complejidad (LOC no vacías/no comentario). No equivale a facilidad de implementación.")
for path in sorted(folder.glob("*.py")):
    if path.name in {"__init__.py","base.py"}:
        continue
    lines = [
        line for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    print(f"{path.name:28} {len(lines):4} LOC")
