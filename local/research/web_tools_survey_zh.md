# web_search / web_fetch 高星实现调研（面向 LightAgent 二开）

调研日期：2026-10-12（America/Martinique）。本调研只用外部 WebSearch/WebFetch，**未消耗** OpenRouter 免费额度。

## 一、七类实现方式

### 1) 官方 / 专用搜索 API
| 服务 | 代表集成 | 免费情况 | 备注 |
|---|---|---|---|
| **Tavily** | LangChain `langchain-tavily`、CrewAI `TavilySearchTool` | ~1000 credits/月，免绑卡 | Agent 友好：结构化结果+摘要；质量高 |
| **Brave Search** | 官方 MCP `@modelcontextprotocol/server-brave-search`；Anthropic 常推荐 | ~$5 月度 credit≈1000 次；**通常需绑卡** | 独立索引；Claude 生态常用 |
| **Exa** | OpenRouter 默认 fallback；语义检索 | 基本付费 | 嵌入+关键词混合，适合 research |
| **SerpAPI** | 各类 SEO/agent 示例 | 试用后付费 | Google SERP 保真，非 LLM 友好正文 |
| **Google CSE** | 老项目常见 | 100 次/天；**对新客户收紧/迁移中** | 需 key+cx，长期风险高 |
| **Bing Web Search API** | 历史 Azure 集成 | **已于 2025-08-11 下线** | 勿再选 |

**高星宿主自带（非开放给 LightAgent）：**
- OpenAI Agents SDK：`WebSearchTool` → Responses API **托管执行**
- Anthropic Claude：`web_search_*` / `web_fetch_*` **服务端工具**（Claude Code 内置 WebSearch+WebFetch）

### 2) 聚合器 / OpenRouter 风格
- OpenRouter **`openrouter:web_search` server tool**（推荐替代已弃用的 `plugins: [{id:web}]` / `:online`）
- 引擎：`auto|native|exa|firecrawl|parallel|perplexity`
- **即使挂在 `:free` 模型上也会另收费**（Exa 约 $0.007/次起；文档明确 *Using web search will incur extra costs, even with free models*）
- **不适合**「没钱、只啃免费额度」的当前约束

### 3) 免费 HTML 抓取（DuckDuckGo / Bing HTML）
- 代表：`ddgs`（原 `duckduckgo-search`，GitHub ~3k⭐）、DeepSeek-Harness 社区 DuckDuckGo shim、各类 MCP（`mcp-duckduckgo`、`web-search-in-mcp`、`tickernelz/mcp-web-search`）
- 做法：请求 `html.duckduckgo.com` 等 → 解析标题/URL/摘要
- **优点**：零 key、零费用、Python 一把梭
- **风险**：反爬/限流、HTML 变更易碎、ToS 灰色、结果质量不稳、偶发 CAPTCHA；Bing HTML 往往还要无头浏览器

### 4) Browser-use / Playwright 当 web_fetch
- 代表：LightAgent 自带 `example/08.browser_use.py`（`browser_data_fetcher`）；`fetcher-mcp`、`browse-mcp`、`zen-mcp/browser`、`mcp-browser-use`
- 能跑 JS、登录页、动态站；代价是 Chromium 依赖重、慢、占资源；若「浏览器里再开 agent」还会**二次烧 LLM token**
- 适合「静态 fetch 失败时的后备」，不适合默认路径

### 5) 简单 HTTP GET + 可读性抽取
- 栈：`httpx`/`requests` + `trafilatura` / `readability-lxml` / `html2text` / `markdownify`
- 官方 MCP **`mcp-server-fetch`**：拉 URL → Markdown（轻量、可复用）
- 社区常见：`fetch_url` 剥脚本/导航，截断长度，防 SSRF（禁 localhost/私网）
- **最适合当一等公民 `web_fetch`**

### 6) MCP web-search / fetch 服务器
- 官方：`mcp-server-fetch`；Brave Search MCP
- 社区：Brave+DDG fallback、Playwright fetch、SearXNG 自托管
- LightAgent **已有 MCPClientManager**，可接；但多一层进程，调试/依赖比本地 `tool_info` 函数重
- 适合「用户已有 MCP」或「想与 Cursor/Claude 共用同一服务器」

### 7) Shell `curl` 当工具 vs 一等工具
| | Shell curl | 一等 `web_fetch`/`web_search` |
|---|---|---|
| 结构化返回 | 差（原始 HTML/JSON） | 好（title/url/snippet/markdown） |
| SSRF/安全 | 难（模型可打内网） | 易（白名单/禁私网） |
| TUI 轨迹可视 | 变成「执行了命令」 | 天然 tool chip |
| 模型负担 | 高（自己解析） | 低 |
| 结论 | 应急调试 OK | **产品默认应一等工具** |

