"""Un índice RAG desactualizado no debe esconder datos que el acceso por rol ya autorizó."""

from types import SimpleNamespace

from server.domain import AgentRole
from server.rag.embedded import EmbeddedRAGRetriever
from server.rag.retriever import RetrievalResult


class CaseRepository:
    def get_conversation_case(self, case_id):
        return {"on_request": [
            {"evidence_id": "CIR-005.lab.coagulacion", "label": "Coagulación", "text": "TTPa prolongado."},
            {"evidence_id": "CIR-005.lab.factores", "label": "Factores", "text": "Factor VIII disminuido; IX normal."},
            {"evidence_id": "CIR-005.lab.plaquetas", "label": "Plaquetas", "text": "Plaquetas normales."},
        ]}


class StaleIndexService:
    """Índice armado antes de completar el caso: no tiene «factores» y guarda un texto viejo de plaquetas."""

    def __init__(self):
        documents = ({"case_id": "CIR-005", "source_id": "CIR-005.lab.coagulacion"},
                     {"case_id": "CIR-005", "source_id": "CIR-005.lab.plaquetas"})
        self.retriever = SimpleNamespace(snapshot=SimpleNamespace(documents=documents))

    def evidence_search(self, *, allowed_evidence_ids, **kwargs):
        texts = {"CIR-005.lab.coagulacion": "Coagulación TTPa prolongado.",
                 "CIR-005.lab.plaquetas": "Plaquetas Recuento bajo (texto viejo)."}
        return [RetrievalResult(evidence_id=eid, text=texts[eid], score=0.5, case_id="CIR-005", role="laboratorio",
                                category="laboratorio", requires=(), specialty="", title="")
                for eid in allowed_evidence_ids if eid in texts]


def _retriever():
    retriever = EmbeddedRAGRetriever.__new__(EmbeddedRAGRetriever)
    retriever.service = StaleIndexService()
    retriever.repository = CaseRepository()
    return retriever


def test_authorized_data_missing_from_the_index_comes_from_the_case():
    results = _retriever().retrieve(query="factor VIII", case_id="CIR-005", agent_role=AgentRole.LABORATORIO,
                                    allowed_evidence_ids=["CIR-005.lab.factores"])
    assert [(r.evidence_id, r.text) for r in results] == [("CIR-005.lab.factores", "Factor VIII disminuido; IX normal.")]


def test_stale_text_in_the_index_is_replaced_by_the_current_case_text():
    results = _retriever().retrieve(query="plaquetas", case_id="CIR-005", agent_role=AgentRole.LABORATORIO,
                                    allowed_evidence_ids=["CIR-005.lab.coagulacion", "CIR-005.lab.plaquetas"])
    texts = {r.evidence_id: r.text for r in results}
    assert texts["CIR-005.lab.coagulacion"] == "Coagulación TTPa prolongado."
    assert texts["CIR-005.lab.plaquetas"] == "Plaquetas normales."


def test_unauthorized_data_is_never_added():
    results = _retriever().retrieve(query="todo", case_id="CIR-005", agent_role=AgentRole.LABORATORIO,
                                    allowed_evidence_ids=["CIR-005.lab.coagulacion"])
    assert [r.evidence_id for r in results] == ["CIR-005.lab.coagulacion"]
