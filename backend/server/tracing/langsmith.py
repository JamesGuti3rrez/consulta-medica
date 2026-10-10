from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


class LangSmithObserver:
    """Observabilidad opcional; una caída de LangSmith no rompe la simulación."""

    def __init__(self, *, enabled: bool, api_key: str, project: str):
        self.enabled = enabled and bool(api_key)
        self.api_key = api_key
        self.project = project
        self._client = None
        if self.enabled:
            try:
                from langsmith import Client  # type: ignore
                self._client = Client(api_key=api_key)
            except Exception:
                self.enabled = False

    def record_turn(self, *, inputs: dict, outputs: dict, metadata: dict) -> None:
        if not self.enabled or self._client is None:
            return
        run_id = uuid4()
        try:
            start = datetime.now(timezone.utc)
            self._client.create_run(
                name="sma_turn",
                inputs=inputs,
                run_type="chain",
                project_name=self.project,
                id=run_id,
                start_time=start,
                extra={"metadata": metadata},
            )
            self._client.update_run(
                run_id,
                outputs=outputs,
                end_time=datetime.now(timezone.utc),
            )
        except Exception:
            return
