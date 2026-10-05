"""Loads source documents and splits them into retrieval-sized chunks.

Must not import anything from `smartmirror.assistant.llm`.
"""

from pathlib import Path

_SUPPORTED_SUFFIXES = {".txt", ".md"}


class Chunker:
    """Loads .txt/.md files and splits them into overlapping text chunks."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load(self, path: str) -> list[dict]:
        """Load one file or a directory of files into chunks.

        Args:
            path: path to a .txt/.md file, or a directory containing such
                files (loaded non-recursively is fine for phase 1).

        Returns:
            A list of {"text": str, "source": str} dicts, one per chunk.
        """
        source_path = Path(path)
        if not source_path.exists():
            raise FileNotFoundError(f"No such file or directory: {path}")

        if source_path.is_dir():
            files = sorted(
                p for p in source_path.iterdir()
                if p.suffix.lower() in _SUPPORTED_SUFFIXES and p.is_file()
            )
        else:
            files = [source_path]

        chunks = []
        for file_path in files:
            text = file_path.read_text(encoding="utf-8")
            for chunk_text in self._split(text):
                chunks.append({"text": chunk_text, "source": str(file_path)})
        return chunks

    def _split(self, text: str) -> list[str]:
        """Split text into overlapping, whitespace-normalized chunks."""
        words = text.split()
        if not words:
            return []

        step = self.chunk_size - self.chunk_overlap
        chunks = []
        for start in range(0, len(words), step):
            chunk_words = words[start:start + self.chunk_size]
            if not chunk_words:
                break
            chunks.append(" ".join(chunk_words))
            if start + self.chunk_size >= len(words):
                break
        return chunks
