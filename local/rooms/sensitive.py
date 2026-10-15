"""Room turns refuse outbound and approval actions. Those go back to a 1:1 chat."""

from __future__ import annotations

_NEEDLES = (
    "发邮件",
    "发送邮件",
    "写邮件",
    "下单",
    "支付",
    "付款",
    "转账",
    "密钥",
    "api key",
    "apikey",
    "密码",
    "审批",
    "批准",
    "slack",
)

SENSITIVE_NOTICE = (
    "请回主对话或该 Bot 的 1:1 处理。"
    "群里不会代发邮件、下单、提交密钥或走审批，也不会假装已经发出。"
)


def sensitive_reason(text: str) -> str | None:
    folded = (text or "").casefold()
    for needle in _NEEDLES:
        if needle.casefold() in folded:
            return needle
    return None
