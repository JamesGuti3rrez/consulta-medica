import json
from typing import Any
from .access_policy import ROLE_KEYS, _collect_evidence_ids

def _flatten(section: Any) -> list[tuple[str, Any]]:
    items = []
    if isinstance(section, dict):
        for k, v in section.items():
            if isinstance(v, (dict, list)):
                items.extend(_flatten(v))
            else:
                items.append((str(k), v))
    elif isinstance(section, list):
        for x in section:
            items.extend(_flatten(x))
    return items

def selective_retrieve(case: dict, role: str, question: str) -> tuple[str, list[str]]:
    """
    Recuperación selectiva controlada por metadatos/rol.
    No es un vector store: modela la propiedad de aislamiento de una RAG
    con prefiltrado de privilegios.
    """
    allowed_keys = ROLE_KEYS.get(role, [])
    q = question.lower()

    # Primero se limita el universo por rol.
    allowed = {k: case[k] for k in allowed_keys if k in case}

    # Luego se selecciona la sección más relevante con reglas lexicales simples.
    selected: dict[str, Any] = {}
    if role == "laboratory":
        lab = allowed.get("laboratory", {})
        if "tropon" in q and "troponin_t" in lab:
            selected = {"troponin_t": lab["troponin_t"]}
        elif "gluc" in q and "glucose" in lab:
            selected = {"glucose": lab["glucose"]}
        else:
            selected = lab
    elif role == "radiologist":
        selected = allowed.get("radiology", {})
    elif role == "patient":
        pat = allowed.get("patient", {})
        if "anteced" in q:
            selected = {"history": pat.get("history", [])}
        elif any(w in q for w in ["sínt", "sint", "siente", "dolor"]):
            selected = {"symptoms": pat.get("symptoms", [])}
        else:
            selected = pat
    elif role == "specialist":
        selected = allowed.get("specialist", {})
    elif role == "assistant":
        selected = allowed
    else:
        selected = {}

    return json.dumps(selected, ensure_ascii=False), _collect_evidence_ids(selected)
