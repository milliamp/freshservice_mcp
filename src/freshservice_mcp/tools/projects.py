"""Freshservice MCP — Project Management tools (NewGen).

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  • read_project / manage_project           — list/get/get_fields/get_templates/
                                               get_memberships/get_associations/
                                               get_versions/get_sprints vs CRUD +
                                               archive/restore/add_members/
                                               create_association/delete_association
  • read_project_task / manage_project_task — list/filter/get/get_task_types/
                                               get_task_type_fields/get_task_statuses/
                                               get_task_priorities/list_notes/
                                               get_associations vs CRUD + note
                                               CRUD + association CRUD
"""
from typing import Any, Dict, List, Optional, Union

import httpx

from ..http_client import (
    api_delete, api_get, api_post, api_put,
    get_auth_headers, handle_error,
)
from ._split import normalize_action, reject_unless_in

# Base path for NewGen project management
_PM = "pm/projects"

# NewGen PM endpoints require Content-Type on ALL verbs (incl. GET/DELETE).

def _pm_headers() -> Dict[str, str]:
    """Return headers with Content-Type for PM endpoints."""
    return get_auth_headers()


def register_project_tools(mcp) -> None:  # noqa: C901
    """Register project management tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  project — read/manage split                                        #
    # ------------------------------------------------------------------ #
    _READ_PROJECT = {
        "list", "get", "get_fields", "get_templates", "get_memberships",
        "get_associations", "get_versions", "get_sprints",
    }
    _WRITE_PROJECT = {
        "create", "update", "delete", "archive", "restore", "add_members",
        "create_association", "delete_association",
    }

    async def _project_handler(
        action: str,
        project_id: Optional[int],
        # core fields (create / update)
        name: Optional[str],
        description: Optional[str],
        key: Optional[str],
        project_type: Optional[int],
        status_id: Optional[int],
        priority_id: Optional[int],
        manager_id: Optional[int],
        start_date: Optional[str],
        end_date: Optional[str],
        visibility: Optional[int],
        sprint_duration: Optional[int],
        custom_fields: Optional[Dict[str, Any]],
        project_template_id: Optional[int],
        # members (add_members)
        members: Optional[List[Dict[str, Any]]],
        # associations
        module_name: Optional[str],
        ids: Optional[List[int]],
        association_id: Optional[int],
        # list / filter
        filter: Optional[str],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        # ---------- list ----------
        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            if filter:
                params["filter"] = filter
            try:
                resp = await api_get(_PM, params=params, headers=_pm_headers())
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list projects")

        # ---------- get ----------
        if action == "get":
            if not project_id:
                return {"error": "project_id required for get"}
            try:
                resp = await api_get(f"{_PM}/{project_id}", headers=_pm_headers())
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
                resp = await api_delete(f"{_PM}/{project_id}", headers=_pm_headers())
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
                resp = await api_get("pm/project-fields", headers=_pm_headers())
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get project fields")

        # ---------- get_templates ----------
        if action == "get_templates":
            try:
                resp = await api_get("pm/project_templates", headers=_pm_headers())
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
                resp = await api_get(f"{_PM}/{project_id}/memberships", headers=_pm_headers())
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
                resp = await api_get(f"{_PM}/{project_id}/{module_name}", headers=_pm_headers())
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
                resp = await api_delete(f"{_PM}/{project_id}/{module_name}/{association_id}", headers=_pm_headers())
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
                resp = await api_get(f"{_PM}/{project_id}/versions", headers=_pm_headers())
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get project versions")

        # ---------- get_sprints ----------
        if action == "get_sprints":
            if not project_id:
                return {"error": "project_id required for get_sprints"}
            try:
                resp = await api_get(f"{_PM}/{project_id}/sprints", headers=_pm_headers())
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get project sprints")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_project(
        action: str,
        project_id: Optional[int] = None,
        module_name: Optional[str] = None,
        filter: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice Projects (NewGen).

        Actions: list, get, get_fields, get_templates, get_memberships,
          get_associations, get_versions, get_sprints

        Required per action:
          get / get_memberships / get_versions / get_sprints: project_id
          get_associations: project_id, module_name (tickets|problems|changes|assets)

        Optional: filter (list: completed|incomplete|archived|open|in_progress),
        page, per_page.
        """
        action = normalize_action(action, _READ_PROJECT)
        err = reject_unless_in(action, _READ_PROJECT, "read_project", "manage_project")
        if err:
            return err
        return await _project_handler(
            action, project_id,
            name=None, description=None, key=None, project_type=None,
            status_id=None, priority_id=None, manager_id=None,
            start_date=None, end_date=None, visibility=None,
            sprint_duration=None, custom_fields=None, project_template_id=None,
            members=None, module_name=module_name, ids=None, association_id=None,
            filter=filter, page=page, per_page=per_page,
        )

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
        # associations
        module_name: Optional[str] = None,
        ids: Optional[List[int]] = None,
        association_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice Projects (NewGen).

        Actions: create, update, delete, archive, restore, add_members,
          create_association, delete_association

        Required per action:
          create: name, project_type (0=Software, 1=Business)
          update / delete / archive / restore: project_id
          add_members: project_id, members ([{email, role: 1|2}])
          create_association: project_id, module_name, ids
          delete_association: project_id, module_name, association_id

        module_name (associations): tickets|problems|changes|assets

        Optional fields:
          status_id: 1=YetToStart, 2=InProgress, 3=Completed
          priority_id: 1=Low, 2=Medium, 3=High, 4=Urgent
          visibility: 0=Private, 1=Public; key (<=10 chars), description,
          manager_id, start_date, end_date, sprint_duration, custom_fields,
          project_template_id (create only).
        """
        action = normalize_action(action, _WRITE_PROJECT)
        err = reject_unless_in(action, _WRITE_PROJECT, "manage_project", "read_project")
        if err:
            return err
        return await _project_handler(
            action, project_id,
            name=name, description=description, key=key, project_type=project_type,
            status_id=status_id, priority_id=priority_id, manager_id=manager_id,
            start_date=start_date, end_date=end_date, visibility=visibility,
            sprint_duration=sprint_duration, custom_fields=custom_fields,
            project_template_id=project_template_id,
            members=members, module_name=module_name, ids=ids,
            association_id=association_id,
            filter=None, page=1, per_page=30,
        )

    # ------------------------------------------------------------------ #
    #  project_task — read/manage split                                   #
    # ------------------------------------------------------------------ #
    _READ_PROJECT_TASK = {
        "list", "filter", "get", "get_task_types", "get_task_type_fields",
        "get_task_statuses", "get_task_priorities", "list_notes",
        "get_associations",
    }
    _WRITE_PROJECT_TASK = {
        "create", "update", "delete", "create_note", "update_note",
        "delete_note", "create_association", "delete_association",
    }

    async def _project_task_handler(
        action: str,
        project_id: Optional[int],
        task_id: Optional[int],
        title: Optional[str],
        description: Optional[str],
        type_id: Optional[int],
        status_id: Optional[int],
        priority_id: Optional[int],
        assignee_id: Optional[int],
        reporter_id: Optional[int],
        parent_id: Optional[int],
        planned_start_date: Optional[str],
        planned_end_date: Optional[str],
        planned_effort: Optional[str],
        story_points: Optional[int],
        sprint_id: Optional[int],
        version_id: Optional[int],
        custom_fields: Optional[Dict[str, Any]],
        note_id: Optional[int],
        content: Optional[str],
        module_name: Optional[str],
        ids: Optional[List[int]],
        association_id: Optional[int],
        query: Optional[str],
        filter: Optional[str],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        if not project_id:
            return {"error": "project_id is required for all project task actions"}

        base = f"{_PM}/{project_id}"

        # ---------- list ----------
        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            if filter:
                params["filter"] = filter
            try:
                resp = await api_get(f"{base}/tasks", params=params, headers=_pm_headers())
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
                resp = await api_get(f"{base}/tasks/filter", params=params, headers=_pm_headers())
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "filter project tasks")

        # ---------- get ----------
        if action == "get":
            if not task_id:
                return {"error": "task_id required for get"}
            try:
                resp = await api_get(f"{base}/tasks/{task_id}", headers=_pm_headers())
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
                resp = await api_delete(f"{base}/tasks/{task_id}", headers=_pm_headers())
                if resp.status_code == 204:
                    return {"success": True, "message": "Project task deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete project task")

        # ---------- get_task_types ----------
        if action == "get_task_types":
            try:
                resp = await api_get(f"{base}/task-types", headers=_pm_headers())
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
                resp = await api_get(f"{base}/task-types/{type_id}/fields", headers=_pm_headers())
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get task type fields")

        # ---------- get_task_statuses ----------
        if action == "get_task_statuses":
            try:
                resp = await api_get(f"{base}/task-statuses", headers=_pm_headers())
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get task statuses")

        # ---------- get_task_priorities ----------
        if action == "get_task_priorities":
            try:
                resp = await api_get(f"{base}/task-priorities", headers=_pm_headers())
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
                resp = await api_get(f"{base}/tasks/{task_id}/notes", headers=_pm_headers())
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
                resp = await api_delete(f"{base}/tasks/{task_id}/notes/{note_id}", headers=_pm_headers())
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
                resp = await api_get(f"{base}/tasks/{task_id}/{module_name}", headers=_pm_headers())
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
                    f"{base}/tasks/{task_id}/{module_name}/{association_id}",
                    headers=_pm_headers(),
                )
                if resp.status_code == 204:
                    return {"success": True, "message": f"Task {module_name} association deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, f"delete task {module_name} association")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_project_task(
        action: str,
        project_id: Optional[int] = None,
        task_id: Optional[int] = None,
        type_id: Optional[int] = None,
        module_name: Optional[str] = None,
        query: Optional[str] = None,
        filter: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice Project Tasks (NewGen).

        Actions: list, filter, get, get_task_types, get_task_type_fields,
          get_task_statuses, get_task_priorities, list_notes, get_associations

        Required per action:
          all actions: project_id
          get / list_notes: task_id
          filter: query (e.g. "priority_id:3 AND status_id:1")
          get_task_type_fields: type_id
          get_associations: task_id, module_name (tickets|problems|changes|assets)

        Optional: filter (list), page, per_page.
        """
        action = normalize_action(action, _READ_PROJECT_TASK)
        err = reject_unless_in(action, _READ_PROJECT_TASK, "read_project_task", "manage_project_task")
        if err:
            return err
        return await _project_task_handler(
            action, project_id, task_id,
            title=None, description=None, type_id=type_id,
            status_id=None, priority_id=None, assignee_id=None,
            reporter_id=None, parent_id=None,
            planned_start_date=None, planned_end_date=None,
            planned_effort=None, story_points=None,
            sprint_id=None, version_id=None, custom_fields=None,
            note_id=None, content=None,
            module_name=module_name, ids=None, association_id=None,
            query=query, filter=filter, page=page, per_page=per_page,
        )

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
        # associations
        module_name: Optional[str] = None,
        ids: Optional[List[int]] = None,
        association_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice Project Tasks (NewGen).

        Actions: create, update, delete, create_note, update_note,
          delete_note, create_association, delete_association

        Required per action:
          all actions: project_id
          create: title, type_id (use get_task_types to discover)
          update / delete: task_id
          create_note: task_id, content
          update_note: task_id, note_id, content
          delete_note: task_id, note_id
          create_association: task_id, module_name, ids
          delete_association: task_id, module_name, association_id

        module_name (associations): tickets|problems|changes|assets

        Optional fields: description, status_id, priority_id, assignee_id,
        reporter_id, parent_id, planned_start_date, planned_end_date,
        planned_effort (e.g. '1w 2d 3h 4m'), story_points, sprint_id,
        version_id, custom_fields.
        """
        action = normalize_action(action, _WRITE_PROJECT_TASK)
        err = reject_unless_in(action, _WRITE_PROJECT_TASK, "manage_project_task", "read_project_task")
        if err:
            return err
        return await _project_task_handler(
            action, project_id, task_id,
            title=title, description=description, type_id=type_id,
            status_id=status_id, priority_id=priority_id,
            assignee_id=assignee_id, reporter_id=reporter_id,
            parent_id=parent_id, planned_start_date=planned_start_date,
            planned_end_date=planned_end_date, planned_effort=planned_effort,
            story_points=story_points, sprint_id=sprint_id,
            version_id=version_id, custom_fields=custom_fields,
            note_id=note_id, content=content,
            module_name=module_name, ids=ids, association_id=association_id,
            query=None, filter=None, page=1, per_page=30,
        )
