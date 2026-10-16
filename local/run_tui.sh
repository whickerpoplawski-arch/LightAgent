#!/usr/bin/env bash
# 日常启动 LightAgent TUI（默认 MX / deepseek-v4.1-flash / effort=medium）
# ScienceEdu：source local/env_scienceedu.sh && ./local/run_tui.sh  ← 需改脚本或手动 export
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:-}:$ROOT"

# 强制日常默认 MX（覆盖会话里残留的 ScienceEdu openai 环境）
# 若要 ScienceEdu：LIGHTAGENT_FORCE_PROVIDER=openai LIGHTAGENT_BASE_URL=... ./local/run_tui.sh
if [[ "${LIGHTAGENT_FORCE_PROVIDER:-}" == "openai" ]]; then
  export LIGHTAGENT_PROVIDER=openai
else
  export LIGHTAGENT_PROVIDER=mx
  unset LIGHTAGENT_BASE_URL || true
fi

export LIGHTAGENT_REASONING_EFFORT="${LIGHTAGENT_REASONING_EFFORT:-medium}"
export LIGHTAGENT_DAILY_LIMIT="${LIGHTAGENT_DAILY_LIMIT:-200}"
export MX_BASE_URL="${MX_BASE_URL:-https://mxzzz.xyz/v1}"
export MX_MODEL="${MX_MODEL:-deepseek-v4.1-flash}"
export LIGHTAGENT_MODEL="${LIGHTAGENT_MODEL:-$MX_MODEL}"

PY="${ROOT}/../la-venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="/workspace/la-venv/bin/python"
fi
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

shot_or_mock=0
for arg in "$@"; do
  if [[ "$arg" == "--mock" || "$arg" == "--shot" ]]; then
    shot_or_mock=1
  fi
done
if [[ "$shot_or_mock" -eq 0 && -z "${LIGHTAGENT_API_KEY:-}${MX_API_KEY:-}${OPENAI_API_KEY:-}${OPENROUTER_API_KEY:-}" ]]; then
  echo "缺少 API key：请提供 MX_API_KEY（或 LIGHTAGENT_API_KEY / OPENAI_API_KEY）" >&2
  exit 1
fi

export LIGHTAGENT_ALLOW_OPENROUTER=1
# NO_COLOR 会让 Textual 把前景涂成灰度。TGP 占位符靠这块颜色认图像 id，涂灰后气泡是空白。
unset NO_COLOR || true

# 图片样式验收走 kitty 的 TGP。halfcell / unicode 马赛克不能当 PASS。
launch_python() {
  exec "$PY" -m local.tui.app "$@"
}

warn_need_kitty() {
  echo "============================================================" >&2
  echo "WARNING: 图片气泡需 TGP/Sixel 终端（请用 kitty）。" >&2
  echo "当前不是 kitty。不会用 halfcell/unicode 马赛克冒充验收 PASS。" >&2
  echo "安装 kitty 后重新执行: ./local/run_tui.sh" >&2
  echo "============================================================" >&2
}

in_kitty=0
if [[ -n "${KITTY_WINDOW_ID:-}${KITTY_PID:-}" ]] || [[ "${TERM:-}" == *kitty* ]]; then
  in_kitty=1
fi

if [[ "$in_kitty" -eq 1 ]]; then
  export LIGHTAGENT_IMAGE_PROTOCOL="${LIGHTAGENT_IMAGE_PROTOCOL:-tgp}"
  launch_python "$@"
fi

if [[ -z "${LIGHTAGENT_TUI_NO_KITTY:-}" ]] && command -v kitty >/dev/null 2>&1; then
  if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    export LIGHTAGENT_IMAGE_PROTOCOL="${LIGHTAGENT_IMAGE_PROTOCOL:-tgp}"
    # kitty 的子进程不应继承 tmux 标记，否则 TGP 序列会被包成 tmux passthrough。
    exec env -u TMUX -u TMUX_PANE -u NO_COLOR kitty --title "LightAgent" "$PY" -m local.tui.app "$@"
  fi
  echo "检测到 kitty，但没有图形显示，无法拉起 kitty 窗口。" >&2
fi

warn_need_kitty
if [[ -z "${LIGHTAGENT_IMAGE_PROTOCOL:-}" || "${LIGHTAGENT_IMAGE_PROTOCOL}" == "halfcell" || "${LIGHTAGENT_IMAGE_PROTOCOL}" == "unicode" ]]; then
  export LIGHTAGENT_IMAGE_PROTOCOL=sixel
fi
launch_python "$@"
