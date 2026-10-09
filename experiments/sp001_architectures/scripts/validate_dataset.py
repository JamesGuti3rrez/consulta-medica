import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.case_store import load_all_cases
from app.dataset_validation import validate_progressive_case


def main():
    results = [validate_progressive_case(c) for c in load_all_cases()]
    valid = sum(r["valid"] for r in results)
    exposed = sum(r["initial_answer_exposed"] for r in results)
    print(f"Casos válidos: {valid}/{len(results)} ({100*valid/len(results):.1f}%)")
    print(f"Casos con respuesta expuesta inicialmente: {exposed}")
    for r in results:
        if not r["valid"]:
            print(r)


if __name__ == "__main__":
    main()
