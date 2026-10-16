# rqark-core
## Overview
無狀態 AI 引擎，提供 常用 Agent Tool 和 Prompt，統一串流 Agent Event 接口

## Quick Start
在專案 `pyproject.toml` 中加入

```toml
[[tool.uv.index]]
name = "gitea"
url = "https://gitea.carhyme.top/api/packages/RedQueenArk/pypi/simple"
publish-url = "https://gitea.carhyme.top/api/packages/RedQueenArk/pypi"
explicit = true

[tool.uv.sources]
rqark-core = { index = "gitea" }
```

設定認證

```bash
uv auth login https://gitea.carhyme.top/api/packages/RedQueenArk/pypi/simple
```

安裝

```bash
uv add rqark-core
```

## Features
### Provider
- `Provider` 有 `reasoning_effort`、`thinking`（`'enabled'` / `'disabled'`，控制 thinking 模式）。
- `temperature`、`top_p`、`seed`、`frequency_penalty`、`presence_penalty` 等欄位（後者暫時未接入），
- `combine`（將 system + tool prompts 合併做一個 `SystemMessage`）。

### Tools
- 全部繼承 `BaseTool`，傳入 `AgentCore.chat()` 就會自動變成 OpenAI function calling schema，由模型決定幾時呼叫。

| 工具 | name | 參數 | 用途 |
|---|---|---|---|
| ReadFile | `read_file` | `path`、`offset`、`limit`（default 2000） | 讀檔案，逐行加行號 |
| WriteFile | `write_file` | `path`、`content` | 寫檔案，自動建 parent 目錄 |
| EditFile | `edit_file` | `path`、`old_string`、`new_string`、`replace_all` | 精確字串替換（同一檔案唔可以並行編輯） |
| ListDir | `list_dir` | `path`（default 當前目錄） | 列出目錄內容，子目錄加 `/` 尾綴；跳過 `.git`、`node_modules`、`.venv`、`__pycache__` 等 |
| Grep | `grep` | `pattern`、`path`、`include`、`include_ignored` | 搜尋檔案內容，輸出 `path:line: content`（max 200 匹配，檔案上限 1MB，跳過 `.git`/`.venv` 等；目錄搜尋預設跟 `.gitignore`，`include_ignored=true` 可以連 ignored 檔都搜） |
| Exec | `exec` | `command`、`working_dir`、`timeout`（max 300） | 執行 shell command（default 60s，command 上限 2000 chars，alias：`shell`） |
| WebSearch | `web_search` | `query` | DuckDuckGo 搜尋（max 10 結果，黑名單 + 關鍵字過濾） |
| WebFetch | `web_fetch` | `url` | 抓網頁變純文字（30s timeout，HTML 最多 200 行，帶信源評分） |
| PlanUpdate | `plan_update` | `items`（array of `{id, content, status}`） | 更新 session plan；會將當前 plan 渲染做 tool prompt |
| SubAgent | `subagent` | `prompt` | 用獨立 context 委派任務；chunk/message 事件以 `(id, ...)` 轉發返父 core |
| GitHub | `github` | `action` + 各 action 參數 | GitHub API：repos、issues、PRs、milestones、labels、branches、releases |
| Gitea | `gitea` | `action` + 各 action 參數 | Gitea API（同上，另加 `list_commits`、`compare`、`create_branch`、`delete_branch`、`set_issue_labels`） |
| GitLab | `gitlab` | `action` + 各 action 參數 | GitLab API（同上，另加 `list_commits`、`compare`） |

Git tool 全部繼承 `BaseGitTool`，用單一 `action` 參數分派（例如 `list_issues`、`create_pull_request`、`merge_pull_request`）。認證同 base URL 一律經 constructor params 傳入：`token`（必填，否則每個 action 都回 token not configured）、`username`（只有 Gitea 用，clone 時需要）、`base_url`（選填，預設 `api.github.com`、`gitea.com`、`gitlab.com`）。`clone_repo` 會 clone 到當前工作目錄嘅 `repos/<repo>`。

Gitea 嘅 `create_issue`、`create_pull_request`、`update_pull_request` 支援 `labels`（label ID array）、`milestone`（milestone ID）、`due_date`；`list_labels` / `list_milestones` 輸出會帶 ID。`merge_pull_request` 嘅 `merge_method` 另有 `fast-forward-only`，並支援 `force_merge`。

### Prompts
- 全部繼承 `BasePrompt`，有 `priority` 同 `get_messages()`。
- `AgentCore` 內部會自動按 `priority` 排序，`get_messages()` 回傳 `None` 就跳過。
- 用嚟生成 system prompt 內容。

| 提示詞 | priority | 參數 | 輸出 |
|---|---|---|---|
| RolePrompt | 10 | `agent_name`（default `Red Queen Ark`）、`user_name`（default `Sir`） | 角色設定 |
| AntiSycophancyPrompt | 12 | — | 反奉承規則：唔好盲目同意、指出錯處、唔好廢話開場白/收尾、唔肯定就講唔知 |
| CharacterPrompt | 15 | `identity`、`personality` | 身份、性格、規則（兩個都空就唔輸出） |
| SubAgentPrompt | 20 | — | subagent 角色、規則、品質清單 |
| PlatformPrompt | 30 | — | 平台提示（win/mac/linux 自動偵測） |
| WorkspacePrompt | 40 | `cwd` | 指明Agent當前工作目錄 |
| AgentsMdPrompt | 50 | `cwd` | 讀 `AGENTS.md` 做專案規則（無檔案就唔輸出） |
| DateTimePrompt | 60 | `timezone_name`（default `Asia/Hong_Kong`） | 當前時間同 UTC offset |
| GitProjectPrompt | 70 | `cwd` | Git 分支、HEAD、status（最多 40 行）、最近 10 個 commit |

### Agent Core
#### Event
| 裝飾器 | 事件內容 |
|---|---|
| `on_chunk` | `AgentPayload[Chunk]`（`agent_id` + `path` + `Chunk`，`Chunk.type`：`reasoning_content`、`content`、`tool_calls`、`tool_result`、`usage`、`error`；支援多層 subagent 嵌套） |
| `on_message` | `AgentPayload[Message]`（user / tool / assistant / system） |
| `on_plan` | `AgentPayload[list[PlanItem]]` |

#### Plan
用 `PlanUpdate()` 開 plan，追蹤 multi-step task。Plan 存喺 `AgentCore.plan_items`（每個 core 各自一份），每次呼叫要回傳**完整** items list。

`PlanItem` 有 `id`、`content`、`status`（`pending` / `in_progress` / `completed` / `cancelled`）。同時只准一個 `in_progress`；空 list 或全部 completed 會自動清空。當前 plan 會 render 入 tool prompt，每次更新都會 fire `on_plan`。

#### Sub Agent
`SubAgent(prompts, tools)` 用獨立 context 跑一個新 `AgentCore`，process 完只回最終字串結果。Provider 沿用父 core，prompts / tools 由 constructor 決定。

子 core 嘅 `chunk` / `message` / `plan` 會連 `agent_id`、`path` 一齊轉發返父 core，所以 listener 可以靠 `(path, agent_id)` 分辨層數，支援多層嵌套。冇遞歸深度限制。

## Example

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
    history, error = await core.chat(provider, [UserMessage('今日天氣')], prompts, tools)


asyncio.run(main())
```

- 成功時 `error` 係 `None`，`history` 係完整對話記錄（包括工具往返）；失敗時 `error` 係 `Exception` 物件。
