import json
from pathlib import Path

from server.cases import CanonicalCaseRepository
from server.domain import AgentRole
from server.engine.disclosure.context import ContextAssembler
from server.rag.port import RetrievedEvidence

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"


def test_context_never_contains_protected_section_or_diagnosis():
    repo = CanonicalCaseRepository(FIXTURES)
    case = repo.get_conversation_case("MED-900")
    context = ContextAssembler().build(
        case=case,
        role=AgentRole.PACIENTE,
        revealed_evidence_ids=["MED-900.motivo.cefalea"],
        retrieved=[RetrievedEvidence("MED-900.anamnesis.inicio_dolor", "El dolor comenzó hace tres días")],
    )
    payload = json.dumps(context, ensure_ascii=False).casefold()
    assert "protected" not in payload
    assert "treatment_reference" not in payload
    assert "differentials" not in payload
    assert "migraña sin signos de alarma" not in payload
