from pathlib import Path

from server.cases import CanonicalCaseRepository
from server.engine.safety.protected_lexicon import ProtectedLexiconService
from server.guardrails import OutputGuard

ROOT = Path(__file__).resolve().parents[2]


def test_guard_blocks_diagnosis_without_receiving_protected_block():
    repo = CanonicalCaseRepository(ROOT / "data/cases/curated", ROOT / "schemas/caso.schema.json")
    denylist = ProtectedLexiconService(repo).for_case("CARD-001")
    ok, reason = OutputGuard().validate("El diagnóstico es Migraña sin signos de alarma", denylist)
    assert ok is False
    assert reason
