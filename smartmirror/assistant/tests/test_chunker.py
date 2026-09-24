import pytest

from smartmirror.assistant.rag import Chunker


def test_load_single_txt_file(tmp_path):
    file_path = tmp_path / "doc.txt"
    file_path.write_text("hello world " * 10, encoding="utf-8")

    chunks = Chunker(chunk_size=500, chunk_overlap=50).load(str(file_path))

    assert len(chunks) == 1
    assert chunks[0]["source"] == str(file_path)
    assert "hello world" in chunks[0]["text"]


def test_load_directory_loads_txt_and_md_only(tmp_path):
    (tmp_path / "a.txt").write_text("alpha content", encoding="utf-8")
    (tmp_path / "b.md").write_text("beta content", encoding="utf-8")
    (tmp_path / "c.json").write_text('{"ignored": true}', encoding="utf-8")

    chunks = Chunker().load(str(tmp_path))

    sources = [c["source"] for c in chunks]
    assert len(chunks) == 2
    assert any("a.txt" in source for source in sources)
    assert any("b.md" in source for source in sources)
    assert not any("c.json" in source for source in sources)


def test_load_missing_path_raises():
    with pytest.raises(FileNotFoundError):
        Chunker().load("/no/such/path/exists")


def test_split_respects_chunk_size_and_overlap():
    words = " ".join(f"word{i}" for i in range(120))
    chunker = Chunker(chunk_size=50, chunk_overlap=10)

    chunks = chunker._split(words)

    assert len(chunks) > 1
    # consecutive chunks should overlap: last words of one appear in the next
    first_tail = chunks[0].split()[-10:]
    second_head = chunks[1].split()[:10]
    assert first_tail == second_head


def test_chunk_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValueError):
        Chunker(chunk_size=10, chunk_overlap=10)
