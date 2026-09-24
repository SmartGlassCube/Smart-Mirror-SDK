from unittest.mock import patch

from smartmirror.assistant.llm import LLMClient


def test_complete_returns_content_and_tool_calls(fake_llm_response):
    fake_response = fake_llm_response("Hello from the model")

    with patch(
        "openai.resources.chat.completions.completions.Completions.create",
        return_value=fake_response,
    ) as mock_create:
        client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
        result = client.complete([{"role": "user", "content": "hi"}])

    assert result == {"content": "Hello from the model", "tool_calls": []}
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
        client = LLMClient(api_key="sk-test")
        client.complete([{"role": "user", "content": "hi"}], tools=tool_specs)

    assert mock_create.call_args.kwargs["tools"] == tool_specs


def test_complete_respects_base_url():
    client = LLMClient(api_key="sk-test", base_url="http://localhost:8000/v1")
    assert str(client._client.base_url) == "http://localhost:8000/v1/"
