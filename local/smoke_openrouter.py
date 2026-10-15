"""只用 OpenRouter 免费模型跑一次真实对话：python local/smoke_openrouter.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openrouter_config import run_free, usage_today

model, out = run_free("用一句中文介绍你自己。")
print("model:", model)
print(out)
print("今日已用请求数（本地计数）:", usage_today())
