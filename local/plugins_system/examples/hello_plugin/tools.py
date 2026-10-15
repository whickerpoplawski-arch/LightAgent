"""Demo tools for hello_plugin — no network."""

from __future__ import annotations


def hello(name: str = "world") -> str:
    """Return a friendly greeting."""
    return f"hello, {name}! (from hello_plugin)"


hello.tool_info = {
    "tool_name": "hello",
    "tool_description": "Say hello to someone. Use when the user asks for a greeting.",
    "tool_params": [
        {
            "name": "name",
            "type": "string",
            "description": "Who to greet.",
            "required": False,
        }
    ],
}


def echo_text(text: str) -> str:
    """Echo text back unchanged."""
    return text


echo_text.tool_info = {
    "tool_name": "echo_text",
    "tool_description": "Echo the given text back. Useful for sanity checks.",
    "tool_params": [
        {
            "name": "text",
            "type": "string",
            "description": "Text to echo.",
            "required": True,
        }
    ],
}


TOOLS = [hello, echo_text]
