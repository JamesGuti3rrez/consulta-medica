from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ai_layer_does_not_import_cases_engine_or_protected():
    forbidden_imports = ("server.cases", "server.engine", "server.guardrails", "server.orchestration", "server.rag")
    for path in (ROOT / "server/ai").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in forbidden_imports:
            assert forbidden not in text, f"{path} importa {forbidden}"
        assert 'get_protected(' not in text, f"{path} intenta leer protected"


def test_only_safety_or_evaluation_consume_get_protected():
    offenders = []
    for path in (ROOT / "server").rglob("*.py"):
        if path.name == "repository.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "get_protected(" not in text:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if not (relative.startswith("server/engine/safety/") or relative.startswith("server/engine/evaluation/")):
            offenders.append(relative)
    assert offenders == []
