from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .retrieval_log import RetrievalLogger
from .retriever import RetrievalResult, SecureRAGRetriever


class RAGService:
    def __init__(self, index_root: Path, log_path: Path):
        self.retriever = SecureRAGRetriever(index_root)
        self.logger = RetrievalLogger(log_path)

    def health(self) -> dict[str, Any]:
        return self.retriever.status()

    def reload(self) -> dict[str, Any]:
        snapshot = self.retriever.reload()
        return {
            "ready": True,
            "fingerprint": snapshot.fingerprint,
            "documents": len(snapshot.documents),
            "index_dir": str(snapshot.index_dir),
        }

    def _search(
        self,
        search_type: str,
        method: Callable[..., list[RetrievalResult]],
        kwargs: dict[str, Any],
    ) -> list[RetrievalResult]:
        call_kwargs = dict(kwargs)
        session_id = call_kwargs.pop("session_id", None)
        agent = call_kwargs.pop("agent", None)
        results = method(**call_kwargs)
        self._log(search_type, call_kwargs, results, session_id=session_id, agent=agent)
        return results

    def evidence_search(self, **kwargs: Any) -> list[RetrievalResult]:
        return self._search("evidence", self.retriever.search_evidence, kwargs)

    def case_search(self, **kwargs: Any) -> list[RetrievalResult]:
        return self._search("cases", self.retriever.search_cases, kwargs)

    def knowledge_search(self, **kwargs: Any) -> list[RetrievalResult]:
        return self._search("knowledge", self.retriever.search_knowledge, kwargs)

    def _log(
        self,
        search_type: str,
        filters: dict[str, Any],
        results: list[RetrievalResult],
        *,
        session_id: str | None,
        agent: str | None,
    ) -> None:
        status = self.retriever.status()
        safe_filters = dict(filters)
        query = safe_filters.pop("query", "")
        self.logger.write(
            {
                "search_type": search_type,
                "session_id": session_id,
                "agent": agent,
                "query": query,
                "filters": safe_filters,
                "results": [
                    {
                        "case_id": result.case_id,
                        "evidence_id": result.evidence_id,
                        "score": result.score,
                        "rank": rank,
                    }
                    for rank, result in enumerate(results, start=1)
                ],
                "index_fingerprint": status.get("fingerprint"),
                "embedding": status.get("embedding"),
            }
        )
