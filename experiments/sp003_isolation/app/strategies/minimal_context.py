from .base import Strategy
from ..access_policy import build_minimal_context

class MinimalContextStrategy(Strategy):
    name = "minimal_context"

    def build_context(self, case, role, question):
        return build_minimal_context(case, role)
