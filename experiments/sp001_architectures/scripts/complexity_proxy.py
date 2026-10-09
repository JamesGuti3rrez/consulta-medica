from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCH_DIR = ROOT / "app" / "architectures"
FILES = ["supervisor.py", "stategraph.py", "handoffs.py", "hybrid.py"]


def logical_loc(path: Path) -> int:
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            total += 1
    return total


def main():
    print("Proxy de complejidad (LOC no vacías/no comentario). No equivale a facilidad de implementación.")
    for name in FILES:
        print(f"{name:20s} {logical_loc(ARCH_DIR / name):4d} LOC")


if __name__ == "__main__":
    main()
