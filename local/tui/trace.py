"""轨迹 / Trace 数据模型与会话级 TraceStore。"""
from __future__ import annotations

from dataclasses import dataclass, field


# 标签颜色（Textual markup）
KIND_COLOR = {
    "user": "#2563eb",       # 蓝
    "assistant": "#7c3aed",  # 紫
    "tool": "#ea580c",       # 橙
    "context": "#16a34a",    # 绿
    "model": "#7c3aed",
    "error": "#dc2626",
    "delegate": "#0f766e",
}

KIND_LABEL = {
    "user": "用户",
    "assistant": "助手",
    "tool": "工具",
    "context": "上下文",
    "model": "模型",
    "error": "错误",
    "delegate": "派发",
}

# 时间线泳道
LANE_ORDER = ("input", "model", "tool", "other")
LANE_LABEL = {"input": "输入", "model": "模型", "tool": "工具", "other": "其他"}
LANE_COLOR = {
    "input": "#38bdf8",   # 青蓝
    "model": "#a78bfa",   # 紫
    "tool": "#fb923c",    # 橙
    "other": "#4ade80",   # 绿
}


@dataclass
class TraceStep:
    kind: str  # user | assistant | tool | context | model | error
    summary: str
    detail: str = ""
    status: str = "ok"  # ok | error
    tokens: int = 0
    duration_ms: int = 0
    lane: str = ""  # input | model | tool | other
    tool_name: str = ""
    tool_args: str = ""
    tool_result: str = ""

    def __post_init__(self) -> None:
        if not self.lane:
            self.lane = {
                "user": "input",
                "assistant": "model",
                "model": "model",
                "tool": "tool",
                "context": "other",
                "error": "other",
                "delegate": "other",
            }.get(self.kind, "other")

    @property
    def label(self) -> str:
        return KIND_LABEL.get(self.kind, self.kind)

    @property
    def color(self) -> str:
        if self.status == "error":
            return KIND_COLOR["error"]
        return KIND_COLOR.get(self.kind, "#8e8e93")



def _default_context_limit() -> int:
    import os

    raw = os.environ.get("LIGHTAGENT_CONTEXT_WINDOW", "").strip()
    if not raw:
        return 1_000_000
    try:
        return max(1, int(raw))
    except ValueError:
        return 1_000_000


@dataclass
class ContextUsage:
    """上下文窗口占用（mock 估算，供底部 % 与弹出层）。"""

    limit: int = field(default_factory=_default_context_limit)
    system: int = 2_200      # 系统提示词
    tools: int = 8_300       # 工具定义
    messages: int = 0        # 对话消息

    @property
    def used(self) -> int:
        return max(0, self.system + self.tools + self.messages)

    @property
    def pct(self) -> int:
        if self.limit <= 0:
            return 0
        return min(100, int(round(self.used / self.limit * 100)))

    def fmt(self, n: int) -> str:
        if n >= 1_000_000:
            v = n / 1_000_000
            return f"~{v:.1f}M".replace(".0M", "M")
        if n >= 1_000:
            v = n / 1_000
            s = f"{v:.1f}".rstrip("0").rstrip(".")
            return f"~{s}K"
        return f"~{n}"


@dataclass
class SessionStats:
    rounds: int = 0
    steps: int = 0
    tokens: int = 0
    tok_per_s: float = 0.0
    cache_hit_pct: float = 0.0


