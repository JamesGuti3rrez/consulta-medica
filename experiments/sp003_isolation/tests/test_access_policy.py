from app.repository import load_case
from app.access_policy import build_minimal_context, build_shared_context
from app.verifier import protected_in_context

def test_shared_context_exposes_diagnosis():
    case = load_case()
    ctx, _ = build_shared_context(case, "patient")
    assert protected_in_context(ctx, case)

def test_minimal_context_hides_diagnosis():
    case = load_case()
    for role in ["patient","assistant","laboratory","radiologist","specialist"]:
        ctx, _ = build_minimal_context(case, role)
        assert not protected_in_context(ctx, case)
