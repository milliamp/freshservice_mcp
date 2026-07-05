# Freshservice MCP Server

## About This Fork

This repository is an **independently maintained fork** of [`effytech/freshservice_mcp`](https://github.com/effytech/freshservice_mcp), continued here because active development on the upstream project has slowed. It is now developed as its own product and is **not intended to stay in sync with upstream**.

- **Original project:** https://github.com/effytech/freshservice_mcp — © the original authors (see `pyproject.toml` and `LICENSE`).
- **Fork point:** upstream commit [`2b6554b`](https://github.com/effytech/freshservice_mcp/commit/2b6554b58b30dd9c2199721f67f8e25752aacbbb) *"Merge pull request #15 from adamwestland/feature/add-changes-support"* (2025-10-06). Everything at or before that commit is upstream's work; everything after is this fork's.
- **What this fork adds** (relative to the fork point): a modular scope-based architecture, a `read_*` / `manage_*` permission split on every resource, consolidated sub-entity handling on tickets / problems / releases, coverage for many additional Freshservice resources (assets/CMDB, projects, status pages, procurement, contracts, software, custom objects, announcements, and more), dynamic form-field discovery, and other quality-of-life changes to the tool surface.

The MIT license is preserved from upstream. If you were previously using `@effytech/freshservice_mcp` via Smithery or PyPI, that continues to install the upstream package — install this fork directly from source (see [Getting Started](#getting-started)).

## Overview

A powerful MCP (Model Context Protocol) server implementation that seamlessly integrates with Freshservice, enabling AI models to interact with Freshservice modules and perform various IT service management operations. This integration bridge empowers your AI assistants to manage and resolve IT service tickets, streamlining your support workflow.

## Key Features

- **Enterprise-Grade Freshservice Integration**: Direct, secure communication with Freshservice API endpoints
- **AI Model Compatibility**: Enables Claude and other AI models to execute service desk operations through Freshservice
- **Modular Architecture**: 71 tools organized into 19 independently loadable scopes — load only what you need
- **Read/Manage Permission Split**: Every resource exposes a `read_*` and `manage_*` pair so MCP clients can grant read-only or read-write access independently
- **Consolidated Sub-Entities**: Ticket / problem / release sub-entities (notes, tasks, time entries, approvals) are dispatched through their parent tool rather than separate tools, keeping the tool surface small
- **Scope-Based Loading**: Use `FRESHSERVICE_SCOPES` env var or `--scope` CLI arg to control which tool modules are active
- **Dynamic Form Discovery**: Auto-discover custom fields for tickets, changes, problems, releases, assets

## Architecture

The server uses a modular scope-based architecture. Each scope exposes one or more `read_*` / `manage_*` tool pairs. Read-only tools accept `get / list / filter / view / get_fields`-style actions; manage tools accept create/update/delete/etc. Tools share a private handler so the two halves stay in sync — the wrappers only enforce the action whitelist.

| Scope | Tools (read / manage) | Notes |
| ----- | --------------------- | ----- |
| `tickets` | `read_ticket` / `manage_ticket`, `read_service_catalog` / `manage_service_catalog` | Ticket CRUD **plus** conversations, tasks, time entries, approvals (consolidated under `read_ticket` / `manage_ticket`). Service catalog stays separate. |
| `changes` | `read_change` / `manage_change`, `read_change_note` / `manage_change_note`, `read_change_task` / `manage_change_task`, `read_change_time_entry` / `manage_change_time_entry`, `read_change_approval` / `manage_change_approval` | Change requests. Sub-entities stay separate here — `manage_change` already carries 26 planning fields. |
| `problems` | `read_problem` / `manage_problem` | Problems CRUD plus notes, tasks, time entries — all consolidated. |
| `releases` | `read_release` / `manage_release` | Releases CRUD plus notes, tasks, time entries — all consolidated. |
| `assets` | `read_asset` / `manage_asset`, `read_asset_details`, `read_asset_relationship` / `manage_asset_relationship` | Assets/CMDB, types, sub-resource details (no writes), relationships. |
| `status_page` | `read_status_page` / `manage_status_page`, `read_maintenance_window` / `manage_maintenance_window` | Status pages, maintenance windows, incidents, components, subscribers. |
| `projects` | `read_project` / `manage_project`, `read_project_task` / `manage_project_task` | Project management (NewGen) — projects, members, associations, sprints, tasks. |
| `departments` | `read_department` / `manage_department` | Departments. |
| `locations` | `read_location` / `manage_location` | Locations. |
| `agents` | `read_agent` / `manage_agent`, `read_agent_group` / `manage_agent_group` | Agents and groups. |
| `requesters` | `read_requester` / `manage_requester`, `read_requester_group` / `manage_requester_group` | Requesters and groups. |
| `solutions` | `read_solution` / `manage_solution` | KB categories, folders, articles. |
| `products` | `read_product` / `manage_product` | Product catalog. |
| `procurement` | `read_purchase_order` / `manage_purchase_order`, `read_vendor` / `manage_vendor` | Purchase orders and vendors. |
| `contracts` | `read_contract` / `manage_contract` | Contracts and contract types. |
| `software` | `read_software` / `manage_software` | Software assets and licenses. |
| `announcements` | `read_announcement` / `manage_announcement` | Announcements. |
| `custom_objects` | `read_custom_object` / `manage_custom_object` | Custom object schemas and records. |
| `misc` | `read_canned_response`, `read_workspace`, `read_agent_role`, `read_business_hour`, `read_sla_policy`, `read_audit_log`, `read_alert` / `manage_alert`, `read_onboarding_request` / `manage_onboarding_request`, `read_offboarding_request` / `manage_offboarding_request` | Low-traffic resources. Several are read-only (no Freshservice write API). |

Additionally, 2 **discovery tools** are always loaded regardless of scope:

- `discover_form_fields` — Discover custom field definitions for any entity type (1-hour cache)
- `clear_field_cache` — Clear cached field definitions

**Total: 71 tools** (69 scoped + 2 discovery), 49 read + 42 manage.

Detailed action lists, required/optional parameters, filter-query syntax, and enum values are documented on each tool's own MCP schema and docstring rather than duplicated here — the LLM sees them directly at call time, which is where that information belongs.

### Design rationale

The tool layout changed substantially between the fork point and today. The reasoning:

- **Scope-based loading** — Upstream loaded every tool at startup. This fork grew Freshservice coverage from ~30 tools to 71, spanning tickets, changes, problems, releases, assets/CMDB, projects, status pages, procurement, contracts, software, custom objects and more. MCP clients enforce hard tool caps — VS Code Copilot maxes out at 128 tools across *all* servers combined — so opt-in scoping (via `FRESHSERVICE_SCOPES` env var or `--scope` CLI arg) lets deployments load only what the agent needs and stay under those limits.
- **`read_*` / `manage_*` permission split** — Many agent workflows (triage, reporting, on-call summaries, root-cause analysis) legitimately need read access without any write capability. Others need both. Splitting every resource into a read tool and a manage tool lets MCP clients grant only the half a given agent needs, which is the standard least-privilege model and dramatically shrinks blast radius. It also makes the boundary explicit to the LLM: read tools are safe to try during exploration; manage tools change state. Both halves share the same private handler so behaviour can't drift — the wrappers only enforce the action whitelist and rejection messages point the LLM at the correct counterpart.
- **Consolidated sub-entities** — A Freshservice ticket has conversations, tasks, time entries, and approvals — each with list/get/create/update/delete. Exposing all of that as separate tools multiplies the tool count and forces the LLM to pick from ~25 similarly-named neighbours (`create_ticket_note`, `create_ticket_task`, `create_ticket_time_entry`, ...). Consolidating them behind a single `action` parameter on the parent tool cuts the surface, keeps documentation coherent, and matches how humans model tickets (a ticket *has* notes; notes aren't a first-class resource). Problem and Release are consolidated the same way. **Change is the deliberate exception**: `manage_change` already carries 26 planning fields, so folding sub-entities in would push its parameter surface past what an LLM can reliably handle, so the sub-entities stay as separate tools there.
- **Unified `action` parameter with synonyms + smart defaults** — LLMs reach for different verbs for the same operation (`get`/`view`/`show`/`read`, `find`/`search`/`filter`, `list`/`index`/`all`). Every tool accepts a common set of synonyms and normalises them internally to the canonical name, so callers can use the verb that comes naturally without triggering "unknown action" errors. Read tools also apply a smart default when `action` is omitted: pass a `ticket_id` and it infers `get`; pass a `query` and it infers `filter`; pass neither and it infers `list`. This means many everyday calls collapse to a single argument.
- **Dynamic form-field discovery** — Freshservice custom fields vary per tenant and per module, so any tool that touches user-defined fields would either hardcode them (brittle, wrong for most tenants) or force the caller to know them in advance. Two always-loaded discovery tools (`discover_form_fields` + `clear_field_cache`) hit the live tenant, cache field definitions for an hour, and give the LLM the ground truth it needs before it tries to write a custom field it doesn't understand.

The net effect is a tool surface that scales past MCP client limits, holds up under least-privilege permissions, and stays legible to an LLM one prompt at a time.

## Getting Started

### Prerequisites

- A Freshservice account ([freshservice.com](https://www.freshservice.com))
- Freshservice API key
- Python >= 3.10

### Installing this fork

Install directly from GitHub — the Smithery / PyPI listing for `@effytech/freshservice_mcp` installs the upstream package, not this fork.

```bash
pip install git+https://github.com/milliamp/freshservice_mcp.git@main
```

Or with `uv` (recommended for MCP tooling):

```bash
uv tool install git+https://github.com/milliamp/freshservice_mcp.git@main
```

Both expose the `freshservice-mcp` CLI entry-point.

### Configuration

Generate your Freshservice API key:

1. Navigate to **Profile Settings → API Settings**
2. Copy your API key

### Usage with Claude Desktop

Add to your `claude_desktop_config.json`. Point `uvx` at the fork's git URL — `uvx freshservice-mcp` on its own resolves to the upstream package on PyPI, not this fork:

```json
"mcpServers": {
  "freshservice-mcp": {
    "command": "uvx",
    "args": [
      "--from",
      "git+https://github.com/milliamp/freshservice_mcp.git@main",
      "freshservice-mcp"
    ],
    "env": {
      "FRESHSERVICE_APIKEY": "<YOUR_API_KEY>",
      "FRESHSERVICE_DOMAIN": "yourcompany.freshservice.com"
    }
  }
}
```

If you've already run `uv tool install ...` (see [Installing this fork](#installing-this-fork)), you can simplify this to `"command": "freshservice-mcp"` with empty `args`.

### Usage with VS Code (Copilot)

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "freshservice": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "freshservice_mcp.server"],
      "env": {
        "PYTHONPATH": "/path/to/freshservice_mcp/src",
        "FRESHSERVICE_APIKEY": "<YOUR_API_KEY>",
        "FRESHSERVICE_DOMAIN": "yourcompany.freshservice.com"
      }
    }
  }
}
```

**WSL users** — use `wsl` as the command:

```json
{
  "servers": {
    "freshservice": {
      "type": "stdio",
      "command": "wsl",
      "args": [
        "-e", "env",
        "FRESHSERVICE_APIKEY=<YOUR_API_KEY>",
        "FRESHSERVICE_DOMAIN=yourcompany.freshservice.com",
        "PYTHONPATH=/path/to/freshservice_mcp/src",
        "python3", "-m", "freshservice_mcp.server"
      ]
    }
  }
}
```

### Scope Selection

By default all 19 scopes are loaded (69 scoped tools + 2 discovery = 71 tools, made up of 49 `read_*` + 42 `manage_*`). To load only specific scopes:

**Via environment variable:**

```bash
FRESHSERVICE_SCOPES=tickets,changes,status_page freshservice-mcp
```

**Via CLI argument:**

```bash
freshservice-mcp --scope tickets changes problems
```

This is useful when you have many MCP servers and need to stay under client tool limits (e.g. VS Code Copilot's 128-tool cap).

## Example Operations

Once configured, you can ask your AI assistant to:

**Tickets:**

- "Create a high priority incident ticket about network connectivity issues in Marketing"
- "List all critical incidents reported in the last 24 hours"
- "Update ticket #12345 status to resolved"

**Changes:**

- "Create a change request for scheduled server maintenance next Tuesday at 2 AM"
- "Close change #5092 with result explanation 'Successfully deployed to production'"
- "List all pending changes awaiting approval"

**Problems:**

- "Create a problem for recurring VPN disconnections, assign to Network team"
- "Add an analysis note to problem #301 with root cause findings"

**Releases:**

- "Create a minor release for the Q1 frontend deployment, planned for March 15-16"
- "List all in-progress releases"

**Status Page / Maintenance:**

- "Create a maintenance window on the status page linked to change #5100"
- "List all service components on our public status page"

**Projects:**

- "List all active projects"
- "Show all tasks in project #2000251059 that are In Progress"
- "Create a new task in project #2000194127 titled 'Deploy monitoring agent'"
- "Find all my non-closed tasks across all projects"

**Assets / CMDB:**

- "List all assets in the CMDB"
- "Create a new hardware asset named 'Dell Latitude 5540'"
- "Show all relationships for asset #42"

**Departments & Locations:**

- "List all departments"
- "Create a new location 'Paris Office' with address details"

## Testing

Start the server manually for testing:

```bash
FRESHSERVICE_APIKEY=<key> FRESHSERVICE_DOMAIN=<domain> python3 -m freshservice_mcp.server
```

Or with `uvx` against the fork's git URL (a bare `uvx freshservice-mcp` would resolve to upstream on PyPI):

```bash
FRESHSERVICE_APIKEY=<key> FRESHSERVICE_DOMAIN=<domain> \
  uvx --from git+https://github.com/milliamp/freshservice_mcp.git@main freshservice-mcp
```

## Troubleshooting

- Verify your Freshservice API key and domain are correct
- Ensure proper network connectivity to Freshservice servers
- Check API rate limits and quotas
- If tools appear "disabled" in VS Code Copilot, you may have exceeded the 128-tool limit across all MCP servers — use `FRESHSERVICE_SCOPES` to load fewer scopes
- Check server logs: the server logs which scopes and how many tools were loaded at startup

## License

This MCP server is licensed under the MIT License, inherited from the upstream project. See the `LICENSE` file for full details; original copyright is retained.

## Additional Resources

- [Freshservice API Documentation](https://api.freshservice.com/)
- [Upstream project (`effytech/freshservice_mcp`)](https://github.com/effytech/freshservice_mcp) — the fork point
- [Claude Desktop Integration Guide](https://docs.anthropic.com/claude/docs/claude-desktop)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)

---

<p align="center">Originally built by effy · forked and maintained by <a href="https://github.com/milliamp">milliamp</a>.</p>
