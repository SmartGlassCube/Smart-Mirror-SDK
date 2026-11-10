"""Dense text embeddings via sentence-transformers.

Must not import anything from `smartmirror.assistant.llm`.
"""

from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class Embedder:
    """Wraps a sentence-transformers model to produce 384-dim embeddings."""

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.dim = EMBEDDING_DIM
        self._model = SentenceTransformer(model_name)

    def embed(self, texts) -> list[list[float]]:
        """Embed one string or a list of strings.

        Args:
            texts: a single string, or a list of strings.

        Returns:
            A list of embedding vectors (list[float]), one per input text,
            even when a single string was passed in.
        """
        single_input = isinstance(texts, str)
        inputs = [texts] if single_input else list(texts)

        if not inputs:
            return []

        vectors = self._model.encode(inputs, convert_to_numpy=True)
        return [vector.tolist() for vector in vectors]
