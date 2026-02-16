# feat: modular architecture — 115 tools consolidated to 21 + Assets/CMDB support + Change planning fixes

## Problem

VS Code Copilot enforces a **hard limit of 128 tools** across all MCP servers combined. With **115 `@mcp.tool()` decorators** in a single monolithic `server.py` (3200+ lines), the Freshservice MCP nearly exhausted the entire budget on its own — triggering VS Code's "Virtual Tools" mechanism which **groups tools into `activate_*` categories and disables individual tools**, effectively breaking the AI agent workflow.

## Solution

### 1. Full modularization — 115 tools → 21

The monolithic `server.py` is split into focused modules. Each consolidated tool uses an `action` parameter (e.g. `manage_ticket(action='create|update|delete|get|list|filter|get_fields')`) instead of exposing separate functions.

| Module | Original tools | Consolidated tools |
| -------- | :-: | :-: |
| `tools/tickets.py` | 11 | 3 |
| `tools/changes.py` | 33 | 5 |
| `tools/assets.py` | 22 | 3 |
| `tools/agents.py` | 10 | 2 |
| `tools/requesters.py` | 12 | 2 |
| `tools/solutions.py` | 13 | 1 |
| `tools/products.py` | 4 | 1 |
| `tools/misc.py` | 6 | 2 |
| `discovery.py` | — | 2 |
| **Total** | **115** | **21** |

### 2. Assets/CMDB support

- Full CRUD on assets, asset types, and relationships (bulk create/delete)
- Asset sub-resources: components, assignment history, requests, contracts
- Asset movement across workspaces
- Search & filter with Freshservice query syntax
- Async job status tracking for bulk operations

### 3. Change management fixes

- `update_change` refactored from opaque `Dict` parameter to explicit typed fields
- Planning fields (`reason_for_change`, `change_impact`, `rollout_plan`, `backout_plan`) now properly wrapped in `{"description": ...}` structure as required by the Freshservice API
- `close_change` simplified with keyword args instead of fragile dict mutation
- Added `assets`, `category`, `sub_category`, `item_category` fields support

## New features

- **`--scope` CLI flag** / `FRESHSERVICE_SCOPES` env-var — load only selected tool modules:

  ```bash
  freshservice-mcp --scope tickets changes  # only 8 tools loaded
  ```

- **Dynamic form-field discovery** — `discover_form_fields(entity='change')` queries the org's actual field templates instead of relying on hard-coded parameters
- **2-level TTL cache** — in-memory + on-disk (`~/.cache/freshservice_mcp/`), configurable via `FRESHSERVICE_CACHE_TTL` env-var (default 1h)
- **Shared HTTP client** (`http_client.py`) — consistent error handling, auth, and pagination parsing across all modules
- **Centralized config** (`config.py`) — all enums, constants, and env-var loading in one place

## Architecture

```text
src/freshservice_mcp/
├── server.py          # slim entrypoint (~90 lines)
├── config.py          # enums, constants, env config
├── http_client.py     # api_get/post/put/delete helpers
├── discovery.py       # dynamic field discovery + cache
└── tools/
    ├── __init__.py    # SCOPE_REGISTRY mapping
    ├── tickets.py     # manage_ticket, manage_ticket_conversation, manage_service_catalog
    ├── changes.py     # manage_change, manage_change_{note,task,time_entry,approval}
    ├── assets.py      # manage_asset, manage_asset_details, manage_asset_relationship
    ├── agents.py      # manage_agent, manage_agent_group
    ├── requesters.py  # manage_requester, manage_requester_group
    ├── solutions.py   # manage_solution
    ├── products.py    # manage_product
    └── misc.py        # manage_canned_response, manage_workspace
```

## Commits

1. `56c8656` — feat: add Assets/CMDB, Relationships and Asset Types management tools
2. `c49e9eb` — fix: correct relationship endpoints and add job status tracking
3. `c187b51` — fix: refactor update_change with explicit parameters for planning fields, assets, and categories
4. `18866bd` — refactor: modularize server — 115 tools consolidated to 21

## Stats

`16 files changed, 7368 insertions(+), 3322 deletions(-)`
