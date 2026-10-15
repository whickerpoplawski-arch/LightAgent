"""演示：带工具的 LightAgent（只用免费模型）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openrouter_config import run_free, usage_today

def get_weather(city_name: str) -> str:
    """Get the current weather for `city_name`"""
    print(f"  >> 工具被调用: get_weather({city_name!r})")
    return f"Query result: {city_name} is sunny, 22°C."

get_weather.tool_info = {
    "tool_name": "get_weather",
    "tool_description": "Get current weather information for the specified city.",
    "tool_params": [{"name": "city_name", "description": "The name of the city to query", "type": "string", "required": True}],
}

q = "帮我查一下上海的天气，用中文回答。"
print("用户:", q)
model, out = run_free(q, tools=[get_weather])
print("模型:", model)
print("Agent:", out)
print("今日已用请求数:", usage_today())
