"""Main Assistant orchestrator class for Smart Mirror SDK."""


class Assistant:
    """High-level orchestrator that wires together LLM, RAG, tools, STT, and TTS."""

    def __init__(
        self,
        api_key: str,
        url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        documents: str | None = None,
        tools: list | None = None,
        stt: bool = False,
        tts: bool = False,
        system_prompt: str | None = None,
        language: str = "en",
    ) -> None:
        pass

    def chat(self, message: str) -> str:
        """Send a text message and return the assistant's text reply."""
        pass

    def voice_chat(self) -> str:
        """Capture speech input, process it, and return the assistant's text reply."""
        pass

    def add_documents(self, path: str) -> None:
        """Index documents at *path* into the RAG vector store."""
        pass

    def reset_history(self) -> None:
        """Clear the conversation history."""
        pass
