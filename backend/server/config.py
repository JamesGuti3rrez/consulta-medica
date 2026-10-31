"""Configuración leída del archivo .env en la raíz del repositorio. No contiene secretos en código."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
load_dotenv(ROOT_DIR / ".env")


def _split_keys(raw: str) -> tuple[str, ...]:
    if not raw:
        return ()
    normalized = raw.replace(";", ",").replace("\n", ",")
    return tuple(item.strip() for item in normalized.split(",") if item.strip())


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


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
    rag_backend: str
    rag_embedded_enabled: bool
    rag_index_dir: Path
    rag_log_path: Path
    rag_http_token: str
    langsmith_tracing: bool
    langsmith_api_key: str
    langsmith_project: str
    trace_path: Path
    session_store: str
    case_store: str = "local"
    synthetic_case_data: bool = False
    history_enabled: bool = False
    tts_provider: str = ""

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
    rag_backend=os.getenv("RAG_BACKEND", "local").strip().lower(),
    rag_embedded_enabled=_flag("RAG_EMBEDDED", "true"),
    rag_index_dir=(ROOT_DIR / os.getenv("RAG_INDEX_DIR", "data/indexes/lightrag")).resolve(),
    rag_log_path=(ROOT_DIR / os.getenv("RAG_LOG_PATH", "backend/logs/rag_retrieval.jsonl")).resolve(),
    rag_http_token=os.getenv("RAG_HTTP_TOKEN", "").strip(),
    langsmith_tracing=_flag("LANGSMITH_TRACING", "false"),
    langsmith_api_key=os.getenv("LANGSMITH_API_KEY", "").strip(),
    langsmith_project=os.getenv("LANGSMITH_PROJECT", "paciente-virtual-sma").strip(),
    trace_path=(ROOT_DIR / os.getenv("AI_TRACE_PATH", "backend/logs/ai_traces.jsonl")).resolve(),
    # memoria (desarrollo y pruebas) o supabase (despliegue con varias instancias, como Vercel).
    session_store=os.getenv("SESSION_STORE", "memoria").strip().lower(),
    case_store=os.getenv("CASE_STORE", "local").strip().lower(),
    synthetic_case_data=_flag("SYNTHETIC_CASE_DATA", "false"),
    # Guardar las consultas de los alumnos con sesión en «Mis simulaciones»; requiere la migración 0001.
    history_enabled=_flag("HISTORIAL_ALUMNOS", "false"),
    # Voz neuronal del simulador: «edge» la activa (local y Vercel, provisional hasta Azure Speech); vacío, el navegador usa su propia voz.
    tts_provider=os.getenv("TTS_PROVIDER", "").strip().lower(),
)
