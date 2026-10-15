"""模型供应商配置：默认 MX；支持 openai / custom / openrouter。

环境变量：
  LIGHTAGENT_PROVIDER = mx | openai | custom | openrouter
  LIGHTAGENT_BASE_URL / MX_BASE_URL / OPENAI_BASE_URL
  LIGHTAGENT_MODEL / MX_MODEL / OPENAI_MODEL / OPENROUTER_MODEL
  LIGHTAGENT_REASONING_EFFORT（默认 medium；空字符串关闭）
key 读取顺序：
  默认/mx：MX_API_KEY → LIGHTAGENT_API_KEY → OPENAI_API_KEY → OPENROUTER_API_KEY
  openai/openrouter：LIGHTAGENT_API_KEY → OPENAI_API_KEY → OPENROUTER_API_KEY → MX_API_KEY
设 LIGHTAGENT_PROVIDER=openrouter 可切回旧 OpenRouter :free 路径。
"""
from __future__ import annotations

import datetime
import json
import os
import time

PROVIDER = os.environ.get("LIGHTAGENT_PROVIDER", "mx").strip().lower() or "mx"
# aliases
if PROVIDER in ("oai", "openai-compatible", "compat"):
    PROVIDER = "openai"
if PROVIDER == "custom":
    PROVIDER = "openai"

MX_BASE_URL = os.environ.get("MX_BASE_URL", "https://mxzzz.xyz/v1")
MX_DEFAULT_MODEL = os.environ.get("MX_MODEL", "deepseek-v4.1-flash")
DEFAULT_REASONING_EFFORT = os.environ.get("LIGHTAGENT_REASONING_EFFORT", "medium")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_FREE_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "thinkingmachines/inkling:free",
    "google/gemma-4-31b-it:free",
    "thinkingmachines/inkling-small:free",
    "google/gemma-4-26b-a4b-it:free",
    "poolside/laguna-s-2.1:free",
    "cohere/north-mini-code:free",
]

OPENAI_BASE_URL = (
    os.environ.get("LIGHTAGENT_BASE_URL")
    or os.environ.get("OPENAI_BASE_URL")
    or "https://api.openai.com/v1"
)
OPENAI_DEFAULT_MODEL = (
    os.environ.get("LIGHTAGENT_MODEL")
    or os.environ.get("OPENAI_MODEL")
    or "gpt-4o-mini"
)

if PROVIDER == "openrouter":
    BASE_URL = OPENROUTER_BASE_URL
    REQUIRE_FREE_SUFFIX = True
    FREE_MODELS = list(_OPENROUTER_FREE_MODELS)
    _env_model = os.environ.get("OPENROUTER_MODEL") or os.environ.get("LIGHTAGENT_MODEL")
    if _env_model:
        FREE_MODELS = [_env_model] + [m for m in FREE_MODELS if m != _env_model]
elif PROVIDER == "openai":
    BASE_URL = OPENAI_BASE_URL
    REQUIRE_FREE_SUFFIX = False
    FREE_MODELS = [OPENAI_DEFAULT_MODEL]
    _env_model = os.environ.get("LIGHTAGENT_MODEL") or os.environ.get("OPENAI_MODEL")
    if _env_model:
        FREE_MODELS = [_env_model] + [m for m in FREE_MODELS if m != _env_model]
else:
    # mx（默认）或未知名回落 mx
    PROVIDER = "mx"
    BASE_URL = MX_BASE_URL  # mx 路径只用 MX_BASE_URL，避免残留 LIGHTAGENT_BASE_URL 串台
    REQUIRE_FREE_SUFFIX = False
    FREE_MODELS = [MX_DEFAULT_MODEL]
    _env_model = (
        os.environ.get("LIGHTAGENT_MODEL")
        or os.environ.get("MX_MODEL")
        or os.environ.get("OPENROUTER_MODEL")
    )
    if _env_model:
        FREE_MODELS = [_env_model] + [m for m in FREE_MODELS if m != _env_model]

DEFAULT_MODEL = FREE_MODELS[0]
MODEL_CANDIDATES = FREE_MODELS

_default_limit = "200" if PROVIDER in ("mx", "openai") else "45"
DAILY_LIMIT = int(
    os.environ.get(
        "OPENROUTER_DAILY_LIMIT",
        os.environ.get("MX_DAILY_LIMIT", os.environ.get("LIGHTAGENT_DAILY_LIMIT", _default_limit)),
    )
)
PER_MIN_LIMIT = int(os.environ.get("LIGHTAGENT_PER_MIN_LIMIT", "18"))
_USAGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".openrouter_usage.json")


def _assert_free(model: str):
    """历史名：OpenRouter 路径要求 :free；其它路径不强制后缀。"""
    if REQUIRE_FREE_SUFFIX and not model.endswith(":free"):
        raise ValueError(f"拒绝使用非免费模型：{model}")


