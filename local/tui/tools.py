"""给 Agent 的工具。二开时在这里加工具并放进 TOOLS。

内置一等联网工具见 local.tools.web（web_search / web_fetch），不是插件。
"""

from local.compact.recall_spill import recall_spilled
from local.conversations.collaborate import delegate_to_bot
from local.memory.tools import MEMORY_TOOLS
from local.tools.web import web_fetch, web_search


def get_weather(city_name: str) -> str:
    """Get the current weather for `city_name`"""
    return f"Query result: {city_name} is sunny, 22°C."


get_weather.tool_info = {
    "tool_name": "get_weather",
    "tool_description": "Get current weather information for the specified city.",
    "tool_params": [
        {"name": "city_name", "description": "The name of the city to query", "type": "string", "required": True}
    ],
}

TOOLS = [get_weather, web_search, web_fetch, delegate_to_bot, recall_spilled, *MEMORY_TOOLS]
