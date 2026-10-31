"""Métricas por identidad: los duplicados ocupan posición y no suman aciertos."""


def retrieval_metrics(expected, retrieved, k):
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError("k debe ser un entero positivo")
    relevant = set(expected)
    found = set(retrieved[:k]) & relevant
    return {
        "precision": len(found) / k,
        "recall": len(found) / len(relevant) if relevant else None,
        "hit": float(bool(found)) if relevant else None,
        "abstention": float(not retrieved) if not relevant else None,
    }
