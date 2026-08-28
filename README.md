# rqark-core

## 安裝

喺專案 `pyproject.toml` 加入：

```toml
[[tool.uv.index]]
name = "gitea"
url = "https://gitea.carhyme.top/api/packages/RedQueenArk/pypi/simple"
publish-url = "https://gitea.carhyme.top/api/packages/RedQueenArk/pypi"
explicit = true

[tool.uv.sources]
rqark-core = { index = "gitea" }
```

設定認證：

```bash
uv auth login https://gitea.carhyme.top/api/packages/RedQueenArk/pypi/simple
```

Username 填 Gitea 帳戶名，Password 填 Personal Access Token（scope: `read:package`）。

CI 用環境變數：

```bash
export UV_INDEX_GITEA_USERNAME=<用户名>
export UV_INDEX_GITEA_PASSWORD=<token>
```

安裝：

```bash
uv add rqark-core
```

唔用 uv 嘅話：

```bash
pip install rqark-core --extra-index-url https://<用户名>:<token>@gitea.carhyme.top/api/packages/RedQueenArk/pypi/simple/
```

## 工具組

全部繼承 `BaseTool`，傳入 `AgentCore.chat()` 就會自動變成 OpenAI function calling schema，由模型決定幾時呼叫。
需要 parent core / provider 嘅 tool（`PlanUpdate`、`SubAgent`）喺 `chat()` 期間會由 `AgentCore` 經 `ctx` 參數顯式傳入 `ToolContext`（包含 `core` 同 `provider`），唔使喺 constructor 手動傳入。同一個 tool instance 可以同時俾多個 core 用。

| 工具 | name | 參數 | 用途 |
|---|---|---|---|
| ReadFile | `read_file` | `path`、`offset`、`limit`（default 2000） | 讀檔案，逐行加行號 |
| WriteFile | `write_file` | `path`、`content` | 寫檔案，自動建 parent 目錄 |
| EditFile | `edit_file` | `path`、`old_string`、`new_string`、`replace_all` | 精確字串替換（同一檔案唔可以並行編輯） |
| ListDir | `list_dir` | `path`（default 當前目錄） | 列出目錄內容，子目錄加 `/` 尾綴；跳過 `.git`、`node_modules`、`.venv`、`__pycache__` 等 |
| Grep | `grep` | `pattern`、`path`、`include` | 搜尋檔案內容，輸出 `path:line: content`（max 200 匹配，檔案上限 1MB，跳過 `.git`/`.venv` 等） |
| Exec | `exec` | `command`、`working_dir`、`timeout`（max 300） | 執行 shell command（default 60s，command 上限 2000 chars，alias：`shell`） |
| WebSearch | `web_search` | `query` | DuckDuckGo 搜尋（max 10 結果，黑名單 + 關鍵字過濾） |
| WebFetch | `web_fetch` | `url` | 抓網頁變純文字（30s timeout，HTML 最多 200 行，帶信源評分） |
| PlanUpdate | `plan_update` | `items`（array of `{id, content, status}`） | 更新 session plan；會將當前 plan 渲染做 tool prompt |
| SubAgent | `subagent` | `prompt` | 用獨立 context 委派任務；chunk/message 事件以 `(id, ...)` 轉發返父 core |

## 提示詞

全部繼承 `BasePrompt`，有 `priority` 同 `get_messages()`。`AgentCore` 內部會自動按 `priority` 排序，`get_messages()` 回傳 `None` 就跳過。用嚟生成 system prompt 內容。

| 提示詞 | priority | 參數 | 輸出 |
|---|---|---|---|
| RolePrompt | 10 | `agent_name`（default `Red Queen Ark`）、`user_name`（default `Sir`） | 角色設定 |
| AntiSycophancy | 12 | — | 反奉承規則：唔好盲目同意、指出錯處、唔好廢話開場白/收尾、唔肯定就講唔知 |
| CharacterPrompt | 15 | `identity`、`personality` | 身份、性格、規則（兩個都空就唔輸出） |
| SubAgentPrompt | 20 | — | subagent 角色、規則、品質清單（未喺 `__init__` export，要 `from rqark_core.prompts.subagent import SubAgentPrompt`） |
| PlatformPrompt | 30 | — | 平台提示（win/mac/linux 自動偵測） |
| WorkspacePrompt | 40 | `cwd` | 工作目錄（未喺 `__init__` export，要 `from rqark_core.prompts.workspace import WorkspacePrompt`） |
| AgentsMdPrompt | 50 | `cwd` | 讀 `AGENTS.md` 做專案規則（無檔案就唔輸出） |
| DateTimePrompt | 60 | `timezone_name`（default `Asia/Hong_Kong`） | 當前時間同 UTC offset |
| GitProjectPrompt | 70 | `cwd` | Git 分支、HEAD、status（最多 40 行）、最近 10 個 commit |

## 用法

```python
import asyncio
from rqark_core.core import AgentCore
from rqark_core.types.provider import Provider
from rqark_core.types.chat import UserMessage
from rqark_core.prompts import RolePrompt, DateTimePrompt, PlatformPrompt
from rqark_core.tools import WebSearch, WebFetch, ReadFile, WriteFile, SubAgent, PlanUpdate

provider = Provider('inhouse', 'api_key', 'http://127.0.0.1:8080', 0)

core = AgentCore()

prompts = [RolePrompt(), DateTimePrompt(), PlatformPrompt()]
tools = [WebSearch(), WebFetch(), ReadFile(), WriteFile()]
tools = tools + [SubAgent(prompts, tools), PlanUpdate()]


@core.on_chunk()
async def on_chunk(chunk):
    print(chunk.type, chunk.content)


async def main():
    messages, error = await core.chat(provider, [UserMessage('今日天氣')], prompts, tools)


asyncio.run(main())
```

`chat(provider, messages, prompts, tools)` 回傳 `(history, error)`（跟 Go 慣例，值行先、error 行後）：成功時 `error` 係 `None`，`history` 係完整對話記錄（包括工具往返）；失敗時 `error` 係 `Exception` 物件。

`AgentCore` 事件：

| 裝飾器 | 事件內容 |
|---|---|
| `on_chunk` | `Chunk`，`type`：`reasoning_content`、`content`、`tool_calls`、`tool_result`、`usage`、`error` |
| `on_message` | `Message`（user / tool / assistant / system） |
| `on_subagent_chunk` | `SubAgentChunk`（`id` + `Chunk`） |
| `on_subagent_message` | `SubAgentMessage`（`id` + `Message`） |
| `on_plan` | `list[PlanItem]` |

`Provider` 有 `reasoning_effort`、`thinking`、`temperature`、`top_p`、`seed`、`frequency_penalty`、`presence_penalty` 等欄位（目前未接入 API 請求），同埋 `combine`（將 system + tool prompts 合併做一個 `SystemMessage`）。
