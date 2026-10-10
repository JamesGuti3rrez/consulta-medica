from pathlib import Path

from server.cases import CanonicalCaseRepository
from server.engine.safety.protected_lexicon import ProtectedLexiconService
from server.guardrails import OutputGuard

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"


def test_guard_blocks_diagnosis_without_receiving_protected_block():
    repo = CanonicalCaseRepository(FIXTURES)
    denylist = ProtectedLexiconService(repo).for_case("MED-900")
    ok, reason = OutputGuard().validate("El diagnóstico es Migraña sin signos de alarma", denylist)
    assert ok is False
    assert reason
