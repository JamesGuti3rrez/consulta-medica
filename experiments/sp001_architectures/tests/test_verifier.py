from app.case_store import load_case
from app.models import GeneratedAnswer
from app.verifier import Verifier


def test_detects_exact_diagnostic_leak():
    case = load_case("case_001")
    answer = GeneratedAnswer(natural_response="El diagnóstico es STEMI inferior.")
    result = Verifier().verify(case, answer)
    assert result["diagnostic_leak"] is True


def test_safe_refusal_passes_leak_check():
    case = load_case("case_001")
    answer = GeneratedAnswer(natural_response="No puedo confirmar el diagnóstico en esta fase.", refused=True)
    result = Verifier().verify(case, answer)
    assert result["diagnostic_leak"] is False
