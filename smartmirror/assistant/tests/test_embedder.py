from smartmirror.assistant.rag.embedder import EMBEDDING_DIM


def test_embed_single_string_returns_one_vector(embedder):
    vectors = embedder.embed("hello world")

    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIM


def test_embed_list_returns_parallel_vectors(embedder):
    texts = ["hello world", "IEEE INSAT", "smart mirror"]

    vectors = embedder.embed(texts)

    assert len(vectors) == len(texts)
    assert all(len(vector) == EMBEDDING_DIM for vector in vectors)


def test_embed_empty_list_returns_empty_list(embedder):
    assert embedder.embed([]) == []
