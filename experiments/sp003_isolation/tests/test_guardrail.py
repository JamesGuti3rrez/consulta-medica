from app.repository import load_case
from app.verifier import apply_guardrail

def test_guardrail_blocks_diagnosis():
    case = load_case()
    text = "El diagnóstico es infarto agudo de miocardio inferior."
    final, ids, blocked, refused = apply_guardrail(text, [], "patient", case)
    assert blocked
    assert refused
    assert "infarto agudo de miocardio inferior" not in final.lower()
