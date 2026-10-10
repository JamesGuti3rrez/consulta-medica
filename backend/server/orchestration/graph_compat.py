try:
    from langgraph.graph import StateGraph, START, END  # type: ignore
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    START, END = "__start__", "__end__"

    class _Compiled:
        def __init__(self, graph):
            self.graph = graph

        def invoke(self, state):
            current = self.graph.edges[START]
            value = dict(state)
            for _ in range(20):
                if current == END:
                    return value
                update = self.graph.nodes[current](value) or {}
                value.update(update)
                if current in self.graph.conditional:
                    router, mapping = self.graph.conditional[current]
                    current = mapping[router(value)]
                else:
                    current = self.graph.edges.get(current, END)
            raise RuntimeError("Ciclo excedido en grafo de compatibilidad")

    class StateGraph:
        def __init__(self, _state):
            self.nodes, self.edges, self.conditional = {}, {}, {}

        def add_node(self, name, fn):
            self.nodes[name] = fn

        def add_edge(self, source, target):
            self.edges[source] = target

        def add_conditional_edges(self, source, router, mapping):
            self.conditional[source] = (router, mapping)

        def compile(self):
            return _Compiled(self)
