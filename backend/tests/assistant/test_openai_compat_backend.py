from unittest.mock import patch

from glasscube.assistant.llm import OpenAICompatBackend


def test_complete_returns_reply_text(fake_llm_response):
    fake_response = fake_llm_response("Hello from the model")

    with patch(
        "openai.resources.chat.completions.completions.Completions.create",
        return_value=fake_response,
    ) as mock_create:
        backend = OpenAICompatBackend(api_key="sk-test", model="gpt-4o-mini")
        result = backend.complete([{"role": "user", "content": "hi"}])

    assert result == "Hello from the model"
    assert mock_create.call_args.kwargs["model"] == "gpt-4o-mini"
    assert mock_create.call_args.kwargs["messages"] == [{"role": "user", "content": "hi"}]
    assert "tools" not in mock_create.call_args.kwargs


def test_complete_passes_tools_through_when_given(fake_llm_response):
    fake_response = fake_llm_response("ok")
    tool_specs = [{"type": "function", "function": {"name": "noop"}}]

    with patch(
        "openai.resources.chat.completions.completions.Completions.create",
        return_value=fake_response,
    ) as mock_create:
        backend = OpenAICompatBackend(api_key="sk-test")
        backend.complete([{"role": "user", "content": "hi"}], tools=tool_specs)

    assert mock_create.call_args.kwargs["tools"] == tool_specs


def test_complete_handles_empty_content():
    fake_response = None

    def fake_create(**kwargs):
        class Message:
            content = None
            tool_calls = None

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        return Response()

    with patch(
        "openai.resources.chat.completions.completions.Completions.create",
        side_effect=fake_create,
    ):
        backend = OpenAICompatBackend(api_key="sk-test")
        result = backend.complete([{"role": "user", "content": "hi"}])

    assert result == ""


def test_respects_base_url_for_ollama_openrouter_vllm_etc():
    backend = OpenAICompatBackend(api_key="sk-test", base_url="http://localhost:11434/v1")
    assert str(backend._client.base_url) == "http://localhost:11434/v1/"
