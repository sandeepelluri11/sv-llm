"""A small vector store wrapper with on-disk persistence.

The production path uses OpenAI embeddings; tests pass ``DeterministicFakeEmbedding`` so
indexing and retrieval are exercised without network access.
"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore


class SpecStore:
    def __init__(self, embeddings: Embeddings) -> None:
        self._embeddings = embeddings
        self._store = InMemoryVectorStore(embeddings)
        self._count = 0

    @property
    def size(self) -> int:
        return self._count

    def add(self, documents: list[Document]) -> None:
        if not documents:
            return
        self._store.add_documents(documents)
        self._count += len(documents)

    def search(self, query: str, k: int = 6, kind: str | None = None) -> list[Document]:
        """Return the top-k chunks, optionally restricted to ``kind`` (spec or rtl)."""
        if kind is None:
            return self._store.similarity_search(query, k=k)
        return self._store.similarity_search(
            query, k=k, filter=lambda doc: doc.metadata.get("kind") == kind
        )

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._store.dump(str(path))
        path.with_suffix(".meta.json").write_text(json.dumps({"count": self._count}))

    @classmethod
    def load(cls, path: Path, embeddings: Embeddings) -> SpecStore:
        path = Path(path)
        instance = cls(embeddings)
        instance._store = InMemoryVectorStore.load(str(path), embeddings)
        meta = path.with_suffix(".meta.json")
        if meta.exists():
            instance._count = json.loads(meta.read_text()).get("count", 0)
        return instance


def format_context(documents: list[Document]) -> list[str]:
    """Render retrieved chunks with their provenance so agents can cite them."""
    rendered: list[str] = []
    for doc in documents:
        meta = doc.metadata
        if meta.get("kind") == "rtl":
            label = f"[rtl {meta.get('source', '?')} module={meta.get('module') or '?'}]"
        else:
            label = f"[spec {meta.get('source', '?')} section={meta.get('section') or 'top'}]"
        rendered.append(f"{label}\n{doc.page_content.strip()}")
    return rendered
