from smartmirror.assistant.rag import Chunker, Retriever, VectorStore


def test_retrieve_returns_relevant_chunk_texts(tmp_path, embedder, seed_corpus_path):
    store = VectorStore(path=str(tmp_path / "qdrant"))
    chunks = Chunker().load(seed_corpus_path)
    embeddings = embedder.embed([c["text"] for c in chunks])
    store.add(chunks, embeddings)

    retriever = Retriever(store=store, embedder=embedder, top_k=2)
    results = retriever.retrieve("What is IEEE INSAT?")

    assert 0 < len(results) <= 2
    assert all(isinstance(text, str) for text in results)
    assert any("IEEE INSAT" in text for text in results)


def test_retrieve_empty_query_returns_no_results(tmp_path, embedder):
    store = VectorStore(path=str(tmp_path / "qdrant"))
    retriever = Retriever(store=store, embedder=embedder)

    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []
