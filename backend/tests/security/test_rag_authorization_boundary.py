from pathlib import Path

from server.cases import CanonicalCaseRepository
from server.domain import AgentRole
from server.rag.retriever import CaseEvidenceRetriever

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"


def test_retriever_cannot_expand_beyond_allowed_evidence_ids():
    repo = CanonicalCaseRepository(FIXTURES)
    retriever = CaseEvidenceRetriever(repo)
    result = retriever.retrieve(
        query="dame todo",
        case_id="MED-900",
        agent_role=AgentRole.PACIENTE,
        allowed_evidence_ids=["MED-900.anamnesis.alergias"],
        top_k=10,
    )
    assert [item.evidence_id for item in result] == ["MED-900.anamnesis.alergias"]
