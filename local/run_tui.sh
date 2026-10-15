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

if [[ -z "${LIGHTAGENT_API_KEY:-}${MX_API_KEY:-}${OPENAI_API_KEY:-}${OPENROUTER_API_KEY:-}" ]]; then
  echo "缺少 API key：请提供 MX_API_KEY（或 LIGHTAGENT_API_KEY / OPENAI_API_KEY）" >&2
  exit 1
fi

if [[ "${1:-}" == "--mock" ]]; then
  exec env -u NO_COLOR "$PY" -m local.tui.app --mock
fi

export LIGHTAGENT_ALLOW_OPENROUTER=1
exec env -u NO_COLOR "$PY" -m local.tui.app "$@"
