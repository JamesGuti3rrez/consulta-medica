from .base import Strategy
from ..retrieval import selective_retrieve

class SelectiveRetrievalStrategy(Strategy):
    name = "selective_retrieval"

    def build_context(self, case, role, question):
        return selective_retrieve(case, role, question)
