# Freshservice MCP Server

[![smithery badge](https://smithery.ai/badge/@effytech/freshservice_mcp)](https://smithery.ai/server/@effytech/freshservice_mcp)

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

## Tools Reference

Every tool uses a unified `action` parameter to select the operation. The action whitelist is enforced inside each tool — `read_*` accepts read actions, `manage_*` accepts write actions, and the rejection message tells the LLM which counterpart to call.

### Ticket Management (`tickets` scope)

**`read_ticket`** — Actions: `get`, `list`, `filter`, `get_fields`, `list_conversations`, `list_tasks`, `get_task`, `list_time_entries`, `get_time_entry`, `list_approvals`, `get_approval`

**`manage_ticket`** — Actions: `create`, `update`, `delete`, `reply`, `add_note`, `update_conversation`, `add_task`, `update_task`, `delete_task`, `add_time_entry`, `update_time_entry`, `delete_time_entry`, `add_approval`, `approve`, `reject`, `remind`

| Action | Required | Notes |
| ------ | -------- | ----- |
| `create` | `subject`, `description`, (`email` OR `requester_id`) | Source / priority / status default if omitted; long-tail via `payload`. |
| `update` / `delete` | `ticket_id` | |
| `reply` / `add_note` | `ticket_id`, `body` | `payload.cc_emails`, `payload.bcc_emails`, `payload.private` etc. |
| `add_task` | `ticket_id`, `title` | Optional: `description`, `status`, `payload.{due_date, notify_before, group_id, agent_id}` |
| `update_task` / `delete_task` | `ticket_id`, `task_id` | |
| `add_time_entry` | `ticket_id`, `time_spent`, `payload.te_agent_id` | `body` becomes the work note; `payload.billable`, `payload.executed_at` etc. |
| `add_approval` | `ticket_id`, `approver_id` | `payload.approval_type`, `payload.email_content` |
| `approve` / `reject` / `remind` | `ticket_id`, `approval_id` | |

**`read_service_catalog`** — Actions: `list_items`, `get_requested_items`. **`manage_service_catalog`** — Action: `place_request`.

### Change Management (`changes` scope)

Change family stays as separate sub-entity tools (unlike ticket/problem/release) because `manage_change` itself already carries 26 planning fields — merging the sub-entities would push the parameter surface past the point an LLM can handle reliably.

**`read_change`** — Actions: `get`, `list`, `filter`, `get_fields`
**`manage_change`** — Actions: `create`, `update`, `delete`, `close`, `move`

| Action | Required | Notes |
| ------ | -------- | ----- |
| `create` | `requester_id`, `subject`, `description`, `priority`, `impact`, `status`, `risk`, `change_type` | `planning_fields`*, `assets`, `impacted_services`, `custom_fields`, `agent_id`, `group_id` |
| `update` | `change_id` | any updatable field including `planning_fields`, `impacted_services` |
| `close` | `change_id` | `body` (result explanation) |
| `move` | `change_id` | move between workspaces |

> *`planning_fields` on create are handled transparently via a 2-step process (POST + PUT) to work around a Freshservice API limitation.
> **`impacted_services`** is distinct from `assets`: use `assets` for CI associations (`[{"display_id": N}]`) and `impacted_services` for business service impact declarations (`[{"id": N, "status": 1}]`). Service statuses: 1=Operational, 5=Under maintenance, 10=Degraded, 20=Partial outage, 30=Major outage.

- **`read_change_note`** / **`manage_change_note`** — list/view vs create/update/delete
- **`read_change_task`** / **`manage_change_task`** — list/view vs create/update/delete
- **`read_change_time_entry`** / **`manage_change_time_entry`** — list/view vs create/update/delete
- **`read_change_approval`** / **`manage_change_approval`** — list_groups/list/view vs create_group/update_group/cancel_group/remind/cancel/set_chain_rule

### Problem Management (`problems` scope)

Problem family is fully consolidated — `read_problem` and `manage_problem` cover the parent plus notes, tasks, and time entries.

**`read_problem`** — Actions: `get`, `list`, `filter`, `get_fields`, `list_notes`, `get_note`, `list_tasks`, `get_task`, `list_time_entries`, `get_time_entry`

**`manage_problem`** — Actions: `create`, `update`, `delete`, `close`, `restore`, `add_note`, `update_note`, `delete_note`, `add_task`, `update_task`, `delete_task`, `add_time_entry`, `update_time_entry`, `delete_time_entry`

| Action | Required | Notes |
| ------ | -------- | ----- |
| `create` | `requester_id`, `subject`, `description`, `priority`, `status`, `impact`, `due_by` | `payload.agent_id`, `payload.assets`, `payload.analysis_fields`, etc. |
| `add_note` | `problem_id`, `body` | |
| `add_task` | `problem_id`, `title` | Optional: `description`, `status`, `payload.{due_date, notify_before, group_id}` |
| `add_time_entry` | `problem_id`, `time_spent` | `body` = work note; `payload.te_agent_id`, `payload.billable` etc. |

Priority: 1=Low, 2=Medium, 3=High, 4=Urgent · Status: 1=Open, 2=Change Requested, 3=Closed · Impact: 1=Low, 2=Medium, 3=High

### Release Management (`releases` scope)

Release family is fully consolidated — `read_release` and `manage_release` cover the parent plus notes, tasks, and time entries.

**`read_release`** — Actions: `get`, `list`, `filter`, `get_fields`, `list_notes`, `get_note`, `list_tasks`, `get_task`, `list_time_entries`, `get_time_entry`

**`manage_release`** — Actions: `create`, `update`, `delete`, `restore`, `add_note`, `update_note`, `delete_note`, `add_task`, `update_task`, `delete_task`, `add_time_entry`, `update_time_entry`, `delete_time_entry`

| Action | Required | Notes |
| ------ | -------- | ----- |
| `create` | `subject`, `description`, `priority`, `status`, `release_type`, `planned_start_date`, `planned_end_date` | `payload.planning_fields`* | `payload.{work_start_date, agent_id, assets, custom_fields, ...}` |
| Sub-entity adds/updates | parent id + entity id | Same pattern as problems. |

> *Like changes, `planning_fields` on create uses transparent 2-step handling (POST then PUT).

Priority: 1=Low, 2=Medium, 3=High, 4=Urgent · Status: 1=Open, 2=On hold, 3=In Progress, 4=Incomplete, 5=Completed · Type: 1=Minor, 2=Standard, 3=Major, 4=Emergency

### Asset / CMDB Management (`assets` scope)

**`read_asset`** — Actions: `list`, `get`, `search`, `filter`, `get_types`, `get_type`, `get_type_fields`
**`manage_asset`** — Actions: `create`, `update`, `delete`, `delete_permanently`, `restore`, `move`, `create_type`

**`read_asset_details`** — Actions: `get_components`, `get_requests`, `get_contracts`, `get_installed_software`, `get_assignment_history` (no write counterpart — all sub-resource GETs)

**`read_asset_relationship`** / **`manage_asset_relationship`** — list/list_all/get/get_types/job_status vs create/delete

### Status Page (`status_page` scope)

**`read_status_page`** / **`manage_status_page`** — Maintenance windows, incidents, service components, and subscribers.

All actions auto-discover `status_page_id` if omitted. Maintenance CRUD requires either `change_id` **or** `maintenance_window_id` as the source entity. Incident CRUD requires `ticket_id`.

 > **Publishing maintenance on the Status Page — workflow:**
>
> 1. Check the Change: `manage_change` action=`get` → inspect `maintenance_window`
> 2. **If `maintenance_window` has an `id`** → use `change_id` directly in `create_maintenance`
> 3. **If `maintenance_window` is empty `{}`** → create a MW with `manage_maintenance_window` action=`create` passing `change_id` (auto-associates the MW with the Change), then use the returned `maintenance_window_id` in `create_maintenance`
> 4. Required fields for `create_maintenance`: `title`, `description`, `started_at`, `ended_at`, `impacted_services` (get component IDs via `list_components`)

**`read_maintenance_window`** / **`manage_maintenance_window`** — CRUD for Maintenance Windows. Pass `change_id` on create to auto-associate.

| Action | Required Parameters |
| ------ | ------------------- |
| `list` | — |
| `get` | `maintenance_window_id` |
| `create` | `name`, `start_time`, `end_time` + optional `change_id` (auto-associates) |
| `update` | `maintenance_window_id` |
| `delete` | `maintenance_window_id` |

**`manage_status_page`** / **`read_status_page`** actions:

| Action | Required Parameters |
| ------ | ------------------- |
| **Pages** | |
| `list_pages` | — |
| **Service Components** | |
| `list_components` | — |
| `get_component` | `component_id` |
| **Maintenance** (from Change or MW) | |
| `list_maintenance` | — |
| `create_maintenance` | `change_id` or `maintenance_window_id`, `title`, `description`, `started_at`, `ended_at`, `impacted_services` |
| `get_maintenance` | `change_id` or `maintenance_window_id`, `maintenance_id` |
| `update_maintenance` | `change_id` or `maintenance_window_id`, `maintenance_id` |
| `delete_maintenance` | `change_id` or `maintenance_window_id`, `maintenance_id` |
| **Maintenance Updates** | |
| `list_maintenance_updates` | `change_id` or `maintenance_window_id`, `maintenance_id` |
| `create_maintenance_update` | `change_id` or `maintenance_window_id`, `maintenance_id`, `body` |
| `update_maintenance_update` | `change_id` or `maintenance_window_id`, `maintenance_id`, `update_id` |
| `delete_maintenance_update` | `change_id` or `maintenance_window_id`, `maintenance_id`, `update_id` |
| **Incidents** (from Ticket) | |
| `list_incidents` | — |
| `create_incident` | `ticket_id`, `title` |
| `get_incident` / `update_incident` / `delete_incident` | `ticket_id`, `incident_id` |
| **Incident Updates** | |
| `list_incident_updates` | `ticket_id`, `incident_id` |
| `create_incident_update` | `ticket_id`, `incident_id`, `body` |
| `update_incident_update` | `ticket_id`, `incident_id`, `update_id` |
| `delete_incident_update` | `ticket_id`, `incident_id`, `update_id` |
| **Statuses** | |
| `list_maintenance_statuses` / `list_incident_statuses` | — |
| **Subscribers** | |
| `list_subscribers` | — |
| `get_subscriber` | `subscriber_id` |
| `create_subscriber` | `email` |
| `update_subscriber` | `subscriber_id` |
| `delete_subscriber` | `subscriber_id` |

Key fields: `started_at` (ISO datetime), `ended_at`, `impacted_services` (`[{id, status}]`), `notifications` (`[{trigger, options}]`), `description`.

### Project Management (`projects` scope)

**`read_project`** — Actions: `get`, `list`, `get_fields`, `get_templates`, `get_memberships`, `get_associations`, `get_versions`, `get_sprints`
**`manage_project`** — Actions: `create`, `update`, `delete`, `archive`, `restore`, `add_members`, `create_association`, `delete_association`

| Action | Required Parameters | Optional Parameters |
| ------ | ------------------- | ------------------- |
| `list` | — | `filter` (`completed`, `incomplete`, `archived`, `open`, `in_progress`), `page`, `per_page` |
| `get` | `project_id` | — |
| `create` | `name`, `project_type` (0=Software, 1=Business) | `description`, `key`, `priority_id`, `manager_id`, `start_date`, `end_date`, `visibility`, `sprint_duration`, `project_template_id`, `custom_fields` |
| `update` | `project_id` | any updatable field |
| `delete` | `project_id` | — |
| `archive` / `restore` | `project_id` | — |
| `get_fields` | — | — |
| `get_templates` | — | — |
| `add_members` | `project_id`, `members` (`[{"email": "...", "role": 1}]`) | — |
| `get_memberships` | `project_id` | — |
| `create_association` | `project_id`, `module_name` (`tickets`/`problems`/`changes`/`assets`), `ids` | — |
| `get_associations` | `project_id`, `module_name` | — |
| `delete_association` | `project_id`, `module_name`, `association_id` | — |
| `get_versions` / `get_sprints` | `project_id` | — |

Priority: 1=Low, 2=Medium, 3=High, 4=Urgent · Status: 1=Yet to start, 2=In Progress, 3=Completed · Visibility: 0=Private, 1=Public

**`read_project_task`** — Actions: `get`, `list`, `filter`, `get_task_types`, `get_task_type_fields`, `get_task_statuses`, `get_task_priorities`, `list_notes`, `get_associations`
**`manage_project_task`** — Actions: `create`, `update`, `delete`, `create_note`, `update_note`, `delete_note`, `create_association`, `delete_association`

| Action | Required Parameters | Optional Parameters |
| ------ | ------------------- | ------------------- |
| `list` | `project_id` | `filter`, `page`, `per_page` |
| `get` | `project_id`, `task_id` | — |
| `create` | `project_id`, `title`, `type_id` | `description`, `status_id`, `priority_id`, `assignee_id`, `reporter_id`, `parent_id`, `planned_start_date`, `planned_end_date`, `planned_effort`, `story_points`, `sprint_id`, `version_id`, `custom_fields` |
| `update` | `project_id`, `task_id` | any updatable field |
| `delete` | `project_id`, `task_id` | — |
| `filter` | `project_id`, `query` | `page`, `per_page` |
| `get_task_types` | `project_id` | — |
| `get_task_type_fields` | `project_id`, `type_id` | — |
| `get_task_statuses` / `get_task_priorities` | `project_id` | — |
| `create_note` | `project_id`, `task_id`, `content` | — |
| `list_notes` | `project_id`, `task_id` | — |
| `update_note` | `project_id`, `task_id`, `note_id`, `content` | — |
| `delete_note` | `project_id`, `task_id`, `note_id` | — |
| `create_association` | `project_id`, `task_id`, `module_name`, `ids` | — |
| `get_associations` | `project_id`, `task_id`, `module_name` | — |
| `delete_association` | `project_id`, `task_id`, `module_name`, `association_id` | — |

> Use `get_task_types` to discover available type_ids before creating tasks. The task UPDATE endpoint uses a singular path (`/task/` instead of `/tasks/`) — this is handled automatically.

### Departments & Locations

`departments` scope: **`read_department`** / **`manage_department`** — list/get/filter/get_fields vs create/update/delete

`locations` scope: **`read_location`** / **`manage_location`** — list/get/filter vs create/update/delete

### Agents & Requesters (`agents` / `requesters` scopes)

- **`read_agent`** / **`manage_agent`** — list/get/filter/get_fields vs create/update
- **`read_agent_group`** / **`manage_agent_group`** — list/get vs create/update
- **`read_requester`** / **`manage_requester`** — list/get/filter/get_fields vs create/update/add_to_group
- **`read_requester_group`** / **`manage_requester_group`** — list/get/list_members vs create/update

### Solutions, Products, Procurement, Contracts, Software, Announcements, Custom Objects

- `solutions`: **`read_solution`** / **`manage_solution`** — list/get categories/folders/articles vs create/update/publish
- `products`: **`read_product`** / **`manage_product`** — list/get vs create/update
- `procurement`: **`read_purchase_order`** / **`manage_purchase_order`**, **`read_vendor`** / **`manage_vendor`**
- `contracts`: **`read_contract`** / **`manage_contract`** — list/get/get_types/get_type/get_type_fields vs create/update/delete
- `software`: **`read_software`** / **`manage_software`** — list/get/list_licenses vs create/update
- `announcements`: **`read_announcement`** / **`manage_announcement`** — list/get vs create/update/delete
- `custom_objects`: **`read_custom_object`** / **`manage_custom_object`** — list_objects/get_object/list_records/get_record vs create_record/update_record/delete_record

### Miscellaneous (`misc` scope)

Lower-traffic resources. Several have no Freshservice write API and are read-only:

- **`read_canned_response`**, **`read_workspace`**, **`read_agent_role`**, **`read_business_hour`**, **`read_sla_policy`**, **`read_audit_log`** — read-only (no manage counterpart)
- **`read_alert`** / **`manage_alert`** — list/get vs delete
- **`read_onboarding_request`** / **`manage_onboarding_request`** — list/get/get_tickets/get_fields vs create
- **`read_offboarding_request`** / **`manage_offboarding_request`** — list/get/get_fields vs create

### Query Syntax for Filtering

When using `filter` actions, **the query string is automatically wrapped in double quotes** by the server. Pass the raw query:

```text
action: "filter", query: "status:3 AND priority:1"
```

**Common filter examples:**

- `"status:3"` — Changes awaiting approval
- `"priority:3 AND status:1"` — High priority open problems
- `"planned_start_date:>'2025-07-14'"` — Changes starting after a date

## Getting Started

### Installing via Smithery

```bash
npx -y @smithery/cli install @effytech/freshservice_mcp --client claude
```

### Prerequisites

- A Freshservice account ([freshservice.com](https://www.freshservice.com))
- Freshservice API key
- Python >= 3.10

### Configuration

Generate your Freshservice API key:

1. Navigate to **Profile Settings → API Settings**
2. Copy your API key

### Usage with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
"mcpServers": {
  "freshservice-mcp": {
    "command": "uvx",
    "args": ["freshservice-mcp"],
    "env": {
      "FRESHSERVICE_APIKEY": "<YOUR_API_KEY>",
      "FRESHSERVICE_DOMAIN": "yourcompany.freshservice.com"
    }
  }
}
```

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

Or with uvx:

```bash
uvx freshservice-mcp --env FRESHSERVICE_APIKEY=<key> --env FRESHSERVICE_DOMAIN=<domain>
```

## Troubleshooting

- Verify your Freshservice API key and domain are correct
- Ensure proper network connectivity to Freshservice servers
- Check API rate limits and quotas
- If tools appear "disabled" in VS Code Copilot, you may have exceeded the 128-tool limit across all MCP servers — use `FRESHSERVICE_SCOPES` to load fewer scopes
- Check server logs: the server logs which scopes and how many tools were loaded at startup

## License

This MCP server is licensed under the MIT License. See the LICENSE file in the project repository for full details.

## Additional Resources

- [Freshservice API Documentation](https://api.freshservice.com/)
- [Claude Desktop Integration Guide](https://docs.anthropic.com/claude/docs/claude-desktop)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)

---

<p align="center">Built with ❤️ by effy</p>
