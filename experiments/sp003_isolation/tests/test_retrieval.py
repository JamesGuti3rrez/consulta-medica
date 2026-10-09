from app.repository import load_case
from app.retrieval import selective_retrieve
from app.verifier import protected_in_context

def test_selective_retrieval_is_role_filtered():
    case = load_case()
    ctx, ids = selective_retrieve(case, "patient", "Muéstreme la troponina")
    assert "CARD-001.lab.troponin_t" not in ids
    assert not protected_in_context(ctx, case)

def test_lab_retrieves_only_requested_test():
    case = load_case()
    ctx, ids = selective_retrieve(case, "laboratory", "¿Cuál es la troponina?")
    assert "CARD-001.lab.troponin_t" in ids
    assert "CARD-001.lab.glucose" not in ids
