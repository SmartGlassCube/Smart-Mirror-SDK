"""Hybrid retrieval: BM25 sparse search + dense vector search fused with RRF."""


class Retriever:
    """Combines BM25 and vector-store results using Reciprocal Rank Fusion (RRF)."""

    def __init__(self, store: object, embedder: object, top_k: int = 5) -> None:
        pass

    def retrieve(self, query: str) -> list[str]:
        """Return the *top_k* most relevant chunks for *query*."""
        pass

    def _bm25_rank(self, query: str) -> list[tuple[str, float]]:
        """Return BM25-ranked (chunk, score) pairs for *query*."""
        pass

    def _vector_rank(self, query: str) -> list[tuple[str, float]]:
        """Return vector-similarity-ranked (chunk, score) pairs for *query*."""
        pass

    def _rrf_fuse(
        self,
        bm25_results: list[tuple[str, float]],
        vector_results: list[tuple[str, float]],
        k: int = 60,
    ) -> list[str]:
        """Fuse two ranked lists with Reciprocal Rank Fusion and return top chunks."""
        pass
