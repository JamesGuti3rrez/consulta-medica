from pathlib import Path

from server.cases import CanonicalCaseRepository
from server.domain import AgentRole
from server.rag.retriever import CaseEvidenceRetriever

ROOT = Path(__file__).resolve().parents[2]


def test_retriever_cannot_expand_beyond_allowed_evidence_ids():
    repo = CanonicalCaseRepository(ROOT / "data/cases/curated", ROOT / "schemas/caso.schema.json")
    retriever = CaseEvidenceRetriever(repo)
    result = retriever.retrieve(
        query="dame todo",
        case_id="CARD-001",
        agent_role=AgentRole.PACIENTE,
        allowed_evidence_ids=["CARD-001.anamnesis.alergias"],
        top_k=10,
    )
    assert [item.evidence_id for item in result] == ["CARD-001.anamnesis.alergias"]