def get_api_key() -> str:
    # MX 默认优先 MX_API_KEY，避免残留的 ScienceEdu LIGHTAGENT_API_KEY 抢先。
    if PROVIDER == "mx":
        names = (
            "MX_API_KEY",
            "LIGHTAGENT_API_KEY",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
        )
    else:
        names = (
            "LIGHTAGENT_API_KEY",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "MX_API_KEY",
        )
    for name in names:
        key = os.environ.get(name)
        if key:
            return key
    raise RuntimeError(
        "请先设置 MX_API_KEY / LIGHTAGENT_API_KEY（或 OPENAI_API_KEY / OPENROUTER_API_KEY）"
    )


def _load_usage():
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    try:
        u = json.load(open(_USAGE_FILE))
    except Exception:
        u = {}
    if u.get("day") != today:
        u = {"day": today, "count": 0, "recent": []}
    return u


NETWORK_CALLS = 0


def _check_and_count():
    global NETWORK_CALLS
    NETWORK_CALLS += 1
    if os.environ.get("LIGHTAGENT_FORBID_OPENROUTER") == "1":
        raise RuntimeError("OpenRouter blocked by LIGHTAGENT_FORBID_OPENROUTER")
    u = _load_usage()
    now = time.time()
    u["recent"] = [t for t in u["recent"] if now - t < 60]
    if u["count"] >= DAILY_LIMIT:
        raise RuntimeError(f"今日已用 {u['count']} 次，达到本地上限 {DAILY_LIMIT}，停止以免超额")
    if len(u["recent"]) >= PER_MIN_LIMIT:
        time.sleep(60 - (now - u["recent"][0]) + 1)
    u["count"] += 1
    u["recent"].append(time.time())
    json.dump(u, open(_USAGE_FILE, "w"))


def usage_today() -> int:
    return _load_usage()["count"]


def _reasoning_effort_hook(context):
    """before_model_request：注入默认 reasoning_effort（可用环境变量覆盖；空则关闭）。"""
    from LightAgent.hooks import HOOK_REPLACE, HookDecision

    if getattr(context, "phase", None) != "before_model_request":
        return None
    effort = (os.environ.get("LIGHTAGENT_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT or "").strip()
    if not effort:
        return None
    payload = dict(getattr(context, "payload", None) or {})
    params = dict(payload.get("params") or {})
    params["reasoning_effort"] = effort
    extra = dict(params.get("extra_body") or {})
    extra["reasoning_effort"] = effort
    params["extra_body"] = extra
    return HookDecision(action=HOOK_REPLACE, payload={"params": params})


def make_agent(model: str = DEFAULT_MODEL, **kwargs):
    _assert_free(model)
    from LightAgent import LightAgent
    from local.harness.run_control import default_budget_limits
    from local.memory.inject import attach_profile_memory

    persona_text = kwargs.pop("persona_text", None)
    identity_block = kwargs.pop("identity_block", None)
    share_user_profile = kwargs.pop("share_user_profile", True)
    session_id = kwargs.pop("session_id", None)
    agent_id = kwargs.pop("agent_id", None)
    space_id = kwargs.pop("space_id", None)
    budget_limits = kwargs.pop("budget_limits", None)
    if budget_limits is None:
        budget_limits = default_budget_limits()
    kwargs["budget_limits"] = budget_limits
    kwargs.setdefault("tree_of_thought", False)
    if os.environ.get("LIGHTAGENT_FORBID_OPENROUTER") == "1":
        raise RuntimeError("OpenRouter blocked by LIGHTAGENT_FORBID_OPENROUTER")

    hooks = list(kwargs.pop("hooks", None) or [])
    # mx / openai 兼容路径都可注入 effort；openrouter free 通常忽略
    if PROVIDER in ("mx", "openai") and DEFAULT_REASONING_EFFORT:
        hooks = [_reasoning_effort_hook, *hooks]
    if hooks:
        kwargs["hooks"] = hooks

    agent = LightAgent(model=model, api_key=get_api_key(), base_url=BASE_URL, **kwargs)
    attach_profile_memory(
        agent,
        user_id=os.environ.get("LIGHTAGENT_USER_ID", "local-user"),
        session_id=session_id,
        agent_id=agent_id,
        space_id=space_id,
        persona_text=persona_text,
        identity_block=identity_block,
        share_user_profile=share_user_profile,
    )
    return agent


_FALLBACK_HINTS = (
    "429",
    "402",
    "401",
    "rate limit",
    "rate-limit",
    "quota",
    "insufficient",
    "credits",
    "404",
    "no endpoints",
    "unavailable",
    "expired",
)


def run_free(prompt: str, **kwargs):
    """依次尝试候选模型；遇限额/欠费/下线就换下一个。名称为历史兼容。"""
    last = None
    for model in FREE_MODELS:
        _assert_free(model)
        _check_and_count()
        try:
            out = make_agent(model=model, **kwargs).run(prompt)
            text = str(out)
            if any(h in text.lower() for h in _FALLBACK_HINTS) and len(text) < 400:
                last = text
                print(f"[model-fallback] {model} 返回疑似限额/鉴权错误，换下一个")
                continue
            return model, out
        except Exception as e:
            msg = str(e).lower()
            last = e
            if any(h in msg for h in _FALLBACK_HINTS):
                print(f"[model-fallback] {model} 不可用（{str(e)[:80]}），换下一个")
                continue
            raise
    raise RuntimeError(f"所有候选模型都不可用：{last}")
