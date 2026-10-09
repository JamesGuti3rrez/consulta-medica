from app.case_store import load_case
from app.context_policy import ContextPolicy


def test_protected_diagnosis_never_reaches_conversational_roles():
    case = load_case("case_001")
    for role in ["assistant", "supervisor", "patient", "laboratory", "radiology", "specialist"]:
        ctx = ContextPolicy.for_role(case, role, set())
        assert "protected_evaluation" not in ctx


def test_progressive_case_has_no_initial_answer_exposure():
    from app.dataset_validation import validate_progressive_case
    case = load_case("case_001")
    result = validate_progressive_case(case)
    assert result["valid"] is True
    assert result["initial_answer_exposed"] is False
