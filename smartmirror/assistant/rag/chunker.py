"""Load and chunk .txt, .md, and .csv files into text segments."""


class Chunker:
    """Reads documents from disk and splits them into fixed-size chunks."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64) -> None:
        pass

    def load(self, path: str) -> list[str]:
        """Load all supported files under *path* and return raw text chunks."""
        pass
