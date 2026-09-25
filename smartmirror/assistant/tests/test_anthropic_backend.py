from unittest.mock import MagicMock, patch

from smartmirror.assistant.llm import AnthropicBackend

CREATE_PATH = "anthropic.resources.messages.messages.Messages.create"


def _fake_response(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def test_complete_returns_reply_text():
    fake_response = _fake_response("Hello from Claude")

    with patch(CREATE_PATH, return_value=fake_response) as mock_create:
        backend = AnthropicBackend(api_key="sk-ant-test", model="claude-sonnet-5")
        result = backend.complete([{"role": "user", "content": "hi"}])

    assert result == "Hello from Claude"
    assert mock_create.call_args.kwargs["model"] == "claude-sonnet-5"
    assert mock_create.call_args.kwargs["messages"] == [{"role": "user", "content": "hi"}]
    assert "system" not in mock_create.call_args.kwargs


def test_system_role_message_is_hoisted_into_system_param():
    fake_response = _fake_response("ok")
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "hi"},
    ]

    with patch(CREATE_PATH, return_value=fake_response) as mock_create:
        backend = AnthropicBackend(api_key="sk-ant-test")
        backend.complete(messages)

    assert mock_create.call_args.kwargs["system"] == "You are helpful."
    assert mock_create.call_args.kwargs["messages"] == [{"role": "user", "content": "hi"}]


def test_complete_sends_max_tokens():
    fake_response = _fake_response("ok")

    with patch(CREATE_PATH, return_value=fake_response) as mock_create:
        backend = AnthropicBackend(api_key="sk-ant-test", max_tokens=256)
        backend.complete([{"role": "user", "content": "hi"}])

    assert mock_create.call_args.kwargs["max_tokens"] == 256


def test_concatenates_multiple_text_blocks():
    block_a = MagicMock(type="text", text="Hello, ")
    block_b = MagicMock(type="text", text="world.")
    response = MagicMock()
    response.content = [block_a, block_b]

    with patch(CREATE_PATH, return_value=response):
        backend = AnthropicBackend(api_key="sk-ant-test")
        result = backend.complete([{"role": "user", "content": "hi"}])

    assert result == "Hello, world."
