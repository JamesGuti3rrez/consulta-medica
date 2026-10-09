from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class LocalTraceLogger:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def record(self, event: dict) -> None:
        payload = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
