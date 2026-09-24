"""Query-time retrieval: embed a query and fetch the closest chunks.

Thin by design -- fusing dense and (eventually) sparse signals is delegated
entirely to Qdrant's native Query API inside VectorStore.query. Retriever
does not implement its own BM25/RRF fusion.

Must not import anything from `smartmirror.assistant.llm`.
"""

from .embedder import Embedder
from .store import VectorStore


class Retriever:
    """Embeds a query and returns the most relevant chunks from a VectorStore."""

    def __init__(self, store: VectorStore, embedder: Embedder = None, top_k: int = 4):
        self.store = store
        self.embedder = embedder or Embedder()
        self.top_k = top_k

    def retrieve(self, query: str) -> list[str]:
        """Return the top_k chunk texts most relevant to `query`."""
        if not query or not query.strip():
            return []
        [query_embedding] = self.embedder.embed(query)
        results = self.store.query(query_embedding, top_k=self.top_k)
        return [result["text"] for result in results]
