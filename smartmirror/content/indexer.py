"""Keeps the Mongo-derived Qdrant collection in sync with one doc at a time.

Reuses the assistant's own Chunker/Embedder/VectorStore (smartmirror.assistant.rag)
-- this is not a second RAG stack, just a different source feeding the same
primitives into a different Qdrant collection than the seed-corpus one.
"""

import uuid

from smartmirror.assistant.rag import Chunker, Embedder, VectorStore

from . import templates

# Fixed namespace so uuid5(NAMESPACE, key) is stable across process restarts.
NAMESPACE = uuid.UUID("f0f8a37e-7f0c-4c1a-9b8e-9c5a2b6d0a11")


def source_id(collection: str, doc_id) -> str:
    return f"{collection}:{doc_id}"


def point_id(source: str, chunk_index: int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{source}:{chunk_index}"))


class ContentIndexer:
    """upsert(collection, doc) / remove(source_id) against a VectorStore."""

    def __init__(self, store: VectorStore, embedder: Embedder = None, chunker: Chunker = None, chapters=None):
        self.store = store
        self.embedder = embedder or Embedder()
        self.chunker = chunker or Chunker()
        # Callable -> {chapter key: name}, so a chapter's content says which chapter it's from.
        self.chapters = chapters or dict

    def upsert(self, collection: str, doc: dict) -> None:
        """Delete any existing points for this doc, then re-chunk, re-embed, and re-insert."""
        source = source_id(collection, doc["_id"])
        self.store.delete_by_source(source)

        text = templates.render(collection, doc, self.chapters())
        if not text or not text.strip():
            return

        chunks = self.chunker.split(text, source=source)
        if not chunks:
            return

        embeddings = self.embedder.embed([chunk["text"] for chunk in chunks])
        ids = [point_id(source, i) for i in range(len(chunks))]
        self.store.add(chunks, embeddings, ids=ids)

    def remove(self, source: str) -> None:
        self.store.delete_by_source(source)
