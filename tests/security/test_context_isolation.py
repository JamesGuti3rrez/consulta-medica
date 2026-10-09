import json
from pathlib import Path

from server.cases import CanonicalCaseRepository
from server.domain import AgentRole
from server.engine.disclosure.context import ContextAssembler
from server.rag.port import RetrievedEvidence

ROOT = Path(__file__).resolve().parents[2]


def test_context_never_contains_protected_section_or_diagnosis():
    repo = CanonicalCaseRepository(ROOT / "data/cases/curated", ROOT / "schemas/caso.schema.json")
    case = repo.get_conversation_case("CARD-001")
    context = ContextAssembler().build(
        case=case,
        role=AgentRole.PACIENTE,
        revealed_evidence_ids=["CARD-001.motivo.cefalea"],
        retrieved=[RetrievedEvidence("CARD-001.anamnesis.inicio_dolor", "El dolor comenzó hace tres días")],
    )
    payload = json.dumps(context, ensure_ascii=False).casefold()
    assert "protected" not in payload
    assert "treatment_reference" not in payload
    assert "differentials" not in payload
    assert "migraña sin signos de alarma" not in payload
