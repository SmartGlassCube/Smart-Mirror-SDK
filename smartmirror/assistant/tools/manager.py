"""Function-calling dispatcher: registers tools and executes model tool calls.

STUB for phase 1 -- registration works, but no real tools are wired in and
dispatch of an actual LLM tool_call is not implemented yet.
"""


class ToolManager:
    """Registers callables as OpenAI-style tools and dispatches tool calls to them."""

    def __init__(self, tools: dict = None):
        # name -> callable
        self._tools = dict(tools or {})

    def register(self, name: str, func, schema: dict = None) -> None:
        """Register a callable under `name` for later dispatch."""
        self._tools[name] = func

    def specs(self) -> list[dict]:
        """Return OpenAI-style tool definitions for the registered tools."""
        return []

    def dispatch(self, tool_call) -> str:
        """Execute a single tool call requested by the LLM and return its result."""
        raise NotImplementedError("ToolManager.dispatch is implemented in phase 2")
