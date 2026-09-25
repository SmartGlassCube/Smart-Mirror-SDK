from smartmirror.assistant.llm import LLMClient


def test_complete_delegates_to_backend(fake_backend):
    backend = fake_backend(reply="delegated reply")
    client = LLMClient(backend)

    result = client.complete([{"role": "user", "content": "hi"}])

    assert result == "delegated reply"
    assert backend.calls == [{"messages": [{"role": "user", "content": "hi"}], "tools": None}]


def test_complete_passes_tools_through_to_backend(fake_backend):
    backend = fake_backend()
    client = LLMClient(backend)
    tool_specs = [{"type": "function", "function": {"name": "noop"}}]

    client.complete([{"role": "user", "content": "hi"}], tools=tool_specs)

    assert backend.calls[0]["tools"] == tool_specs


def test_client_holds_no_provider_logic_of_its_own(fake_backend):
    """LLMClient must be a pure pass-through -- swapping backends is all it does."""
    backend_a = fake_backend(reply="from A")
    backend_b = fake_backend(reply="from B")

    assert LLMClient(backend_a).complete([]) == "from A"
    assert LLMClient(backend_b).complete([]) == "from B"
