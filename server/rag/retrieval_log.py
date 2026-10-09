from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class RetrievalLogger:
    def __init__(self, path: Path):
        self.path = path
        self._lock = Lock()

    def write(self, payload: dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
