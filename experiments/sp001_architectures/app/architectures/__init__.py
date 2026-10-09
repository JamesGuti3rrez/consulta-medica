from app.architectures.supervisor import SupervisorArchitecture
from app.architectures.stategraph import StateGraphArchitecture
from app.architectures.handoffs import HandoffsArchitecture
from app.architectures.hybrid import HybridArchitecture


def build_architectures(llm):
    return [
        SupervisorArchitecture(llm),
        StateGraphArchitecture(llm),
        HandoffsArchitecture(llm),
        HybridArchitecture(llm),
    ]
