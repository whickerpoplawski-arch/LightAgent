# 插件安装方式调研与选型

调研时间：2026-10。目标：给 LightAgent 选**最轻量**、可在 `local/` 旁路落地的插件系统，不 fork 上游 core。

## 各家怎么做

| 方案 | 安装方式 | 包形态 | 复杂度 | 与 LightAgent 契合度 |
| --- | --- | --- | --- | --- |
| **Claude Code Plugins** | marketplace + `/plugin install`；scope: user/project/local | 目录：skills / agents / hooks / MCP | 高（市场、校验、作用域） | 重；上游已明确不做 marketplace |
| **OpenAI Agent Plugins** | marketplace / 本地 catalog；`plugin.json` + `skills/` + `mcp.json` | 可移植 Agent Plugins 标准 | 中高 | 目录形态可借鉴，但发布/目录太重 |
| **Cursor Skills** | 目录发现（`.cursor/skills` 等）；插件市场装技能包 | `SKILL.md` 渐进披露 | 低（技能层） | LightAgent 已有同类 SkillManager |
| **LangChain / LangGraph** | pip 包 + 官方 marketplace（给 coding agent 用的 skills/MCP） | Python 包 / Claude 插件市场 | 中 | pip 依赖求解不适合「轻量二开」 |
| **MCP as plugins** | `mcp.json` / stdio / SSE 配置后挂工具 | 外部进程或远程 server | 中 | LightAgent 已支持 MCP；适合「工具源」，不是完整插件生命周期 |
| **LightAgent ConnectorManifest** | 无安装；清单 + 离线 `validate_connector`，应用代码手动挂载 | 内存对象：tools/skills/MCP/hooks | 很低 | 已有，但**没有 install/enable 层** |

## 选型结论

采用 **本地目录插件（Local Directory Plugins）**：

```
plugin/
  manifest.yaml      # name / version / description / entrypoints
  tools.py           # 可选，带 tool_info 的可调用对象
  skills/            # 可选，SKILL.md 树（复用上游渐进加载）
  mcp.json           # 可选，仅声明，不自动起进程
```

- **install** = 复制或软链到 `local/plugins/<name>/`（默认不拉远程代码）
- **enable/disable** = `local/plugins/enabled.json`
- **load** = 收集 tools + skills_directories，交给现有 `LightAgent(..., tools=, skills_directories=)`
- **不做**：marketplace、任意 URL 下载、依赖求解、自动装 pip 包

### 为什么是最轻量且合适

1. 与上游 Connector「清单 + 手动激活」哲学一致，只补「安装/启用」这一层。
2. 技能继续走 LightAgent 自带的渐进式 `SkillManager`，不另造运行时。
3. 工具是普通 Python 函数 + `tool_info`，和现有示例一致。
4. MCP 只存配置，调用方决定是否 `setup_mcp`，避免 install 时偷跑网络。
5. 全部落在 `local/`，不改 `pyproject` / core，方便跟上游合并。

### 刻意不做的

- 远程 marketplace / 自动 git clone（需要时可由用户先 clone 再 `install ./path`）
- 插件内 `requirements.txt` 自动 pip install
- 对任意第三方代码的沙箱执行保证（仍需人工审查 tools.py）

## 参考链接

- Claude Code Plugins: https://code.claude.com/docs/en/plugins/overview
- OpenAI Agent Plugins packaging: https://developers.openai.com/plugins/build/plugins
- Cursor Skills: https://cursor.com/docs/skills
- LightAgent connectors: `docs/connectors.md`
- MCP as plugins (Semantic Kernel 等): 配置挂载，非应用商店
