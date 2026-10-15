"""Agent tools: learn / forget / recall / pin / edit.

``user_id`` and ``namespace`` are accepted so a model that sends them does not
crash the call. They are ignored. The host stamps the write scope.
"""

from __future__ import annotations

import json

from .editor import MemoryEditor
from .host import current_host
from .pack import tokens
from .store import get_store


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _scope_echo() -> dict:
    host = current_host()
    return {"user_id": host.user_id, "namespace": host.namespace}


def memory_learn(
    text: str,
    lane: str = "general",
    facet: str = "identity",
    kind: str = "preference",
    topics: str = "",
    user_id: str = "",
    namespace: str = "",
) -> str:
    """记住一条用户偏好或事实。不能指定写到谁的画像里。"""
    topic_list = [part.strip() for part in (topics or "").split(",") if part.strip()]
    result = MemoryEditor().learn(
        text,
        lane=lane,
        facet=facet,
        kind=kind,
        topics=topic_list,
        user_id=user_id,
        namespace=namespace,
    )
    body = result.to_dict()
    body["scope"] = _scope_echo()
    if result.status == "needs_confirm":
        body["note"] = "已保存为待确认，确认前不会注入对话。"
    elif result.status == "saved":
        body["note"] = "已写入用户画像。"
    return _dump(body)


memory_learn.tool_info = {
    "tool_name": "memory_learn",
    "tool_description": "记住用户的一条偏好或事实（general 常驻，situational 按主题召回）。不要用它记助手自己的反思。",
    "tool_params": [
        {"name": "text", "type": "string", "description": "要记住的一句话", "required": True},
        {"name": "lane", "type": "string", "description": "general 或 situational", "required": False},
        {"name": "facet", "type": "string", "description": "identity/style/goal/tooling/veto/channel/life", "required": False},
        {"name": "kind", "type": "string", "description": "preference/fact/procedure/correction/other", "required": False},
        {"name": "topics", "type": "string", "description": "逗号分隔的主题，情景车道用", "required": False},
    ],
}


def memory_forget(learning_id: str = "", query: str = "", user_id: str = "", namespace: str = "") -> str:
    """忘掉一条画像。只能删除 host 盖章范围内的记录。"""
    target = learning_id or query
    if not target.strip():
        return _dump({"status": "rejected", "reason": "learning_id or query is required", "scope": _scope_echo()})
    removed = MemoryEditor().forget(target, user_id=user_id, namespace=namespace)
    if not removed:
        return _dump({"status": "not_found", "scope": _scope_echo()})
    return _dump({"status": "forgotten", "ids": removed, "scope": _scope_echo()})


memory_forget.tool_info = {
    "tool_name": "memory_forget",
    "tool_description": "删除一条用户画像。可传 learning_id，或一段原文片段。",
    "tool_params": [
        {"name": "learning_id", "type": "string", "description": "学习条目 id", "required": False},
        {"name": "query", "type": "string", "description": "按原文片段删除", "required": False},
    ],
}


def memory_recall(query: str, user_id: str = "", namespace: str = "") -> str:
    """同步回忆。只读 host 范围内的画像，不写回聊天记录。"""
    stamped = current_host().stamp({"user_id": user_id, "namespace": namespace})
    rows = get_store().list_injectable(user_id=stamped["user_id"], namespace=stamped["namespace"])
    query_tokens = tokens(query)
    ranked = []
    for item in rows:
        bag = tokens(item.text) | tokens(" ".join(item.topics))
        score = len(query_tokens & bag)
        if item.pinned:
            score += 1
        if score > 0 or (not query.strip() and item.lane == "general"):
            ranked.append((score, item))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].lane != "general"))
    hits = [item.to_dict() for _, item in ranked[:8]]
    if not hits:
        return _dump({
            "status": "empty",
            "note": "这一轮没有对上的画像。不要说成「我什么都不记得」。",
            "scope": _scope_echo(),
            "hits": [],
        })
    return _dump({"status": "ok", "hits": hits, "scope": _scope_echo()})


memory_recall.tool_info = {
    "tool_name": "memory_recall",
    "tool_description": "按当前问题同步回忆用户画像。结果只用于回答，不要写进用户原话。",
    "tool_params": [
        {"name": "query", "type": "string", "description": "要回忆的主题", "required": True},
    ],
}


def memory_pin(learning_id: str, user_id: str = "", namespace: str = "") -> str:
    """把一条画像钉住，预算裁剪时优先保留。"""
    saved = MemoryEditor().pin(learning_id, pinned=True, user_id=user_id, namespace=namespace)
    if saved is None:
        return _dump({"status": "not_found", "scope": _scope_echo()})
    return _dump({"status": "pinned", "learning": saved.to_dict(), "scope": _scope_echo()})


memory_pin.tool_info = {
    "tool_name": "memory_pin",
    "tool_description": "钉住一条用户画像，让它在记忆包预算里优先保留。",
    "tool_params": [
        {"name": "learning_id", "type": "string", "description": "学习条目 id", "required": True},
    ],
}


def memory_edit(learning_id: str, text: str, user_id: str = "", namespace: str = "") -> str:
    """改正一条画像的原文。"""
    result = MemoryEditor().edit(learning_id, text, user_id=user_id, namespace=namespace)
    body = result.to_dict()
    body["scope"] = _scope_echo()
    return _dump(body)


memory_edit.tool_info = {
    "tool_name": "memory_edit",
    "tool_description": "修改一条已有用户画像的文本。",
    "tool_params": [
        {"name": "learning_id", "type": "string", "description": "学习条目 id", "required": True},
        {"name": "text", "type": "string", "description": "新的原文", "required": True},
    ],
}


def memory_list(lane: str = "", user_id: str = "", namespace: str = "") -> str:
    """列出当前用户的画像，含待确认条目。"""
    rows = MemoryEditor().list_rows(lane=lane)
    # lane filter is applied inside list_rows; user scope is host-stamped via editor
    del user_id, namespace
    return _dump({"status": "ok", "rows": rows, "scope": _scope_echo()})


memory_list.tool_info = {
    "tool_name": "memory_list",
    "tool_description": "列出用户画像，包括尚未确认的敏感条目。",
    "tool_params": [
        {"name": "lane", "type": "string", "description": "可选：general 或 situational", "required": False},
    ],
}


MEMORY_TOOLS = [
    memory_learn,
    memory_forget,
    memory_recall,
    memory_pin,
    memory_edit,
    memory_list,
]
