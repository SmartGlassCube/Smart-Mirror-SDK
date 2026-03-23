"""OpenAI-compatible API client backed by the requests library."""


class LLMClient:
    """Sends chat-completion requests to any OpenAI-compatible endpoint."""

    def __init__(self, api_key: str, url: str, model: str) -> None:
        pass

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        """Send *messages* to the LLM and return the raw response dict."""
        pass