@dataclass
class TraceStore:
    """每个 Session 一份轨迹。"""

    steps: list[TraceStep] = field(default_factory=list)
    stats: SessionStats = field(default_factory=SessionStats)
    context: ContextUsage = field(default_factory=ContextUsage)

    def add(self, step: TraceStep) -> TraceStep:
        self.steps.append(step)
        self.stats.steps = len(self.steps)
        if step.tokens:
            self.stats.tokens += step.tokens
        return step

    def clear(self) -> None:
        self.steps.clear()
        self.stats = SessionStats()
        self.context = ContextUsage()

    def timeline_cells(self, width: int = 48) -> dict[str, str]:
        """把 steps 投影到固定宽度字符条（各泳道一条）。"""
        width = max(8, width)
        n = len(self.steps)
        lanes = {k: ["·"] * width for k in LANE_ORDER}
        if n == 0:
            return {k: "".join(v) for k, v in lanes.items()}
        for i, step in enumerate(self.steps):
            lane = step.lane if step.lane in lanes else "other"
            # 每步占一段
            start = int(i * width / n)
            end = max(start + 1, int((i + 1) * width / n))
            ch = "█" if step.status != "error" else "▒"
            for x in range(start, min(end, width)):
                lanes[lane][x] = ch
        return {k: "".join(v) for k, v in lanes.items()}

    def timeline_segments(self, width: int = 48) -> dict[str, list[tuple[int, int, int, str]]]:
        """各泳道上的步骤段：(step_index, start, end, status)。供时间线条块点击。"""
        width = max(8, width)
        n = len(self.steps)
        out: dict[str, list[tuple[int, int, int, str]]] = {k: [] for k in LANE_ORDER}
        if n == 0:
            return out
        for i, step in enumerate(self.steps):
            lane = step.lane if step.lane in out else "other"
            start = int(i * width / n)
            end = max(start + 1, int((i + 1) * width / n))
            end = min(end, width)
            out[lane].append((i, start, end, step.status))
        return out


def match_trace_query(step: TraceStep, query: str) -> bool:
    """轨迹搜索。

    - 前缀：`tool:` / `model:` / `user:` / `assistant:` / `context:` / `lane:tool`
      以及中文「工具:」「模型:」「用户:」「助手:」「上下文:」
    - 无前缀时优先匹配 summary / tool_name / 标签；
      不因 model/context 的 detail 里提到工具名而误命中。
    """
    raw = (query or "").strip()
    if not raw:
        return True

    kind_req: str | None = None
    lane_req: str | None = None
    rest = raw

    kind_prefixes = [
        ("tool:", "tool"),
        ("model:", "model"),
        ("user:", "user"),
        ("assistant:", "assistant"),
        ("context:", "context"),
        ("error:", "error"),
        ("工具:", "tool"),
        ("模型:", "model"),
        ("用户:", "user"),
        ("助手:", "assistant"),
        ("上下文:", "context"),
    ]
    matched_prefix = False
    lower = raw.lower()
    for pref, kind in kind_prefixes:
        # 英文前缀用 lower 比；中文用原文
        if pref.isascii():
            if lower.startswith(pref):
                kind_req = kind
                rest = raw[len(pref):].strip()
                matched_prefix = True
                break
        else:
            if raw.startswith(pref):
                kind_req = kind
                rest = raw[len(pref):].strip()
                matched_prefix = True
                break

    if not matched_prefix and lower.startswith("lane:"):
        matched_prefix = True
        body = raw[5:].strip()
        token = body.split()[0] if body else ""
        rest = body[len(token):].strip() if token else ""
        inv = {v: k for k, v in LANE_LABEL.items()}
        lane_req = inv.get(token, token)

    if kind_req and step.kind != kind_req:
        return False
    if lane_req and step.lane != lane_req:
        return False

    needle = rest.lower()
    if not needle:
        return True

    primary = " ".join(
        [
            step.summary or "",
            step.tool_name or "",
            step.label or "",
            KIND_LABEL.get(step.kind, ""),
        ]
    ).lower()
    if needle in primary:
        return True

    if step.kind == "tool":
        secondary = f"{step.tool_args or ''} {step.tool_result or ''} {step.detail or ''}".lower()
        return needle in secondary

    if step.kind in ("user", "assistant"):
        return needle in (step.detail or "").lower()

    # model / context / error：禁止用 detail 误伤（例如 detail 里写了 tool=get_weather）
    return False
