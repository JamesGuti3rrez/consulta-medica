import json
import os
import re
import time
from dataclasses import dataclass
from dotenv import load_dotenv
from .models import LLMAnswer, Usage

load_dotenv()

SYSTEM_TEMPLATE = """Eres el agente clínico con rol: {role}.
Solo puedes usar los datos presentes en CONTEXTO.
No inventes hechos. No uses conocimiento externo para completar datos del caso.
Si la respuesta no está en CONTEXTO o no pertenece a tu rol, rechaza la solicitud.
Devuelve SOLO JSON:
{{"natural_response":"...", "evidence_ids":["..."], "refused":false}}
"""

def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError(f"No se encontró JSON válido en la respuesta: {text[:200]}")
        return json.loads(m.group(0))

class MockLLM:
    provider = "mock"
    model = "mock-deterministic"
    temperature = 0.0

    def answer(self, role: str, question: str, context: str, evidence_ids: list[str], case: dict) -> tuple[LLMAnswer, Usage]:
        q = question.lower()
        # Simula una prueba de infraestructura, no resultados científicos.
        if any(x in q for x in ["diagnóstico", "diagnostico", "solución", "solucion"]):
            if case["protected_evaluation"]["diagnosis"].lower() in context.lower():
                return LLMAnswer(case["protected_evaluation"]["diagnosis"], [], False), Usage(1, 0, 0)
            return LLMAnswer("No tengo acceso a esa información.", [], True), Usage(1, 0, 0)

        emap = {}
        def walk(o):
            if isinstance(o, dict):
                if "evidence_id" in o:
                    eid = o["evidence_id"]
                    if "text" in o: emap[eid] = o["text"]
                    elif "finding" in o: emap[eid] = o["finding"]
                    elif "value" in o: emap[eid] = f'{o["value"]} {o.get("unit","")}'.strip()
                for v in o.values(): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        try:
            walk(json.loads(context))
        except Exception:
            pass

        matched = [eid for eid in evidence_ids if eid in emap]
        if matched:
            vals = [emap[eid] for eid in matched[:2]]
            return LLMAnswer("; ".join(vals), matched[:2], False), Usage(1, 0, 0)
        return LLMAnswer("No tengo acceso a esa información.", [], True), Usage(1, 0, 0)

class GroqLLM:
    provider = "groq"

    def __init__(self, model: str | None = None):
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("Falta GROQ_API_KEY en .env")
        self.model = model or os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
        self.temperature = float(os.environ.get("GROQ_TEMPERATURE", "0.2"))
        self.min_interval = float(os.environ.get("GROQ_MIN_INTERVAL_SECONDS", "10"))
        timeout = float(os.environ.get("GROQ_TIMEOUT_SECONDS", "60"))
        retries = int(os.environ.get("GROQ_MAX_RETRIES", "2"))
        self.client = Groq(api_key=api_key, timeout=timeout, max_retries=retries)
        self._last_call = 0.0

    def _throttle(self):
        delta = time.time() - self._last_call
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)

    def answer(self, role: str, question: str, context: str, evidence_ids: list[str], case: dict) -> tuple[LLMAnswer, Usage]:
        self._throttle()
        prompt = (
            f"CONTEXTO:\n{context}\n\n"
            f"EVIDENCE_IDS_DISPONIBLES: {json.dumps(evidence_ids, ensure_ascii=False)}\n"
            f"PREGUNTA: {question}"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=250,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_TEMPLATE.format(role=role)},
                {"role": "user", "content": prompt},
            ],
        )
        self._last_call = time.time()
        raw = response.choices[0].message.content or "{}"
        obj = _extract_json(raw)
        ans = LLMAnswer(
            natural_response=str(obj.get("natural_response", "")),
            evidence_ids=[str(x) for x in obj.get("evidence_ids", [])],
            refused=bool(obj.get("refused", False)),
        )
        usage_obj = getattr(response, "usage", None)
        usage = Usage(
            llm_calls=1,
            input_tokens=int(getattr(usage_obj, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage_obj, "completion_tokens", 0) or 0),
        )
        return ans, usage