---

## 二、对照表（是否适合本 Agent）

| 方式 | 费用 | 依赖重 | 质量 | 与 LightAgent 契合 | 推荐度 |
|---|---|---|---|---|---|
| OpenAI/Anthropic 托管搜索 | 付费/绑模型 | 低 | 高 | 当前走 OpenRouter `:free`，不可用 | ✗ |
| OpenRouter `web_search` / `:online` | **另收费** | 极低 | 高 | 直接撞「没钱」红线 | ✗ |
| Tavily / Brave API | 有免费档 | 低 | 高 | 可选增强（Brave 常要绑卡） | △ 后备 |
| Google CSE / SerpAPI / Bing | 紧/付费/已死 | 低 | 中高 | 不划算 | ✗ |
| **DDG (`ddgs`) HTML** | **$0** | 低 | 中 | 完美贴合免费约束 | ✅ 主搜 |
| **httpx + 可读性抽取** | **$0** | 低 | 中高（静态页） | 已依赖 httpx；tool_info 即插 | ✅ 主拉 |
| MCP fetch / Brave MCP | 0 / 免费档 | 中 | 中高 | 已有 MCP，但偏重 | △ 可选 |
| Playwright / browser-use | $0(+token) | **高** | 高（动态页） | 已有示例，作 fallback | △ 后置 |
| Shell curl | $0 | 无 | 低 | 不安全、难可视 | ✗ 不作默认 |

---

## 三、给 LightAgent 的推荐

### 主推（最轻、零花钱）
做一个本地插件 **`web_tools`**（走现有 `local/plugins_system`）：

```
local/plugins/web_tools/
  manifest.yaml
  tools.py          # web_search + web_fetch（tool_info）
  requirements 暗示: ddgs, httpx, trafilatura|html2text
```

- **`web_search(query, max_results=5)`**  
  默认 `ddgs.DDGS().text(...)` → 返回 `[{title, url, snippet}, ...]` JSON/Markdown  
  可选环境变量：若设了 `BRAVE_API_KEY` / `TAVILY_API_KEY` 则优先官方 API，失败再 DDG（provider chain）
- **`web_fetch(url, max_chars=8000)`**  
  `httpx` GET（超时、UA、跟随跳转上限）→ 可读性抽取 → Markdown/纯文本截断  
  **必做 SSRF**：禁 `file:`、localhost、RFC1918、link-local；限制重定向目标
- 安装形态与 `hello_plugin` 一致：`manifest.yaml` + `tools.py`；TUI 插件页开关热加载
- Mock 轨迹里的同名工具换成真实现，轨迹/对话芯片不用改产品语义

### 后备（按需升级，仍尽量免费）
1. **静态页失败 / SPA**：再挂 LightAgent 示例同款 `browser_data_fetcher`（Playwright/browser-use），或 MCP `fetcher-mcp`——默认关闭  
2. **搜索质量不够**：用户自愿申请 **Tavily 免费 1000/月**（免绑卡优先于 Brave）或自建 **SearXNG**  
3. **已有 MCP 工作流**：`mcp-server-fetch` +（可选）Brave MCP，经现有 MCPClientManager 接入——不必重写，但不是最轻默认

### 明确不要做的
- 默认启用 OpenRouter `:online` / `openrouter:web_search`（烧钱）
- 只暴露 `curl` shell 当联网能力
- 默认启动无头浏览器当唯一 fetch

### 为何这是「最轻且最贴」
- 对齐 TUI 已 mock 的工具名与轨迹可视化  
- 复用 `tool_info` + 插件开关，不动 `core.py`  
- 零 API 账单；搜索用成熟 `ddgs`，抓取用已有 httpx 生态  
- MCP / browser-use / 付费 API 全部可后挂，不堵死升级路径

## 四、建议落地顺序
1. 插件骨架 + `web_fetch`（可单测、零模型）  
2. `web_search`（ddgs）+ SSRF/截断  
3. 挂进 TUI `TOOLS` / 插件启用列表，mock 改真  
4. （可选）provider env 切换 Tavily/Brave  
5. （可选）browser-use fallback 与 MCP 双轨

## 落地决议（2026-10-12）

- `web_search` / `web_fetch`：**一等 Tools**（`local/tools/web.py` → `local/tui/tools.TOOLS`），**不是**插件。
- `browser-use`：**Skill**（`skills/browser-use/`），对接真实上游 https://github.com/browser-use/browser-use ，对齐 `example/08.browser_use.py`。
