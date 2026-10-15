# 生活助手上下文压缩（Compact）

Compact 只管「这一会话还看得见什么」。跨会话要记住的事进 Memory。可复用的步骤经确认后写成 LightAgent skill。

默认摘要器是本地模板填充，**不调用 OpenRouter**。单测同样不联网。

## 怎么用

在 TUI 输入框：

```text
/compact
/compact 焦点：下周东京行程的预算上限、已否决的酒店
```

以 `/compact` 开头的输入不会送进普通对话。

自动压缩：当前上下文占窗口 **严格大于 85%** 时，在发送前和每轮结束后各检查一次。TUI 窗口默认约 100 万 token，可用环境变量改小：

```bash
LIGHTAGENT_CONTEXT_WINDOW=8000 python -m local.tui.app --mock
```

压缩后状态栏会出现「上下文已压缩」或手动回执。摘要失败时回执是「已裁剪未摘要」，最近的用户轮次还在。

程序化流程（例如「下次订票按这三步」）会弹出「存为 skill？」。确认后写到 `local/skills_promoted/skills/<slug>/SKILL.md`，可被 `SkillManager` 的 `skills_directories` 发现。画像、偏好、忌口、否决直接进 Memory，不再问一次。过敏、工资等仍走既有 Admission：敏感句会变成待确认，确认前不注入。

忌口、用药、Never、素食会在会话消息上打 `metadata.compact = "never"`，裁剪时不会被丢掉。

取回被外置的大工具结果：

```text
recall_spilled(reference="tool-result:sha256:…", query="可选定位词")
```

## 可选的真实 :free 摘要

```bash
LIGHTAGENT_COMPACT_LLM=1
```

打开后才会走 `local.openrouter_config.run_free`（只允许 `:free`，并计入本地额度）。测试不要打开这个开关。

## 测试

在 `LightAgent/` 目录：

```bash
python -m pytest local/compact/tests local/memory/tests local/conversations/tests -q
```
