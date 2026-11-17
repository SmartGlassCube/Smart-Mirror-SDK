import pytest

from glasscube.assistant.rag import VectorStore


def test_add_and_query_returns_nearest_chunk(tmp_path, embedder):
    store = VectorStore(path=str(tmp_path / "qdrant"))
    chunks = [
        {"text": "IEEE INSAT is the IEEE student branch at INSAT.", "source": "a.txt"},
        {"text": "The weather today is sunny with a light breeze.", "source": "b.txt"},
    ]
    embeddings = embedder.embed([c["text"] for c in chunks])

    store.add(chunks, embeddings)
    [query_vector] = embedder.embed("What is IEEE INSAT?")
    results = store.query(query_vector, top_k=1)

    assert len(results) == 1
    assert "IEEE INSAT" in results[0]["text"]
    assert results[0]["source"] == "a.txt"
    assert "score" in results[0]


def test_query_on_empty_store_returns_no_results(tmp_path):
    store = VectorStore(path=str(tmp_path / "qdrant"))

    results = store.query([0.0] * 384, top_k=3)

    assert results == []


def test_add_mismatched_lengths_raises(tmp_path):
    store = VectorStore(path=str(tmp_path / "qdrant"))

    with pytest.raises(ValueError):
        store.add([{"text": "a", "source": "s"}], [])
