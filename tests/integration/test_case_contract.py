from pathlib import Path

from server.cases import CanonicalCaseRepository

ROOT = Path(__file__).resolve().parents[2]


def test_canonical_case_is_curated_and_schema_valid():
    repo = CanonicalCaseRepository(ROOT / "data/cases/curated", ROOT / "schemas/caso.schema.json")
    case = repo.get_case("CARD-001")
    assert case["status"] == "curado"
    assert set(["public", "on_request", "protected"]).issubset(case)
    conversation = repo.get_conversation_case("CARD-001")
    assert "protected" not in conversation
