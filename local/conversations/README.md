# 多对话身份

侧栏里每个对话是一个 Bot。它的身份是**你写的职位和职责**，注入当轮 system 的 `<identity>`，不进用户画像。模板只是可选起稿。需要时，主对话可以用 `@角色` 或 `delegate_to_bot` 请另一个已存在的 Bot 办一件事，再把结果说回来。

用户画像默认跨 Bot 共享。人格默认沿用 `local/persona/` 的 SOUL / IDENTITY。某个 Bot 可以改成只用自己的人格文本。`space_id` 默认等于所在分组的 `project_id`，分组一换，还停在旧分组上的 space 会跟着走。

## 侧栏

- 头像、标题、预览、相对时间
- **置顶**在最上面，其余按最近更新
- 分组沿用原来的项目：移入、新建、移出
- 未读是标题前的圆点，标题变蓝；打开该对话就清掉
- 隐藏的对话默认不出现。侧栏底部「显示已隐藏」可以找回来
- 「创建群聊」会开一个主持式同房。做法见 `local/rooms/README.md`。主对话里的 `@` 派发仍然是一对一，不进群。

顶栏标题后面会带当前职位，例如 `账本  家庭账本官`。没有填职位就不显示。

## 设定身份

菜单里的「设定身份…」，或 **Ctrl+Shift+I**。

主路径是两个输入框：

- **职位** `role_title`：短名字，比如「家庭账本官」
- **职责** `job_description`：多行，你想让这个 Bot 守的边界和语气

保存的就是这两个字段里的文字。下面的模板下拉是起稿：选「日程秘书」会把示例填进输入框，你再改。改过之后 `template_id` 会清空，下次打开不会用模板盖掉你的句子。不选模板、从头写，同样是一等公民。

另外两个开关：

- **人格**：`inherit` 用全局 SOUL / IDENTITY，再加这段身份。`override` 只用编辑框里的人格文本，不再注入全局 SOUL。
- **共享用户画像**：默认开。关掉以后，这个 Bot 的当轮请求里没有 Profile pack，身份块还在。

注入顺序：基础 system → `<persona>` → `<identity>` → `<memory-context>`。身份和 pack 只进这一次模型请求，不写进用户消息，也不调用 `memory_learn`。

内置起稿（都可以改掉）：个人生活助手、日程秘书、学习导师、出行顾问、习惯教练、饮食顾问、家务管家、工作纪要。

## 会话菜单

右键会话行，或把焦点放在行上按 **`:`** 或 **`m`**，打开贴着该行的浮层菜单：置顶、移至分组、标未读、重命名（在行内改）、设定身份、复制对话 ID、隐藏、删除（先确认）。

焦点在行上时 **Delete** 也是删除确认。菜单动作在 `context_menu.py` 的 `apply_action`。

## 派发（单层）

协作默认开着。主对话里写 `@日程秘书 帮我看下周是否冲突` 会派给已存在 Bot。子调用只拿任务和一句背景。只一层；关掉协作时 `@` 当普通文本。mock/测试不打 OpenRouter。

## 落盘

`local/data/workspace/workspace.json` 与 `local/data/workspace/conversations/<id>.json`。

## 运行和测试

```bash
PYTHONPATH=. python -m local.tui.app --mock
PYTHONPATH=. python -m pytest local/conversations/tests local/memory/tests -q
```

## 非目标

群聊；默认 ToT/LightFlow；身份写入 User Profile；子 Bot 再派发；付费模型。
