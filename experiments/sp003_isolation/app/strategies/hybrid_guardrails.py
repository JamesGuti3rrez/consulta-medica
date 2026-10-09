from .base import Strategy
from ..retrieval import selective_retrieve

class HybridGuardrailsStrategy(Strategy):
    name = "hybrid_guardrails"
    uses_runtime_guardrail = True

    def build_context(self, case, role, question):
        return selective_retrieve(case, role, question)
