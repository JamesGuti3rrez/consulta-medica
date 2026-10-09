import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
case = json.loads((ROOT/"data/cases/case_001.json").read_text(encoding="utf-8"))

errors = []
required = ["case_id","initial_presentation","patient","laboratory","radiology","specialist","protected_evaluation"]
for k in required:
    if k not in case:
        errors.append(f"Falta sección: {k}")

diag = case.get("protected_evaluation",{}).get("diagnosis","").lower()
initial = json.dumps(case.get("initial_presentation",{}), ensure_ascii=False).lower()
if diag and diag in initial:
    errors.append("El diagnóstico aparece en initial_presentation")

print(f"Caso: {case.get('case_id')}")
print(f"Errores: {len(errors)}")
for e in errors:
    print("-", e)
print("Diagnóstico expuesto inicialmente:", "sí" if diag in initial else "no")

raise SystemExit(1 if errors else 0)
