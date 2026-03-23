"""ChromaDB vector store (embedded mode, no server required)."""


class VectorStore:
    """Persists and queries document embeddings via ChromaDB in embedded mode."""

    def __init__(self, collection_name: str = "assistant", persist_dir: str = ".chroma") -> None:
        pass

    def add(self, chunks: list[str], embeddings: list[list[float]]) -> None:
        """Store *chunks* alongside their *embeddings*."""
        pass

    def query(self, embedding: list[float], top_k: int = 5) -> list[str]:
        """Return the *top_k* most similar chunks for the given *embedding*."""
        pass
