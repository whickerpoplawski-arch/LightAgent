# LightAgent 本地插件系统（轻量）

在 `local/` 旁路实现：目录即插件，复制/软链即安装，`enabled.json` 控制启用。  
**无 marketplace、默认不下载远程代码、不改上游 core。**

## 目录

```
local/
  plugins/                         # 已安装插件
    enabled.json
    hello_plugin/                  # install 后出现
  plugins_system/
    manifest.py / manager.py / agent_bridge.py
    examples/hello_plugin/         # 演示源
    RESEARCH.md                    # 选型说明
```

## 插件长什么样

```
my_plugin/
  manifest.yaml
  tools.py          # 可选
  skills/           # 可选（SKILL.md）
  mcp.json          # 可选（只声明，不自动连接）
```

`manifest.yaml` 示例：

```yaml
name: hello_plugin
version: 0.1.0
description: 演示插件
entrypoints:
  tools: tools.py
  skills: skills
```

`tools.py` 里函数需带 `tool_info`（与 LightAgent 一致），或导出 `TOOLS = [...]`。

## 用法

在仓库根目录 `/workspace/LightAgent`：

```bash
# 安装演示插件（复制到 local/plugins/，并启用）
PYTHONPATH=. python -m local.plugins_system install local/plugins_system/examples/hello_plugin
# 也可：GitHub URL 或 owner/repo（需本机 git + 网络）
# PYTHONPATH=. python -m local.plugins_system install owner/repo

# 软链安装（改源码即时生效）
PYTHONPATH=. python -m local.plugins_system install local/plugins_system/examples/hello_plugin --symlink

# 列表 / 启用 / 禁用 / 卸载
PYTHONPATH=. python -m local.plugins_system list
PYTHONPATH=. python -m local.plugins_system enable hello_plugin
PYTHONPATH=. python -m local.plugins_system disable hello_plugin
PYTHONPATH=. python -m local.plugins_system uninstall hello_plugin

# 加载已启用插件（不调任何 LLM API）
PYTHONPATH=. python -m local.plugins_system load
```

Python API：

```python
from local.plugins_system import install, list_plugins, enable, load_enabled_plugins
from local.plugins_system.agent_bridge import make_agent_with_plugins

install("local/plugins_system/examples/hello_plugin")
print(list_plugins())
loaded = load_enabled_plugins()
# loaded.tools / loaded.skills_directories / loaded.mcp_servers

# 接 OpenRouter 免费护栏（会消耗额度，慎用）
# agent = make_agent_with_plugins()
```

冒烟（零 API）：

```bash
PYTHONPATH=. python -m local.plugins_system.smoke_test
```


## 适配 Cursor / Superpowers 类仓库

GitHub 安装时若仓库**没有** `manifest.yaml`，但有 `skills/*/SKILL.md`
（例如 [obra/superpowers](https://github.com/obra/superpowers)），安装器会：

1. 读取 `.cursor-plugin/plugin.json`（或 package.json）取 name/version/description
2. 生成临时 wrapper（`manifest.yaml` + `skills` 软链），**不改上游文件**
3. `copytree` 跟进 softlink，装到 `local/plugins/<name>/`

```bash
PYTHONPATH=. python -m local.plugins_system install obra/superpowers
PYTHONPATH=. python -m local.plugins_system list   # [ON] superpowers@7.0.0 (skills)
```

## 与上游 Connector 的关系

上游 `ConnectorManifest` = 内存清单 + 离线校验，**没有 install**。  
本系统 = 文件系统生命周期（install/enable/load），加载结果仍走 `tools=` / `skills_directories=`，可再包成 Connector 做校验。

## TUI

LightAgent TUI 左下角 ⚙ →「插件」可安装/开关；见 `local/tui/README.md`。

## Not plugins

`web_search` / `web_fetch` are **first-class tools** in `local/tools/web.py` (wired via `local/tui/tools.TOOLS`). Do **not** install a `web_tools` plugin for them. Browser automation is Skill `skills/browser-use/` ([browser-use/browser-use](https://github.com/browser-use/browser-use)).
