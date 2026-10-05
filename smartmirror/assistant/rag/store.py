"""Vector storage and similarity search, backed by an embedded Qdrant.

Runs Qdrant in local on-disk mode (`path=".qdrant_data"`) -- this is a
library, not a server, so the whole assistant boots with zero external
services running.

Must not import anything from `smartmirror.assistant.llm`.
"""

import uuid

from qdrant_client import QdrantClient, models

DEFAULT_PATH = ".qdrant_data"
DEFAULT_COLLECTION = "assistant_documents"
DENSE_VECTOR_NAME = "dense"


class VectorStore:
    """Local, on-disk Qdrant-backed store of document chunks and their embeddings."""

    def __init__(self, path: str = DEFAULT_PATH, collection_name: str = DEFAULT_COLLECTION, dim: int = 384):
        self.collection_name = collection_name
        self.dim = dim
        self._client = QdrantClient(path=path)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if self._client.collection_exists(self.collection_name):
            return
        self._client.create_collection(
            collection_name=self.collection_name,
            # Named dense vector today; a named sparse vector (e.g. "bm25")
            # can be added alongside it later so Retriever can run hybrid
            # queries through Qdrant's own fusion instead of Python code.
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(size=self.dim, distance=models.Distance.COSINE),
            },
        )

    def add(self, chunks: list[dict], embeddings: list[list[float]]) -> None:
        """Add chunks and their embeddings to the store.

        Args:
            chunks: list of {"text": str, "source": str} dicts, as produced
                by Chunker.load.
            embeddings: parallel list of embedding vectors, one per chunk.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must be the same length")
        if not chunks:
            return

        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector={DENSE_VECTOR_NAME: embedding},
                payload={"text": chunk["text"], "source": chunk.get("source", "")},
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        self._client.upsert(collection_name=self.collection_name, points=points)

    def query(self, query_embedding: list[float], top_k: int = 4) -> list[dict]:
        """Find the top_k chunks nearest to query_embedding.

        Uses Qdrant's native Query API (`query_points`) so that adding a
        sparse vector later only means adding a `prefetch` + fusion query
        here -- no hand-rolled BM25/RRF fusion in Python.

        Returns:
            A list of {"text": str, "source": str, "score": float} dicts,
            best match first.
        """
        result = self._client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            using=DENSE_VECTOR_NAME,
            limit=top_k,
        )
        return [
            {"text": point.payload.get("text", ""), "source": point.payload.get("source", ""), "score": point.score}
            for point in result.points
        ]
