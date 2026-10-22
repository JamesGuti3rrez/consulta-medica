"""Completar historia autorizada, validar, persistir y reutilizar datos sintéticos.

Los hechos sintéticos no cambian el caso canónico ni cuentan para la evaluación.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re

from server.ai.agents.base import clean_reply
from server.ai.agents.invencion import invented_symptoms
from server.cases.supabase import CaseStoreError
from server.domain import AgentReply, AgentRole
from server.engine.disclosure.synthetic_scope import (
    OUT_OF_SCOPE_REPLY, candidate_topics, canonical_topic_exists, outside_clinical_scope, rapport_reply,
)
from server.engine.disclosure.policy import _normalize


@dataclass
class Completion:
    reply: AgentReply | None = None
    generated_ids: list[str] = field(default_factory=list)
    reused_ids: list[str] = field(default_factory=list)
    source: str = "curado"
    scope_rejected: bool = False
    validation_rejected: bool = False
    selector_usage: tuple[int, int] = (0, 0)
    rejection_reason: str | None = None


class PatientHistoryCompletion:
    def __init__(self, composer, store, output_guard):
        self.composer = composer
        self.store = store
        self.output_guard = output_guard

    @staticmethod
    def fingerprint(case):
        # No incluye protected; solo el código calcula el hash, no se pasa el caso al LLM.
        return hashlib.sha256(json.dumps(case, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def complete(self, *, question, case, context, forbidden_terms, session_id=None):
        input_tokens = output_tokens = 0
        provider_fallback = False
        provider = model = "reglas"
        stage = "seleccionar"

        def call(phase, payload):
            nonlocal input_tokens, output_tokens, provider, model, provider_fallback, stage
            stage = phase
            data, result = self.composer.call(phase, payload)
            input_tokens += result.input_tokens
            output_tokens += result.output_tokens
            provider_fallback |= result.fallback_used
            provider, model = result.provider, result.model
            return data

        def finish(text=None, *, generated=(), reused=(), source="curado", scope=False, rejected=False, curated_ids=None):
            reply = None if text is None else AgentReply(
                role=AgentRole.PACIENTE, text=text, provider=provider, model=model,
                evidence_ids=([] if scope or rejected else
                              curated_ids if curated_ids is not None else
                              [item["evidence_id"] for item in context.get("retrieved_evidence", [])]),
                input_tokens=input_tokens, output_tokens=output_tokens, fallback_used=provider_fallback,
            )
            return Completion(reply, list(generated), list(reused),
                              "fuera_de_alcance" if scope else source, scope, rejected)

        if outside_clinical_scope(question):
            return finish(OUT_OF_SCOPE_REPLY, scope=True)
        social = rapport_reply(question)
        if social:
            return finish(social, source="conversacional")
        candidates = candidate_topics(question)
        # El modelo nunca ve preguntas anteriores, instrucciones o datos clínicos no autorizados.
        authorized = {key: context.get(key) for key in (
            "patient", "public_evidence", "revealed_evidence", "retrieved_evidence",
        )}
        payload = {"pregunta": question, "contexto": authorized, "claves_permitidas": candidates,
                   "ano_actual": datetime.now(timezone.utc).year}
        try:
            selection = call("seleccionar", payload)
            if selection.get("alcance") == "fuera":
                return finish(OUT_OF_SCOPE_REPLY, scope=True)
            if selection.get("alcance") == "social":
                return finish("No entendí bien lo último, doctor. ¿Me lo puede repetir?", source="conversacional")
            keys = selection.get("claves")
            if selection.get("alcance") == "caso" and isinstance(keys, list):
                # Una clave fuera de las permitidas nunca se genera: se descarta. Si no queda ninguna, la
                # pregunta es del caso pero no pide un dato sintético (p. ej. el motivo de consulta).
                keys = list(dict.fromkeys(key for key in keys if key in candidates))
            if selection.get("alcance") == "curado" or (selection.get("alcance") == "caso" and keys == []):
                result = finish()
                # Registrar llamadas del selector aunque se responda con el agente normal.
                result.selector_usage = (input_tokens, output_tokens)
                return result
            if (selection.get("alcance") != "caso" or not isinstance(keys, list)
                    or not 1 <= len(keys) <= 3 or any(not isinstance(k, str) for k in keys)
                    or len(set(keys)) != len(keys) or not set(keys).issubset(candidates)):
                raise ValueError("Selección fuera de los campos permitidos.")
            curated_topics = [key for key in keys if canonical_topic_exists(case, key)]
            keys = [key for key in keys if key not in curated_topics]
            if not keys:
                result = finish()
                result.selector_usage = (input_tokens, output_tokens)
                return result
            if any(key in {"medicacion_habitual", "inicio_antecedentes", "reaccion_diagnostico"} for key in keys):
                # No fabricar un tratamiento o una fecha para una enfermedad que no consta.
                known_history = [item for item in [*context.get("public_evidence", []),
                                                 *context.get("revealed_evidence", [])]
                                 if item.get("category") == "antecedente"]
                retrieved_ids = {item["evidence_id"] for item in context.get("retrieved_evidence", [])}
                known_history.extend(item for item in case.get("on_request", [])
                                     if item.get("category") == "antecedente"
                                     and item.get("evidence_id") in retrieved_ids)
                if not any(not re.search(r"\b(?:no|sin|niega|desconoce)\b", item.get("text", ""), re.I)
                           for item in known_history):
                    raise ValueError("Falta un antecedente conocido para completar esos campos.")
            if "impacto_vida_diaria" in keys:
                visible_text = _normalize(json.dumps(authorized, ensure_ascii=False))
                question_text = _normalize(question)
                # Una pregunta que adivina un hallazgo no lo vuelve visible al generador.
                skin_terms = ("papula", "lesion", "bulto", "mancha")
                if (any(word in question_text for word in skin_terms)
                        and not any(word in visible_text for word in skin_terms)):
                    raise ValueError("El hallazgo preguntado todavía no se ha revelado.")
                for word in ("herida",):
                    if word in question_text and word not in visible_text:
                        raise ValueError("El hallazgo preguntado todavía no se ha revelado.")
            fingerprint = self.fingerprint(case)
            rows = {row["clave"]: row for row in self.store.list_for_case(case["case_id"])}
            for key in keys:
                if key in rows and not self._reusable(rows[key], fingerprint):
                    # Ni un dato rechazado ni uno de otra versión puede regenerarse a escondidas.
                    raise CaseStoreError("Un dato adicional del caso requiere revisión antes de reutilizarse.")
            existing = {key: row["contenido"]["respuesta"] for key, row in rows.items()
                        if self._reusable(row, fingerprint)}
            missing = [key for key in keys if key not in existing]
            generated_rows = []
            if missing:
                generation_payload = {**payload, "claves_solicitadas": missing, "datos_fijados": existing}
                for attempt in range(2):
                    try:
                        proposal = call("generar", generation_payload)
                        generation_model = model
                        data = self._validate_proposal(proposal, missing, case, forbidden_terms, context)
                        verdict = call("validar", {**generation_payload, "candidatos": data})
                        if any(verdict.get(key) is not True for key in (
                            "coherente", "dentro_alcance", "sin_cambios_clinicos", "responde_pregunta",
                        )):
                            raise ValueError("Revisa coherencia y responde solo los campos solicitados, sin dosis nuevas.")
                        break
                    except (ValueError, TypeError, KeyError) as exc:
                        if attempt:
                            raise
                        # Corregir una vez, sin guardar el borrador rechazado ni relajar las reglas.
                        generation_payload = {**generation_payload, "correcciones": [str(exc)[:160]]}
                for item in data:
                    generated_rows.append({
                        "case_id": case["case_id"], "clave": item["clave"],
                        "pregunta_origen": question, "modelo": generation_model,
                        "estado_revision": "pendiente",
                        "contenido": {"respuesta": clean_reply(item["respuesta"]), "origen": "sintetico",
                                      "caso_hash": fingerprint, "validacion_automatica": True,
                                      "session_id_origen": session_id, "version": 1},
                    })
                self.store.insert_missing(generated_rows)
                # Leer siempre el ganador de la clave única, también si otra sesión insertó primero.
                rows = {row["clave"]: row for row in self.store.list_for_case(case["case_id"])}
            chosen = [rows.get(key) for key in keys]
            if any(row is None or not self._reusable(row, fingerprint) for row in chosen):
                raise CaseStoreError("No se pudo verificar el guardado de los datos adicionales.")
            for row in chosen:
                self._validate_text(row["clave"], row["contenido"]["respuesta"], case, forbidden_terms, context)
            # Respuesta basada en hechos ya persistidos, no en el borrador del LLM.
            # La concatenación conserva exactamente nombres y cifras en sesiones futuras.
            curated_records = self._curated_records(case, context, curated_topics)
            curated = [item["text"] for item in curated_records if item.get("text")]
            answer = " ".join([*curated, *(row["contenido"]["respuesta"] for row in chosen)])
            ok, _ = self.output_guard.validate(answer, forbidden_terms)
            if not ok:
                raise ValueError("Respuesta no autorizada.")
            ids = [str(row["id"]) for row in chosen]
            generated = [str(row["id"]) for row in chosen if row["clave"] in missing
                         and row["contenido"].get("session_id_origen") == session_id]
            return finish(answer, generated=generated,
                          reused=[fact_id for fact_id in ids if fact_id not in generated],
                          source="mixto" if curated else "sintetico",
                          curated_ids=[item["evidence_id"] for item in curated_records])
        except (ValueError, TypeError, KeyError) as exc:
            # No persistir JSON inválido ni volver a convertir un dato ausente en un "No".
            result = finish("No entendí bien, doctor. ¿Me puede hacer la pregunta de otra manera?", rejected=True)
            result.rejection_reason = f"{stage}:{type(exc).__name__}:{str(exc)[:160]}"
            return result

    def _validate_proposal(self, proposal, missing, case, forbidden_terms, context):
        data = proposal.get("datos")
        if (not isinstance(data, list) or len(data) != len(missing)
                or any(not isinstance(item, dict) or set(item) != {"clave", "respuesta"} for item in data)):
            raise ValueError("Devuelve datos con exactamente clave y respuesta para todos los campos solicitados.")
        if (any(not isinstance(item["clave"], str) for item in data)
                or {item["clave"] for item in data} != set(missing)):
            raise ValueError("Usa exactamente las claves solicitadas.")
        for item in data:
            if item["clave"] == "inicio_antecedentes" and isinstance(item["respuesta"], str):
                # Algunos modelos entregan "2013, 55". El año es el hecho sintético;
                # la edad se deriva de los datos conocidos y se expresa como paciente.
                match = re.fullmatch(r"\s*((?:19|20)\d{2})(?:\s*[,;]\s*\d{1,3})?\s*[.]?", item["respuesta"])
                if match:
                    year = int(match.group(1))
                    age_then = case["public"]["patient"]["age_years"] - (datetime.now(timezone.utc).year - year)
                    item["respuesta"] = (f"Me lo diagnosticaron en {year}, cuando tenía aproximadamente "
                                         f"{age_then} años.")
            self._validate_text(item["clave"], item["respuesta"], case, forbidden_terms, context)
        return data

    @staticmethod
    def _curated_records(case, context, topics):
        """Entregar los datos curados solicitados, no toda coincidencia de palabras."""
        canonical = {item["evidence_id"]: item for item in [
            *case["public"].get("items", []), *case.get("on_request", []),
        ]}
        result = {}
        for item in [*context.get("public_evidence", []), *context.get("revealed_evidence", []),
                     *context.get("retrieved_evidence", [])]:
            original = canonical.get(item["evidence_id"])
            if original is not None and any(canonical_topic_exists(
                {"public": {"items": [original]}, "on_request": []}, topic
            ) for topic in topics):
                result[item["evidence_id"]] = item
        return list(result.values())

    @staticmethod
    def _reusable(row, fingerprint):
        content = row.get("contenido")
        return (row.get("estado_revision") in {"pendiente", "aprobado"}
                and isinstance(content, dict) and content.get("caso_hash") == fingerprint
                and content.get("origen") == "sintetico" and content.get("validacion_automatica") is True
                and isinstance(content.get("respuesta"), str) and bool(content["respuesta"].strip()))

    def _validate_text(self, key, text, case, forbidden_terms, context):
        if not isinstance(text, str) or not 3 <= len(text.strip()) <= 700:
            raise ValueError("Respuesta inválida.")
        if re.fullmatch(r"\W*(?:no|s[ií]|nada|ningun[oa])\W*", text, re.I):
            raise ValueError("Un dato sintético debe ser explícito y reutilizable.")
        if any(term in text.casefold() for term in ("no recuerdo", "no consta", "no se registra", "no sé")):
            raise ValueError("Dato sin completar.")
        if not self.output_guard.validate(text, forbidden_terms)[0] or outside_clinical_scope(text):
            raise ValueError("Contenido fuera de alcance.")
        if invented_symptoms(text, context):
            raise ValueError("El complemento no puede añadir síntomas nuevos.")
        if re.search(r"\b(?:deber[ií]a|recomiendo|prescribo|t[oó]mese|aumente la dosis)\b", text, re.I):
            raise ValueError("No se permiten prescripciones.")
        if key == "medicacion_habitual" and re.search(
            r"\b(?:mg|ml|mcg|miligramos?|mililitros?|microgramos?|cada|comprimidos?)\b", text, re.I
        ):
            raise ValueError("Para medicacion_habitual indica solo el nombre; elimina dosis, unidades y frecuencia de toma.")
        if key == "inicio_antecedentes":
            age = case["public"]["patient"]["age_years"]
            year = datetime.now(timezone.utc).year
            for value in re.findall(r"\b\d{4}\b", text):
                if not year - age <= int(value) <= year:
                    raise ValueError("Cronología imposible.")
            for value in re.findall(r"\b(\d+)\s+a[ñn]os\b", text):
                if int(value) > age:
                    raise ValueError("Cronología imposible.")
            dates = re.findall(r"\b((?:19|20)\d{2})\b", text)
            ages = re.findall(r"\b(?:a los|ten[ií]a(?: aproximadamente| unos)?|con)\s+(\d+)\s+a[ñn]os", text, re.I)
            if len(dates) == 1 and len(ages) == 1:
                expected = age - (year - int(dates[0]))
                if abs(int(ages[0]) - expected) > 1:
                    raise ValueError("El año y la edad al diagnóstico no coinciden con la edad actual.")
