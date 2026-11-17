"""Vector storage and similarity search, backed by an embedded Qdrant.

Runs Qdrant in local on-disk mode (under `data_dir("qdrant")`) -- this is a
library, not a server, so the whole assistant boots with zero external
services running.

Must not import anything from `glasscube.assistant.llm`.
"""

import uuid

from qdrant_client import QdrantClient, models

from ...config import data_dir

DEFAULT_COLLECTION = "assistant_documents"
DENSE_VECTOR_NAME = "dense"


class VectorStore:
    """Local, on-disk Qdrant-backed store of document chunks and their embeddings."""

    def __init__(self, path=None, collection_name: str = DEFAULT_COLLECTION, dim: int = 384):
        self.collection_name = collection_name
        self.dim = dim
        self._client = QdrantClient(path=str(path or data_dir("qdrant")))
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

    def add(self, chunks: list[dict], embeddings: list[list[float]], ids: list[str] = None) -> None:
        """Add chunks and their embeddings to the store.

        Args:
            chunks: list of {"text": str, "source": str} dicts, as produced
                by Chunker.load.
            embeddings: parallel list of embedding vectors, one per chunk.
            ids: optional parallel list of point ids (str/UUID); random
                UUIDs are used if omitted. Pass deterministic ids (e.g.
                uuid5 of a stable key) when callers need idempotent upserts.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must be the same length")
        if not chunks:
            return
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in chunks]

        points = [
            models.PointStruct(
                id=id_,
                vector={DENSE_VECTOR_NAME: embedding},
                payload={"text": chunk["text"], "source": chunk.get("source", "")},
            )
            for id_, chunk, embedding in zip(ids, chunks, embeddings)
        ]
        self._client.upsert(collection_name=self.collection_name, points=points)

    def delete_by_source(self, source: str) -> None:
        """Delete every point whose payload["source"] equals `source`."""
        self._client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="source", match=models.MatchValue(value=source))]
                )
            ),
        )

    def clear(self) -> None:
        """Drop and recreate the collection (used when the embedding model changes)."""
        if self._client.collection_exists(self.collection_name):
            self._client.delete_collection(self.collection_name)
        self._ensure_collection()

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
