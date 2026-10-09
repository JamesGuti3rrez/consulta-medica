"""Configuración leída de .env. No contiene secretos en código."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _split_keys(raw: str) -> tuple[str, ...]:
    if not raw:
        return ()
    normalized = raw.replace(";", ",").replace("\n", ",")
    return tuple(item.strip() for item in normalized.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str
    groq_api_keys: tuple[str, ...]
    groq_model: str
    groq_base_url: str
    llm_temperature: float
    llm_timeout_seconds: float
    provider_cooldown_seconds: float
    rag_service_url: str
    langsmith_tracing: bool
    langsmith_api_key: str
    langsmith_project: str
    trace_path: Path

    @property
    def auth_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_publishable_key)

    @property
    def llm_mode(self) -> str:
        return "groq-pool" if self.groq_api_keys else "local-development"


settings = Settings(
    supabase_url=os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
    supabase_publishable_key=os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip(),
    supabase_secret_key=os.getenv("SUPABASE_SECRET_KEY", "").strip(),
    groq_api_keys=_split_keys(os.getenv("GROQ_API_KEYS", "")),
    groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip(),
    groq_base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
    llm_temperature=float(os.getenv("AI_LLM_TEMPERATURE", "0")),
    llm_timeout_seconds=float(os.getenv("AI_LLM_TIMEOUT_SECONDS", "30")),
    provider_cooldown_seconds=float(os.getenv("AI_PROVIDER_COOLDOWN_SECONDS", "60")),
    rag_service_url=os.getenv("RAG_SERVICE_URL", "").strip().rstrip("/"),
    langsmith_tracing=os.getenv("LANGSMITH_TRACING", "false").lower() in {"1", "true", "yes", "on"},
    langsmith_api_key=os.getenv("LANGSMITH_API_KEY", "").strip(),
    langsmith_project=os.getenv("LANGSMITH_PROJECT", "paciente-virtual-sma").strip(),
    trace_path=ROOT_DIR / ".runtime" / "ai_traces.jsonl",
)
