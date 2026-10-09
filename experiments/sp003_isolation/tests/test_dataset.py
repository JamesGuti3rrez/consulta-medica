from app.repository import load_case

def test_protected_evaluation_exists_and_is_separate():
    case = load_case()
    assert "protected_evaluation" in case
    assert "diagnosis" in case["protected_evaluation"]
    assert case["protected_evaluation"]["diagnosis"] not in str(case["initial_presentation"])
