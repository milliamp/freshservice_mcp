"""Freshservice MCP — Project Management tools (NewGen).

Exposes 2 tools:
  • manage_project      — CRUD + list/archive/restore + fields/templates/
                          members/memberships/associations/versions/sprints
  • manage_project_task — CRUD + list/filter + task-types/statuses/priorities/
                          notes/associations
"""
from typing import Any, Dict, List, Optional, Union

import httpx

from ..http_client import api_delete, api_get, api_post, api_put, handle_error

# Base path for NewGen project management
_PM = "pm/projects"


def register_project_tools(mcp) -> None:  # noqa: C901
    """Register project management tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  manage_project                                                     #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_project(
        action: str,
        project_id: Optional[int] = None,
        # core fields (create / update)
        name: Optional[str] = None,
        description: Optional[str] = None,
        key: Optional[str] = None,
        project_type: Optional[int] = None,
        status_id: Optional[int] = None,
        priority_id: Optional[int] = None,
        manager_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        visibility: Optional[int] = None,
        sprint_duration: Optional[int] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        project_template_id: Optional[int] = None,
        # members (add_members)
        members: Optional[List[Dict[str, Any]]] = None,
        # associations (create_association / view_associations / delete_association)
        module_name: Optional[str] = None,
        ids: Optional[List[int]] = None,
        association_id: Optional[int] = None,
        # list / filter
        filter: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice Projects (NewGen).

        Projects let you plan, prioritize, manage, and track work within
        the service desk. You can associate tickets, changes, problems,
        and assets to projects.

        Args:
            action: One of 'create', 'update', 'get', 'list', 'delete',
                    'archive', 'restore', 'get_fields', 'get_templates',
                    'add_members', 'get_memberships',
                    'create_association', 'get_associations', 'delete_association',
                    'get_versions', 'get_sprints'.
            project_id: Project ID (required for most actions except create,
                list, get_fields, get_templates).
            name: Project name (create — MANDATORY, max 255 chars).
            description: Project description (HTML or plain text).
            key: Project key — starts with letter, letters+numbers, max 10 chars.
                Auto-generated from name if omitted on create.
            project_type: 0=Software, 1=Business (create — MANDATORY).
            status_id: 1=Yet to start, 2=In Progress, 3=Completed.
            priority_id: 1=Low, 2=Medium, 3=High, 4=Urgent.
            manager_id: User ID of the project manager.
            start_date: Start date (yyyy-mm-dd).
            end_date: End date (yyyy-mm-dd).
            visibility: 0=Private, 1=Public (default 1).
            sprint_duration: Sprint duration in days (default 14).
            custom_fields: Custom fields dict.
            project_template_id: Template ID (create only).
            members: List of members to add (add_members).
                Format: [{"email": "user@example.com", "role": 1}]
                role: 1 or 2 (project admin vs member).
            module_name: Association module — 'tickets', 'problems',
                'changes', or 'assets' (create/get/delete_association).
            ids: List of IDs to associate (create_association).
            association_id: Entity ID to dissociate (delete_association).
            filter: Filter for list — 'completed', 'incomplete', 'archived',
                'open', 'in_progress'. Default shows open + completed.
            page/per_page: Pagination (list, max 100 per page).
        """
        action = action.lower().strip()

        # ---------- list ----------
        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            if filter:
                params["filter"] = filter
            try:
                resp = await api_get(_PM, params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list projects")

        # ---------- get ----------
        if action == "get":
            if not project_id:
                return {"error": "project_id required for get"}
            try:
                resp = await api_get(f"{_PM}/{project_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get project")

        # ---------- create ----------
        if action == "create":
            if not name:
                return {"error": "name is required for create"}
            if project_type is None:
                return {"error": "project_type is required for create (0=Software, 1=Business)"}
            data: Dict[str, Any] = {
                "name": name,
                "project_type": project_type,
            }
            for k, v in [("description", description), ("key", key),
                         ("priority_id", priority_id), ("manager_id", manager_id),
                         ("start_date", start_date), ("end_date", end_date),
                         ("visibility", visibility), ("sprint_duration", sprint_duration),
                         ("project_template_id", project_template_id)]:
                if v is not None:
                    data[k] = v
            if custom_fields:
                data["custom_fields"] = custom_fields
            try:
                resp = await api_post(_PM, json=data)
                resp.raise_for_status()
                return {"success": True, "project": resp.json()}
            except Exception as e:
                return handle_error(e, "create project")

        # ---------- update ----------
        if action == "update":
            if not project_id:
                return {"error": "project_id required for update"}
            data = {}
            for k, v in [("name", name), ("description", description), ("key", key),
                         ("status_id", status_id), ("priority_id", priority_id),
                         ("manager_id", manager_id), ("start_date", start_date),
                         ("end_date", end_date), ("visibility", visibility),
                         ("sprint_duration", sprint_duration)]:
                if v is not None:
                    data[k] = v
            if custom_fields:
                data["custom_fields"] = custom_fields
            if not data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"{_PM}/{project_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "project": resp.json()}
            except Exception as e:
                return handle_error(e, "update project")

        # ---------- delete ----------
        if action == "delete":
            if not project_id:
                return {"error": "project_id required for delete"}
            try:
                resp = await api_delete(f"{_PM}/{project_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Project deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete project")

        # ---------- archive ----------
        if action == "archive":
            if not project_id:
                return {"error": "project_id required for archive"}
            try:
                resp = await api_post(f"{_PM}/{project_id}/archive", json={})
                if resp.status_code == 200:
                    return {"success": True, "message": "Project archived"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "archive project")

        # ---------- restore ----------
        if action == "restore":
            if not project_id:
                return {"error": "project_id required for restore"}
            try:
                resp = await api_post(f"{_PM}/{project_id}/restore", json={})
                if resp.status_code == 200:
                    return {"success": True, "message": "Project restored"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "restore project")

        # ---------- get_fields ----------
        if action == "get_fields":
            try:
                resp = await api_get("pm/project-fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get project fields")

        # ---------- get_templates ----------
        if action == "get_templates":
            try:
                resp = await api_get("pm/project_templates")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get project templates")

        # ---------- add_members ----------
        if action == "add_members":
            if not project_id:
                return {"error": "project_id required for add_members"}
            if not members:
                return {
                    "error": "members required — list of {email, role?} dicts. "
                    "Example: [{\"email\": \"user@example.com\", \"role\": 1}]"
                }
            try:
                resp = await api_post(
                    f"{_PM}/{project_id}/members",
                    json={"members": members},
                )
                resp.raise_for_status()
                return {"success": True, "result": resp.json()}
            except Exception as e:
                return handle_error(e, "add members to project")

        # ---------- get_memberships ----------
        if action == "get_memberships":
            if not project_id:
                return {"error": "project_id required for get_memberships"}
            try:
                resp = await api_get(f"{_PM}/{project_id}/memberships")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get project memberships")

        # ---------- create_association ----------
        if action == "create_association":
            if not project_id:
                return {"error": "project_id required for create_association"}
            if not module_name or module_name not in ("tickets", "problems", "changes", "assets"):
                return {
                    "error": "module_name required — one of: tickets, problems, changes, assets"
                }
            if not ids:
                return {"error": "ids required — list of entity IDs to associate"}
            try:
                resp = await api_post(
                    f"{_PM}/{project_id}/{module_name}",
                    json={"ids": ids},
                )
                resp.raise_for_status()
                return {"success": True, "result": resp.json()}
            except Exception as e:
                return handle_error(e, f"create {module_name} association")

        # ---------- get_associations ----------
        if action == "get_associations":
            if not project_id:
                return {"error": "project_id required for get_associations"}
            if not module_name or module_name not in ("tickets", "problems", "changes", "assets"):
                return {
                    "error": "module_name required — one of: tickets, problems, changes, assets"
                }
            try:
                resp = await api_get(f"{_PM}/{project_id}/{module_name}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, f"get {module_name} associations")

        # ---------- delete_association ----------
        if action == "delete_association":
            if not project_id:
                return {"error": "project_id required for delete_association"}
            if not module_name or module_name not in ("tickets", "problems", "changes", "assets"):
                return {
                    "error": "module_name required — one of: tickets, problems, changes, assets"
                }
            if not association_id:
                return {"error": "association_id required — the ID of the entity to dissociate"}
            try:
                resp = await api_delete(f"{_PM}/{project_id}/{module_name}/{association_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": f"{module_name} association deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, f"delete {module_name} association")

        # ---------- get_versions ----------
        if action == "get_versions":
            if not project_id:
                return {"error": "project_id required for get_versions"}
            try:
                resp = await api_get(f"{_PM}/{project_id}/versions")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get project versions")

        # ---------- get_sprints ----------
        if action == "get_sprints":
            if not project_id:
                return {"error": "project_id required for get_sprints"}
            try:
                resp = await api_get(f"{_PM}/{project_id}/sprints")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get project sprints")

        return {
            "error": f"Unknown action '{action}'. Valid: create, update, get, list, "
            "delete, archive, restore, get_fields, get_templates, add_members, "
            "get_memberships, create_association, get_associations, "
            "delete_association, get_versions, get_sprints"
        }

    # ------------------------------------------------------------------ #
    #  manage_project_task                                                #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_project_task(
        action: str,
        project_id: Optional[int] = None,
        task_id: Optional[int] = None,
        # core fields (create / update)
        title: Optional[str] = None,
        description: Optional[str] = None,
        type_id: Optional[int] = None,
        status_id: Optional[int] = None,
        priority_id: Optional[int] = None,
        assignee_id: Optional[int] = None,
        reporter_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        planned_start_date: Optional[str] = None,
        planned_end_date: Optional[str] = None,
        planned_effort: Optional[str] = None,
        story_points: Optional[int] = None,
        sprint_id: Optional[int] = None,
        version_id: Optional[int] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        # notes (create_note / update_note)
        note_id: Optional[int] = None,
        content: Optional[str] = None,
        # associations (create_association / get_associations / delete_association)
        module_name: Optional[str] = None,
        ids: Optional[List[int]] = None,
        association_id: Optional[int] = None,
        # filter
        query: Optional[str] = None,
        filter: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice Project Tasks (NewGen).

        Tasks organize project work — epics, user stories, subtasks, etc.
        Each task has a type, status, priority, assignee, and can be linked
        to sprints, versions, and parent tasks.

        Args:
            action: One of 'create', 'update', 'get', 'list', 'filter',
                    'delete', 'get_task_types', 'get_task_type_fields',
                    'get_task_statuses', 'get_task_priorities',
                    'create_note', 'list_notes', 'update_note', 'delete_note',
                    'create_association', 'get_associations', 'delete_association'.
            project_id: Project ID (required for all actions).
            task_id: Task ID (required for get/update/delete and note/association ops).
            title: Task title (create — MANDATORY).
            description: Task description (HTML or plain text).
            type_id: Task type ID — obtain via get_task_types (create — MANDATORY).
            status_id: Task status ID — obtain via get_task_statuses.
            priority_id: Task priority ID — obtain via get_task_priorities.
            assignee_id: User ID to assign the task to.
            reporter_id: User ID of the reporter (defaults to creator).
            parent_id: Parent task/epic ID for subtasks.
            planned_start_date: ISO datetime (yyyy-mm-ddThh:mm:ssZ).
            planned_end_date: ISO datetime (yyyy-mm-ddThh:mm:ssZ).
            planned_effort: Effort string, e.g. '1w 2d 3h 4m'.
            story_points: Story points for the task.
            sprint_id: Sprint ID — obtain via manage_project get_sprints.
            version_id: Version ID — obtain via manage_project get_versions.
            custom_fields: Custom fields dict.
            note_id: Note ID (update_note / delete_note).
            content: Note content — HTML (create_note / update_note).
            module_name: Association module — 'tickets', 'problems',
                'changes', or 'assets' (association operations).
            ids: Entity IDs to associate (create_association).
            association_id: Entity ID to dissociate (delete_association).
            query: Filter query for 'filter' action. Format:
                "priority_id:3 AND created_at:>'2025-01-01'"
            filter: Predefined filter for 'list' — 'all', etc.
            page/per_page: Pagination.
        """
        action = action.lower().strip()

        if not project_id:
            return {"error": "project_id is required for all project task actions"}

        base = f"{_PM}/{project_id}"

        # ---------- list ----------
        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            if filter:
                params["filter"] = filter
            try:
                resp = await api_get(f"{base}/tasks", params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list project tasks")

        # ---------- filter ----------
        if action == "filter":
            if not query:
                return {"error": "query required for filter. Example: \"priority_id:3 AND status_id:1\""}
            params = {"query": f'"{query}"', "page": page, "per_page": per_page}
            try:
                resp = await api_get(f"{base}/tasks/filter", params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "filter project tasks")

        # ---------- get ----------
        if action == "get":
            if not task_id:
                return {"error": "task_id required for get"}
            try:
                resp = await api_get(f"{base}/tasks/{task_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get project task")

        # ---------- create ----------
        if action == "create":
            if not title:
                return {"error": "title is required for create"}
            if type_id is None:
                return {
                    "error": "type_id is required for create. "
                    "Use action='get_task_types' to discover available types."
                }
            data: Dict[str, Any] = {"title": title, "type_id": type_id}
            for k, v in [("description", description), ("status_id", status_id),
                         ("priority_id", priority_id), ("assignee_id", assignee_id),
                         ("reporter_id", reporter_id), ("parent_id", parent_id),
                         ("planned_start_date", planned_start_date),
                         ("planned_end_date", planned_end_date),
                         ("planned_effort", planned_effort),
                         ("story_points", story_points),
                         ("sprint_id", sprint_id), ("version_id", version_id)]:
                if v is not None:
                    data[k] = v
            if custom_fields:
                data["custom_fields"] = custom_fields
            try:
                resp = await api_post(f"{base}/tasks", json=data)
                resp.raise_for_status()
                return {"success": True, "task": resp.json()}
            except Exception as e:
                return handle_error(e, "create project task")

        # ---------- update ----------
        if action == "update":
            if not task_id:
                return {"error": "task_id required for update"}
            data = {}
            for k, v in [("title", title), ("description", description),
                         ("type_id", type_id), ("status_id", status_id),
                         ("priority_id", priority_id), ("assignee_id", assignee_id),
                         ("reporter_id", reporter_id), ("parent_id", parent_id),
                         ("planned_start_date", planned_start_date),
                         ("planned_end_date", planned_end_date),
                         ("planned_effort", planned_effort),
                         ("story_points", story_points),
                         ("sprint_id", sprint_id), ("version_id", version_id)]:
                if v is not None:
                    data[k] = v
            if custom_fields:
                data["custom_fields"] = custom_fields
            if not data:
                return {"error": "No fields provided for update"}
            try:
                # NOTE: Freshservice uses singular "task" for update URL
                resp = await api_put(f"{base}/task/{task_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "task": resp.json()}
            except Exception as e:
                return handle_error(e, "update project task")

        # ---------- delete ----------
        if action == "delete":
            if not task_id:
                return {"error": "task_id required for delete"}
            try:
                resp = await api_delete(f"{base}/tasks/{task_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Project task deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete project task")

        # ---------- get_task_types ----------
        if action == "get_task_types":
            try:
                resp = await api_get(f"{base}/task-types")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get task types")

        # ---------- get_task_type_fields ----------
        if action == "get_task_type_fields":
            if not type_id:
                return {
                    "error": "type_id required for get_task_type_fields. "
                    "Use action='get_task_types' first."
                }
            try:
                resp = await api_get(f"{base}/task-types/{type_id}/fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get task type fields")

        # ---------- get_task_statuses ----------
        if action == "get_task_statuses":
            try:
                resp = await api_get(f"{base}/task-statuses")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get task statuses")

        # ---------- get_task_priorities ----------
        if action == "get_task_priorities":
            try:
                resp = await api_get(f"{base}/task-priorities")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get task priorities")

        # ---------- create_note ----------
        if action == "create_note":
            if not task_id:
                return {"error": "task_id required for create_note"}
            if not content:
                return {"error": "content required for create_note (HTML supported)"}
            try:
                resp = await api_post(
                    f"{base}/tasks/{task_id}/notes",
                    json={"content": content},
                )
                resp.raise_for_status()
                return {"success": True, "notes": resp.json()}
            except Exception as e:
                return handle_error(e, "create task note")

        # ---------- list_notes ----------
        if action == "list_notes":
            if not task_id:
                return {"error": "task_id required for list_notes"}
            try:
                resp = await api_get(f"{base}/tasks/{task_id}/notes")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list task notes")

        # ---------- update_note ----------
        if action == "update_note":
            if not task_id or not note_id:
                return {"error": "task_id and note_id required for update_note"}
            if not content:
                return {"error": "content required for update_note"}
            try:
                resp = await api_put(
                    f"{base}/tasks/{task_id}/notes/{note_id}",
                    json={"content": content},
                )
                resp.raise_for_status()
                return {"success": True, "note": resp.json()}
            except Exception as e:
                return handle_error(e, "update task note")

        # ---------- delete_note ----------
        if action == "delete_note":
            if not task_id or not note_id:
                return {"error": "task_id and note_id required for delete_note"}
            try:
                resp = await api_delete(f"{base}/tasks/{task_id}/notes/{note_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Task note deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete task note")

        # ---------- create_association ----------
        if action == "create_association":
            if not task_id:
                return {"error": "task_id required for create_association"}
            if not module_name or module_name not in ("tickets", "problems", "changes", "assets"):
                return {
                    "error": "module_name required — one of: tickets, problems, changes, assets"
                }
            if not ids:
                return {"error": "ids required — list of entity IDs to associate"}
            try:
                resp = await api_post(
                    f"{base}/tasks/{task_id}/{module_name}",
                    json={"ids": ids},
                )
                resp.raise_for_status()
                return {"success": True, "result": resp.json()}
            except Exception as e:
                return handle_error(e, f"create task {module_name} association")

        # ---------- get_associations ----------
        if action == "get_associations":
            if not task_id:
                return {"error": "task_id required for get_associations"}
            if not module_name or module_name not in ("tickets", "problems", "changes", "assets"):
                return {
                    "error": "module_name required — one of: tickets, problems, changes, assets"
                }
            try:
                resp = await api_get(f"{base}/tasks/{task_id}/{module_name}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, f"get task {module_name} associations")

        # ---------- delete_association ----------
        if action == "delete_association":
            if not task_id:
                return {"error": "task_id required for delete_association"}
            if not module_name or module_name not in ("tickets", "problems", "changes", "assets"):
                return {
                    "error": "module_name required — one of: tickets, problems, changes, assets"
                }
            if not association_id:
                return {"error": "association_id required — the entity ID to dissociate"}
            try:
                resp = await api_delete(
                    f"{base}/tasks/{task_id}/{module_name}/{association_id}"
                )
                if resp.status_code == 204:
                    return {"success": True, "message": f"Task {module_name} association deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, f"delete task {module_name} association")

        return {
            "error": f"Unknown action '{action}'. Valid: create, update, get, list, "
            "filter, delete, get_task_types, get_task_type_fields, "
            "get_task_statuses, get_task_priorities, create_note, list_notes, "
            "update_note, delete_note, create_association, get_associations, "
            "delete_association"
        }
