import time
from abc import ABC, abstractmethod
from ..models import TurnResult
from ..verifier import (
    protected_in_context, contains_protected, cross_role_leak,
    authorized_correct, correct_refusal, apply_guardrail
)

class Strategy(ABC):
    name = "base"
    uses_runtime_guardrail = False

    def __init__(self, llm):
        self.llm = llm

    @abstractmethod
    def build_context(self, case: dict, role: str, question: str):
        ...

    def run_turn(self, case: dict, q: dict, repeat: int) -> TurnResult:
        t0 = time.perf_counter()
        context, context_ids = self.build_context(case, q["role"], q["question"])
        answer, usage = self.llm.answer(q["role"], q["question"], context, context_ids, case)

        raw_text = answer.natural_response
        raw_ids = list(answer.evidence_ids)
        raw_diag = contains_protected(raw_text, case)

        final_text = raw_text
        final_ids = raw_ids
        blocked = False
        refused = answer.refused

        if self.uses_runtime_guardrail:
            final_text, final_ids, blocked, forced_refusal = apply_guardrail(
                raw_text, raw_ids, q["role"], case
            )
            refused = refused or forced_refusal

        final_diag = contains_protected(final_text, case)
        cross_final = cross_role_leak(final_text, final_ids, q["role"], case)
        auth_correct = authorized_correct(q, final_ids, final_text, case)
        corr_refusal = correct_refusal(q, refused, final_diag, cross_final)
        traceable = all([
            self.name, q.get("id"), q.get("role"), isinstance(context_ids, list),
            isinstance(final_ids, list)
        ])
        latency = (time.perf_counter() - t0) * 1000

        return TurnResult(
            strategy=self.name,
            provider=self.llm.provider,
            model=self.llm.model,
            temperature=self.llm.temperature,
            case_id=case["case_id"],
            repeat=repeat,
            question_id=q["id"],
            kind=q["kind"],
            role=q["role"],
            question=q["question"],
            context_text=context,
            context_evidence_ids=context_ids,
            response_raw=raw_text,
            response_final=final_text,
            evidence_ids=final_ids,
            refused=refused,
            protected_context_exposure=protected_in_context(context, case),
            diagnostic_leak_raw=raw_diag,
            diagnostic_leak_final=final_diag,
            cross_role_leak_final=cross_final,
            authorized_correct=auth_correct,
            correct_refusal=corr_refusal,
            guardrail_blocked=blocked,
            traceable=bool(traceable),
            latency_ms=latency,
            llm_calls=usage.llm_calls,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
