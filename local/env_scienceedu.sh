#!/usr/bin/env bash
# ScienceEdu 日常环境（key 来自 process.env.LIGHTAGENT_API_KEY 或外部 export）
export LIGHTAGENT_PROVIDER=openai
export LIGHTAGENT_BASE_URL="${LIGHTAGENT_BASE_URL:-https://api.scienceedu.me/v1}"
export LIGHTAGENT_MODEL="${LIGHTAGENT_MODEL:-deepseek-v4.1-flash}"
export LIGHTAGENT_REASONING_EFFORT="${LIGHTAGENT_REASONING_EFFORT:-medium}"
export LIGHTAGENT_DAILY_LIMIT="${LIGHTAGENT_DAILY_LIMIT:-200}"
# 兼容旧路径：若只有 LIGHTAGENT_API_KEY，openrouter_config 已优先读它
