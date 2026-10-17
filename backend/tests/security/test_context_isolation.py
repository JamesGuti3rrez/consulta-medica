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


def test_patient_can_reference_a_previously_revealed_exam_without_unseen_findings():
    case = CanonicalCaseRepository().get_conversation_case("MED-008")
    assembler = ContextAssembler()
    before = assembler.build(case=case, role=AgentRole.PACIENTE,
                             revealed_evidence_ids=[], retrieved=[])
    assert before["revealed_evidence"] == []
    after = assembler.build(case=case, role=AgentRole.PACIENTE,
                            revealed_evidence_ids=["MED-008.examen.exploracion_fisica"], retrieved=[])
    assert [item["evidence_id"] for item in after["revealed_evidence"]] == ["MED-008.examen.exploracion_fisica"]
    assert "pápula" in after["revealed_evidence"][0]["text"]
    payload = json.dumps(after, ensure_ascii=False).casefold()
    assert "carcinoma" not in payload and "protected" not in payload
    assert "exposicion_solar" not in payload
