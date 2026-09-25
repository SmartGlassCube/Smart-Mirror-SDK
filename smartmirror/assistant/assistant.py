"""Assistant orchestrator: wires RAG, the LLM client, STT/TTS, and tools together.

This is the only place allowed to know about both `rag` and `llm` -- prompt
assembly (mixing the user question with retrieved chunks into a messages
list) happens exclusively in `_build_prompt` below. `rag/` and `llm/` must
never import from each other.
"""

from .llm import LLMBackend, LLMClient, OpenAICompatBackend
from .rag import Chunker, Embedder, Retriever, VectorStore
from .stt import WhisperSTT
from .tts import PiperTTS
from .tools import ToolManager

DEFAULT_SYSTEM_PROMPT = (
    "You are the Smart Mirror voice assistant. Answer questions concisely "
    "and factually, grounding your answers in the provided context when it "
    "is relevant. If the context doesn't contain the answer, say so instead "
    "of making one up."
)


class Assistant:
    """Orchestrates retrieval-augmented, tool-capable chat with an LLM."""

    def __init__(
        self,
        llm: LLMBackend = None,
        api_key=None,
        url=None,
        model="gpt-4o-mini",
        documents=None,
        tools=None,
        stt=False,
        tts=False,
        system_prompt=None,
        language="en",
    ):
        self.language = language
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        backend = llm or (OpenAICompatBackend(api_key=api_key, base_url=url, model=model) if api_key else None)
        if backend is None:
            raise ValueError("Assistant requires either llm=<LLMBackend instance> or api_key=<str>")
        self.llm = LLMClient(backend)

        self.chunker = Chunker()
        self.embedder = Embedder()
        self.store = VectorStore()
        self.retriever = Retriever(store=self.store, embedder=self.embedder)

        self.stt = WhisperSTT(language=language) if stt else None
        self.tts = PiperTTS(enabled=tts)
        self.tool_manager = ToolManager(tools=tools)

        self.history: list[dict] = []

        if documents:
            self.add_documents(documents)

    def add_documents(self, path: str) -> None:
        """Load, chunk, embed, and index documents from `path` (file or dir)."""
        chunks = self.chunker.load(path)
        if not chunks:
            return
        embeddings = self.embedder.embed([chunk["text"] for chunk in chunks])
        self.store.add(chunks, embeddings)

    def chat(self, message: str) -> str:
        """Answer `message`, grounding the reply in retrieved document chunks."""
        retrieved_chunks = self.retriever.retrieve(message)
        messages = self._build_prompt(message, retrieved_chunks)

        reply = self.llm.complete(messages, tools=self.tool_manager.specs() or None)

        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def voice_chat(self) -> str:
        """Listen for a spoken question, answer it, and speak the reply.

        STUB for phase 1 -- wiring the microphone (STT) and speaker (TTS)
        output happens in phase 2.
        """
        raise NotImplementedError("Assistant.voice_chat is implemented in phase 2")

    def reset_history(self) -> None:
        """Clear the conversation history."""
        self.history = []

    def _build_prompt(self, message: str, retrieved_chunks: list[str]) -> list[dict]:
        """Assemble the OpenAI-style messages list for one chat turn.

        This is the one place question + retrieved context become a prompt --
        neither `rag/` nor `llm/` know about the other.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)

        if retrieved_chunks:
            context = "\n\n".join(f"- {chunk}" for chunk in retrieved_chunks)
            user_content = (
                f"Context:\n{context}\n\nQuestion: {message}"
            )
        else:
            user_content = message

        messages.append({"role": "user", "content": user_content})
        return messages
