"""Candidato -> validación -> evidencia sintética. Persistencia únicamente en la sesión activa."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

from server.ai.llm.gateway import LLMUnavailable
from server.ai.llm.providers import ProviderError
from server.domain import AgentReply, AgentRole
from server.engine.disclosure.exam_policy import generation_permission
from server.engine.validation.exams import VERSION, specification, validate_candidate


class SyntheticExamCompletion:
    def __init__(self, composer):
        self.composer = composer

    def complete(self, *, case, role, intent, message, context, previous, forbidden_terms, guard):
        panel, decision = generation_permission(case=case, role=role, intent=intent, message=message)
        if panel is None:
            return None
        spec = specification(panel, case["public"]["patient"]["sex"])
        fingerprint = hashlib.sha256(json.dumps(case, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        saved = (previous or {}).get(panel)
        reused = bool(saved and saved.get("case_fingerprint") == fingerprint and saved.get("validator_version") == VERSION)
        usage = (0, 0)
        provider, model = "sesion", "resultado-validado"
        if reused:
            candidate = saved.get("candidate")
        else:
            try:
                result = self.composer.compose(panel=panel, context=context, specification=spec)
                usage = (result.input_tokens, result.output_tokens)
                provider, model = result.provider, result.model
                candidate = json.loads(result.text)
            except (LLMUnavailable, ProviderError, ValueError, TypeError):
                return self._rejected("generador_no_disponible", usage)
        valid, reason = validate_candidate(candidate, panel=panel, sex=case["public"]["patient"]["sex"], case=case)
        if not valid:
            return self._rejected(reason, usage)
        indicators = [{"key": key, "label": rule["label"], "value": candidate["values"][key], "unit": rule["unit"],
                       "reference": {"min": rule["min"], "max": rule["max"]}, "reference_source": rule["source"]}
                      for key, rule in spec.items()]
        text = "Resultado sintético educativo, no observado en una persona real. " + "; ".join(
            f"{i['label']}: {i['value']:g} {i['unit']} (referencia educativa {i['reference']['min']}–{i['reference']['max']} {i['unit']})"
            for i in indicators) + "."
        if not guard.validate(text, forbidden_terms)[0]:
            return self._rejected("contenido_protegido", usage)
        eid = case["case_id"] + ".sintetico." + panel
        evidence = {"evidence_id": eid, "label": "Hemograma parcial sintético" if panel == "hemograma" else "Glucosa sintética en ayunas",
                    "text": text, "category": "laboratorio", "synthetic": True, "indicators": indicators,
                    "reveal_policy": {"owner": "laboratorio", "mode": "al_solicitar_examen", "requires": [panel]},
                    "provenance": {"provider": provider, "model": model, "validator_version": VERSION,
                                   "validation": "contrato_validado", "clinical_review": "pendiente"}}
        snapshot = {"candidate": deepcopy(candidate), "evidence": evidence, "case_fingerprint": fingerprint,
                    "validator_version": VERSION, "created_at": saved["created_at"] if reused else datetime.now(timezone.utc).isoformat()}
        reply = AgentReply(role=AgentRole.LABORATORIO, text=text, provider=provider, model=model,
                           evidence_ids=[eid], input_tokens=usage[0], output_tokens=usage[1])
        return {"reply": reply, "evidence": [evidence], "snapshot": {panel: snapshot}, "reused": reused,
                "validation": {"decision": "contrato_validado", "version": VERSION}}

    @staticmethod
    def _rejected(reason, usage):
        return {"reply": AgentReply(role=AgentRole.LABORATORIO,
                text="No hay un resultado validado para ese examen. Requiere revisión docente antes de incorporarse al caso.",
                provider="reglas", model="reglas", input_tokens=usage[0], output_tokens=usage[1], blocked=True),
                "evidence": [], "snapshot": {}, "reused": False,
                "validation": {"decision": reason, "version": VERSION}}
