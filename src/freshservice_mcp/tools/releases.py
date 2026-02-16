"""Freshservice MCP — Release Management tools.

Exposes 4 tools:
  • manage_release           — CRUD + list/filter/restore releases
  • manage_release_note      — CRUD notes on a release
  • manage_release_task      — CRUD tasks on a release
  • manage_release_time_entry — CRUD time entries on a release
"""
from typing import Any, Dict, List, Optional

from ..http_client import api_delete, api_get, api_post, api_put, handle_error


def register_release_tools(mcp) -> None:
    """Register release management tools on *mcp*."""

    @mcp.tool()
    async def manage_release(
        action: str,
        release_id: Optional[int] = None,
        # core fields
        subject: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        status: Optional[int] = None,
        release_type: Optional[int] = None,
        # scheduling
        planned_start_date: Optional[str] = None,
        planned_end_date: Optional[str] = None,
        work_start_date: Optional[str] = None,
        work_end_date: Optional[str] = None,
        # assignment
        agent_id: Optional[int] = None,
        group_id: Optional[int] = None,
        department_id: Optional[int] = None,
        # categorization
        category: Optional[str] = None,
        sub_category: Optional[str] = None,
        item_category: Optional[str] = None,
        # associations
        assets: Optional[List[Dict[str, Any]]] = None,
        planning_fields: Optional[Dict[str, Any]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        # filter / pagination
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice releases.

        NOTE: Like changes, planning_fields cannot be set on create.
        If you supply them, they will be applied via a follow-up PUT
        automatically.

        Args:
            action: One of 'list', 'get', 'create', 'update', 'delete',
                    'filter', 'restore', 'get_fields'.
            release_id: Release ID (required for get/update/delete/restore).
            subject: Release subject (required for create).
            description: HTML description (required for create).
            priority: 1=Low, 2=Medium, 3=High, 4=Urgent (required for create).
            status: 1=Open, 2=On hold, 3=In Progress, 4=Incomplete, 5=Completed
                    (required for create).
            release_type: 1=Minor, 2=Standard, 3=Major, 4=Emergency
                          (required for create).
            planned_start_date: ISO datetime for planned start.
            planned_end_date: ISO datetime for planned end.
            work_start_date: ISO datetime for actual work start.
            work_end_date: ISO datetime for actual work end.
            agent_id: Assigned agent ID.
            group_id: Assigned group ID.
            department_id: Department ID.
            category/sub_category/item_category: Categorization.
            assets: Associated assets [{"display_id": N}].
            planning_fields: Planning fields dict (build_plan, test_plan).
            custom_fields: Custom fields dict.
            query: Filter query for 'filter' action.
            page/per_page: Pagination.
        """
        action = action.lower().strip()

        if action == "list":
            try:
                resp = await api_get("releases", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list releases")

        if action == "get":
            if not release_id:
                return {"error": "release_id required for get"}
            try:
                resp = await api_get(f"releases/{release_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get release")

        if action == "create":
            if not all([subject, description, priority, status, release_type,
                        planned_start_date, planned_end_date]):
                return {
                    "error": "Required for create: subject, description, priority, status, "
                    "release_type, planned_start_date, planned_end_date"
                }
            data: Dict[str, Any] = {
                "subject": subject,
                "description": description,
                "priority": priority,
                "status": status,
                "release_type": release_type,
                "planned_start_date": planned_start_date,
                "planned_end_date": planned_end_date,
            }
            for k, v in [("agent_id", agent_id), ("group_id", group_id),
                         ("department_id", department_id), ("category", category),
                         ("sub_category", sub_category), ("item_category", item_category),
                         ("assets", assets), ("custom_fields", custom_fields),
                         ("work_start_date", work_start_date),
                         ("work_end_date", work_end_date)]:
                if v is not None:
                    data[k] = v

            # planning_fields cannot be set on create — same pattern as changes
            deferred_planning = planning_fields

            try:
                resp = await api_post("releases", json=data)
                resp.raise_for_status()
                result = resp.json()
            except Exception as e:
                return handle_error(e, "create release")

            # Step 2: apply planning_fields via PUT if provided
            if deferred_planning:
                rel = result.get("release", {})
                new_id = rel.get("id")
                if new_id:
                    try:
                        resp2 = await api_put(
                            f"releases/{new_id}",
                            json={"planning_fields": deferred_planning},
                        )
                        resp2.raise_for_status()
                        result = resp2.json()
                    except Exception:
                        result["_warning"] = (
                            "Release created but planning_fields could not be set. "
                            "Use manage_release(action='update') to retry."
                        )

            return {"success": True, "release": result}

        if action == "update":
            if not release_id:
                return {"error": "release_id required for update"}
            data = {}
            for k, v in [("subject", subject), ("description", description),
                         ("priority", priority), ("status", status),
                         ("release_type", release_type),
                         ("planned_start_date", planned_start_date),
                         ("planned_end_date", planned_end_date),
                         ("work_start_date", work_start_date),
                         ("work_end_date", work_end_date),
                         ("agent_id", agent_id), ("group_id", group_id),
                         ("department_id", department_id), ("category", category),
                         ("sub_category", sub_category), ("item_category", item_category),
                         ("assets", assets), ("planning_fields", planning_fields),
                         ("custom_fields", custom_fields)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_put(f"releases/{release_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "release": resp.json()}
            except Exception as e:
                return handle_error(e, "update release")

        if action == "delete":
            if not release_id:
                return {"error": "release_id required for delete"}
            try:
                resp = await api_delete(f"releases/{release_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": f"Release {release_id} deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete release")

        if action == "restore":
            if not release_id:
                return {"error": "release_id required for restore"}
            try:
                resp = await api_put(f"releases/{release_id}/restore", json={})
                resp.raise_for_status()
                return {"success": True, "release": resp.json()}
            except Exception as e:
                return handle_error(e, "restore release")

        if action == "filter":
            if not query:
                return {"error": "query required for filter"}
            try:
                resp = await api_get(
                    "releases",
                    params={"query": f'"{query}"', "page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "filter releases")

        if action == "get_fields":
            try:
                resp = await api_get("release_form_fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get release fields")

        return {
            "error": f"Unknown action '{action}'. Valid: list, get, create, update, delete, "
            "filter, restore, get_fields"
        }

    # ── Release Notes ──

    @mcp.tool()
    async def manage_release_note(
        action: str,
        release_id: int,
        note_id: Optional[int] = None,
        body: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manage notes on a Freshservice release.

        Args:
            action: One of 'list', 'get', 'create', 'update', 'delete'.
            release_id: Release ID (always required).
            note_id: Note ID (required for get/update/delete).
            body: Note body HTML (required for create/update).
        """
        action = action.lower().strip()
        base = f"releases/{release_id}/notes"

        if action == "list":
            try:
                resp = await api_get(base)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list release notes")

        if action == "get":
            if not note_id:
                return {"error": "note_id required for get"}
            try:
                resp = await api_get(f"{base}/{note_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get release note")

        if action == "create":
            if not body:
                return {"error": "body required for create"}
            try:
                resp = await api_post(base, json={"body": body})
                resp.raise_for_status()
                return {"success": True, "note": resp.json()}
            except Exception as e:
                return handle_error(e, "create release note")

        if action == "update":
            if not note_id or not body:
                return {"error": "note_id and body required for update"}
            try:
                resp = await api_put(f"{base}/{note_id}", json={"body": body})
                resp.raise_for_status()
                return {"success": True, "note": resp.json()}
            except Exception as e:
                return handle_error(e, "update release note")

        if action == "delete":
            if not note_id:
                return {"error": "note_id required for delete"}
            try:
                resp = await api_delete(f"{base}/{note_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": f"Note {note_id} deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete release note")

        return {"error": f"Unknown action '{action}'. Valid: list, get, create, update, delete"}

    # ── Release Tasks ──

    @mcp.tool()
    async def manage_release_task(
        action: str,
        release_id: int,
        task_id: Optional[int] = None,
        # task fields
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[int] = None,
        due_date: Optional[str] = None,
        notify_before: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Manage tasks on a Freshservice release.

        Args:
            action: One of 'list', 'get', 'create', 'update', 'delete'.
            release_id: Release ID (always required).
            task_id: Task ID (required for get/update/delete).
            title: Task title (required for create).
            description: Task description.
            status: 1=Open, 2=In Progress, 3=Completed.
            due_date: ISO datetime due date.
            notify_before: Hours to notify before due date.
            group_id: Assigned group ID.
        """
        action = action.lower().strip()
        base = f"releases/{release_id}/tasks"

        if action == "list":
            try:
                resp = await api_get(base)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list release tasks")

        if action == "get":
            if not task_id:
                return {"error": "task_id required for get"}
            try:
                resp = await api_get(f"{base}/{task_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get release task")

        if action == "create":
            if not title:
                return {"error": "title required for create"}
            data: Dict[str, Any] = {"title": title}
            for k, v in [("description", description), ("status", status),
                         ("due_date", due_date), ("notify_before", notify_before),
                         ("group_id", group_id)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_post(base, json=data)
                resp.raise_for_status()
                return {"success": True, "task": resp.json()}
            except Exception as e:
                return handle_error(e, "create release task")

        if action == "update":
            if not task_id:
                return {"error": "task_id required for update"}
            data = {}
            for k, v in [("title", title), ("description", description),
                         ("status", status), ("due_date", due_date),
                         ("notify_before", notify_before), ("group_id", group_id)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_put(f"{base}/{task_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "task": resp.json()}
            except Exception as e:
                return handle_error(e, "update release task")

        if action == "delete":
            if not task_id:
                return {"error": "task_id required for delete"}
            try:
                resp = await api_delete(f"{base}/{task_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": f"Task {task_id} deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete release task")

        return {"error": f"Unknown action '{action}'. Valid: list, get, create, update, delete"}

    # ── Release Time Entries ──

    @mcp.tool()
    async def manage_release_time_entry(
        action: str,
        release_id: int,
        time_entry_id: Optional[int] = None,
        # time entry fields
        agent_id: Optional[int] = None,
        note: Optional[str] = None,
        time_spent: Optional[str] = None,
        executed_at: Optional[str] = None,
        task_id: Optional[int] = None,
        billable: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Manage time entries on a Freshservice release.

        Args:
            action: One of 'list', 'get', 'create', 'update', 'delete'.
            release_id: Release ID (always required).
            time_entry_id: Time entry ID (required for get/update/delete).
            agent_id: Agent who performed the work.
            note: Description of work performed.
            time_spent: Time in "hh:mm" format (required for create).
            executed_at: ISO datetime when work was performed.
            task_id: Associated task ID.
            billable: Whether the time is billable.
        """
        action = action.lower().strip()
        base = f"releases/{release_id}/time_entries"

        if action == "list":
            try:
                resp = await api_get(base)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list release time entries")

        if action == "get":
            if not time_entry_id:
                return {"error": "time_entry_id required for get"}
            try:
                resp = await api_get(f"{base}/{time_entry_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get release time entry")

        if action == "create":
            if not time_spent:
                return {"error": "time_spent required for create (format: 'hh:mm')"}
            data: Dict[str, Any] = {"time_spent": time_spent}
            for k, v in [("agent_id", agent_id), ("note", note),
                         ("executed_at", executed_at), ("task_id", task_id)]:
                if v is not None:
                    data[k] = v
            if billable is not None:
                data["billable"] = billable
            try:
                resp = await api_post(base, json=data)
                resp.raise_for_status()
                return {"success": True, "time_entry": resp.json()}
            except Exception as e:
                return handle_error(e, "create release time entry")

        if action == "update":
            if not time_entry_id:
                return {"error": "time_entry_id required for update"}
            data = {}
            for k, v in [("agent_id", agent_id), ("note", note),
                         ("time_spent", time_spent), ("executed_at", executed_at),
                         ("task_id", task_id)]:
                if v is not None:
                    data[k] = v
            if billable is not None:
                data["billable"] = billable
            try:
                resp = await api_put(f"{base}/{time_entry_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "time_entry": resp.json()}
            except Exception as e:
                return handle_error(e, "update release time entry")

        if action == "delete":
            if not time_entry_id:
                return {"error": "time_entry_id required for delete"}
            try:
                resp = await api_delete(f"{base}/{time_entry_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": f"Time entry {time_entry_id} deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete release time entry")

        return {"error": f"Unknown action '{action}'. Valid: list, get, create, update, delete"}
