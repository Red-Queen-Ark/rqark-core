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

全部繼承 `BaseTool`，傳入 `AgentCore` 就會自動變成 OpenAI function calling schema，由模型決定幾時呼叫。

| 工具 | name | 參數 | 用途 |
|---|---|---|---|
| ReadFile | `read_file` | `path`、`offset`、`limit`（default 2000） | 讀檔案，逐行加行號 |
| WriteFile | `write_file` | `path`、`content` | 寫檔案，自動建 parent 目錄 |
| EditFile | `edit_file` | `path`、`old_string`、`new_string`、`replace_all` | 精確字串替換 |
| ListDir | `list_dir` | `path`（default 當前目錄） | 列出目錄內容，子目錄加 `/` 尾綴 |
| Grep | `grep` | `pattern`、`path`、`include` | 搜尋檔案內容，輸出 `path:line: content`（max 200 匹配，跳過 `.git`/`.venv` 等） |
| Exec | `exec` | `command`、`working_dir`、`timeout`（max 300） | 執行 shell command（default 60s，command 上限 2000 chars） |
| WebSearch | `web_search` | `query` | DuckDuckGo 搜尋（max 10 結果，有黑名單過濾） |
| WebFetch | `web_fetch` | `url` | 抓網頁變純文字（30s timeout，帶信源評分） |

## 提示詞

全部繼承 `BasePrompt`，有 `priority` 排序同 `get_messages()`。用嚟生成 system prompt 內容。

| 提示詞 | priority | 參數 | 輸出 |
|---|---|---|---|
| RolePrompt | 10 | `agent_name`（default `Red Queen Ark`）、`user_name`（default `Sir`） | 角色設定 |
| CharacterPrompt | 15 | `identity`、`personality` | 身份、性格、規則（兩個都空就唔輸出） |
| PlatformPrompt | 30 | — | 平台提示（win/mac/linux 自動偵測） |
| WorkspacePrompt | 40 | `cwd` | 工作目錄（未喺 `__init__` export，要 `from rqark_core.prompts.workspace import WorkspacePrompt`） |
| AgentsMdPrompt | 50 | `cwd` | 讀 `AGENTS.md` 做專案規則（無檔案就唔輸出） |
| DateTimePrompt | 60 | `timezone_name`（default `Asia/Hong_Kong`） | 當前時間同 UTC offset |
| GitProjectPrompt | 70 | `cwd` | Git 分支、HEAD、status、最近 commit |

## 用法

```python
import asyncio
from rqark_core.core import AgentCore
from rqark_core.types.provider import Provider
from rqark_core.types.chat import UserMessage, SystemMessage
from rqark_core.prompts import RolePrompt, DateTimePrompt, PlatformPrompt
from rqark_core.tools import WebSearch, WebFetch, ReadFile, WriteFile

provider = Provider('inhouse', 'api_key', 'http://127.0.0.1:8080', 0)

prompts = [DateTimePrompt(), RolePrompt(), PlatformPrompt()]
prompts.sort(key=lambda p: p.priority)

core = AgentCore(provider, [WebSearch(), WebFetch(), ReadFile(), WriteFile()])


@core.on_chunk()
async def on_chunk(chunk):
    print(chunk.type, chunk.content)


async def main():
    system_prompts = [SystemMessage('')]
    for prompt in prompts:
        if p := prompt.get_messages():
            system_prompts[0].content += p
    error, messages = await core.chat([UserMessage('今日天氣')], system_prompts)


asyncio.run(main())
```

`chat()` 回傳 `(error, history)`：成功時 `error` 係 `None`，`history` 係完整對話記錄（包括工具往返）；失敗時 `error` 係錯誤訊息。

`on_chunk` 事件類型：`reasoning_content`、`content`、`tool_calls`、`tool_result`、`usage`、`error`。
