"""sentence-transformers wrapper for generating dense embeddings."""


class Embedder:
    """Produces dense vector embeddings using a sentence-transformers model."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        pass

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per entry in *texts*."""
        pass
