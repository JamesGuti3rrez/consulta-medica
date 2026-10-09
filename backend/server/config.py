"""Configuración leída del archivo .env en la raíz del repositorio."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str

    @property
    def auth_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_publishable_key)


settings = Settings(
    supabase_url=os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
    supabase_publishable_key=os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip(),
    supabase_secret_key=os.getenv("SUPABASE_SECRET_KEY", "").strip(),
)
