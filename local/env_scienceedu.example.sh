#!/usr/bin/env bash
# 用法：export LIGHTAGENT_API_KEY='sk-...' && source local/env_scienceedu.example.sh
export LIGHTAGENT_PROVIDER=openai
export LIGHTAGENT_BASE_URL="${LIGHTAGENT_BASE_URL:-https://api.scienceedu.me/v1}"
export LIGHTAGENT_MODEL="${LIGHTAGENT_MODEL:-deepseek-v4.1-flash}"
export LIGHTAGENT_REASONING_EFFORT="${LIGHTAGENT_REASONING_EFFORT:-medium}"
export LIGHTAGENT_DAILY_LIMIT="${LIGHTAGENT_DAILY_LIMIT:-200}"
