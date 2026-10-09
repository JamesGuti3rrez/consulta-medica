from app.architectures import build_architectures
from app.case_store import load_case
from app.llm import MockLLM
from app.models import SessionState


def test_all_architectures_execute_same_question():
    case = load_case("case_001")
    for arch in build_architectures(MockLLM()):
        session = SessionState(session_id=f"T-{arch.name}", case_id=case["case_id"])
        result = arch.run_turn(case, "F06", "Solicito troponina T.", session)
        assert "CARD-001.lab.troponin_t" in result.answer.evidence_ids
        assert result.validation["diagnostic_leak"] is False
