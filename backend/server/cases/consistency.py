"""TA-027: informe determinista previo a la presentación; no certifica validez clínica."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
import json
import math

from jsonschema import Draft202012Validator

from .rules import check_case_rules, check_case_warnings, evidence_text
from .validator import load_schema
from server.guardrails.output_guard import OutputGuard, _normalize

VERSION = "case-consistency-1.0.0"


@lru_cache
def _schema():
    return Draft202012Validator(load_schema())


def review_case(case) -> dict:
    """Hallazgos para personal autorizado; no enviar este informe a los agentes ni al alumno."""
    findings = []

    def add(code, severity, path, message, ids=()):
        findings.append({"code": code, "severity": severity, "path": path,
                         "message": message, "evidence_ids": list(ids)})

    for error in sorted(_schema().iter_errors(case), key=lambda e: str(list(e.path))):
        add("CV001", "error", ".".join(map(str, error.path)),
            "No cumple el contrato del caso: " + str(error.validator) + ".")
    if not findings:
        public = case["public"]
        items = [public["chief_complaint"], *public["items"], *case["on_request"]]
        ids = [i["evidence_id"] for i in items]
        for message in check_case_rules(case):
            add(message.split()[0], "error", "caso", message,
                [eid for eid in ids if eid in message])
        for message in check_case_warnings(case):
            add("CVW01", "aviso", "public", message)
        diagnosis = case["protected"]["diagnosis"]
        terms = {_normalize(s) for s in [diagnosis["name"], *diagnosis["synonyms"]] if len(s) >= 4}
        visible = [case["title"], public["patient"]["alias"], *public.get("allergies", [])]
        visible.extend(i["label"] + " " + evidence_text(i) for i in items)
        if not OutputGuard().validate(" ".join(visible), terms)[0]:
            add("CV002", "error", "public/on_request", "Referencia diagnóstica expuesta fuera de protected.")
        by_label = {}
        for item in items:
            eid, label = item["evidence_id"], _normalize(item["label"])
            if label in by_label and by_label[label][1] != evidence_text(item):
                add("CV003", "revision", "evidencia", "Una misma etiqueta contiene datos diferentes; revisar contexto temporal.",
                    [by_label[label][0], eid])
            by_label[label] = (eid, evidence_text(item))
            value = item.get("value")
            if isinstance(value, (int, float)):
                bounds = None
                if "temperatura" in label and item.get("unit") in {"Cel", "°C", "C"}:
                    bounds = (25, 45)
                elif "saturacion" in label and item.get("unit") == "%":
                    bounds = (0, 100)
                elif "frecuencia cardiaca" in label and item.get("unit") in {"/min", "1/min"}:
                    bounds = (0, 300)
                if not math.isfinite(value) or (bounds and not bounds[0] <= value <= bounds[1]):
                    add("CV004", "error", "evidencia.value", "Valor incompatible con los límites técnicos de plausibilidad.", [eid])
        for item in case["on_request"]:
            policy = item["reveal_policy"]
            if policy["owner"] == "especialista" and policy["mode"] != "al_preguntar":
                add("CV005", "error", "reveal_policy", "La interconsulta requiere una solicitud al especialista.", [item["evidence_id"]])
    blocked = any(f["severity"] == "error" for f in findings)
    review = any(f["severity"] == "revision" for f in findings)
    return {"case_id": case.get("case_id") if isinstance(case, dict) else None, "version": VERSION,
            "fingerprint": hashlib.sha256(json.dumps(case, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "status": "bloqueado" if blocked else "revision_requerida" if review else "apto",
            "can_present": not blocked and not review, "requires_human_review": blocked or review,
            "summary": dict(Counter(f["severity"] for f in findings)), "findings": findings,
            "scope": "Validación automática de consistencia; no sustituye revisión clínica humana."}


def ensure_presentable(case):
    report = review_case(case)
    if not report["can_present"]:
        codes = sorted({f["code"] for f in report["findings"] if f["severity"] != "aviso"})
        raise ValueError("Caso bloqueado por revisión de consistencia: " + ", ".join(codes))
    return report
