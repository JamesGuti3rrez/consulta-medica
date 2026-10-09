from .base import Strategy
from ..access_policy import build_shared_context

class SharedContextStrategy(Strategy):
    name = "shared_context"

    def build_context(self, case, role, question):
        return build_shared_context(case, role)
