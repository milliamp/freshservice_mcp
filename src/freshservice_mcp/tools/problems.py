"""Freshservice MCP — Problem Management tools.

Exposes 4 tools:
  • manage_problem           — CRUD + list/filter/close/restore problems
  • manage_problem_note      — CRUD notes on a problem
  • manage_problem_task      — CRUD tasks on a problem
  • manage_problem_time_entry — CRUD time entries on a problem
"""
from typing import Any, Dict, List, Optional

from ..http_client import api_delete, api_get, api_post, api_put, handle_error


def register_problem_tools(mcp) -> None:
    """Register problem management tools on *mcp*."""

    @mcp.tool()
    async def manage_problem(
        action: str,
        problem_id: Optional[int] = None,
        # core fields
        requester_id: Optional[int] = None,
        subject: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        status: Optional[int] = None,
        impact: Optional[int] = None,
        due_by: Optional[str] = None,
        # optional fields
        agent_id: Optional[int] = None,
        group_id: Optional[int] = None,
        department_id: Optional[int] = None,
        known_error: Optional[bool] = None,
        category: Optional[str] = None,
        sub_category: Optional[str] = None,
        item_category: Optional[str] = None,
        assets: Optional[List[Dict[str, Any]]] = None,
        analysis_fields: Optional[Dict[str, Any]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        # filter / pagination
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice problems.

        Args:
            action: One of 'list', 'get', 'create', 'update', 'delete',
                    'filter', 'close', 'restore', 'get_fields'.
            problem_id: Problem ID (required for get/update/delete/close/restore).
            requester_id: Requester user ID (required for create).
            subject: Problem subject (required for create).
            description: HTML description (required for create).
            priority: 1=Low, 2=Medium, 3=High, 4=Urgent (required for create).
            status: 1=Open, 2=Change Requested, 3=Closed (required for create).
            impact: 1=Low, 2=Medium, 3=High (required for create).
            due_by: ISO datetime due date (required for create).
            agent_id: Assigned agent ID.
            group_id: Assigned group ID.
            department_id: Department ID.
            known_error: Mark as known error (boolean).
            category/sub_category/item_category: Problem categorization.
            assets: List of associated assets [{"display_id": N}].
            analysis_fields: Analysis fields dict (problem_cause, symptom, impact).
            custom_fields: Custom fields dict.
            query: Filter query for 'filter' action
                   (e.g. "priority:3 AND status:1").
            page/per_page: Pagination.
        """
        action = action.lower().strip()

        if action == "list":
            try:
                resp = await api_get("problems", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list problems")

        if action == "get":
            if not problem_id:
                return {"error": "problem_id required for get"}
            try:
                resp = await api_get(f"problems/{problem_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get problem")

        if action == "create":
            if not all([requester_id, subject, description, priority, status, impact, due_by]):
                return {
                    "error": "Required for create: requester_id, subject, description, "
                    "priority, status, impact, due_by"
                }
            data: Dict[str, Any] = {
                "requester_id": requester_id,
                "subject": subject,
                "description": description,
                "priority": priority,
                "status": status,
                "impact": impact,
                "due_by": due_by,
            }
            for k, v in [("agent_id", agent_id), ("group_id", group_id),
                         ("department_id", department_id), ("category", category),
                         ("sub_category", sub_category), ("item_category", item_category),
                         ("assets", assets), ("custom_fields", custom_fields)]:
                if v is not None:
                    data[k] = v
            if known_error is not None:
                data["known_error"] = known_error
            if analysis_fields:
                data["analysis_fields"] = analysis_fields
            try:
                resp = await api_post("problems", json=data)
                resp.raise_for_status()
                return {"success": True, "problem": resp.json()}
            except Exception as e:
                return handle_error(e, "create problem")

        if action == "update":
            if not problem_id:
                return {"error": "problem_id required for update"}
            data = {}
            for k, v in [("requester_id", requester_id), ("subject", subject),
                         ("description", description), ("priority", priority),
                         ("status", status), ("impact", impact), ("due_by", due_by),
                         ("agent_id", agent_id), ("group_id", group_id),
                         ("department_id", department_id), ("category", category),
                         ("sub_category", sub_category), ("item_category", item_category),
                         ("assets", assets), ("custom_fields", custom_fields),
                         ("analysis_fields", analysis_fields)]:
                if v is not None:
                    data[k] = v
            if known_error is not None:
                data["known_error"] = known_error
            try:
                resp = await api_put(f"problems/{problem_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "problem": resp.json()}
            except Exception as e:
                return handle_error(e, "update problem")

        if action == "delete":
            if not problem_id:
                return {"error": "problem_id required for delete"}
            try:
                resp = await api_delete(f"problems/{problem_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": f"Problem {problem_id} deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete problem")

        if action == "close":
            if not problem_id:
                return {"error": "problem_id required for close"}
            data = {"status": 3}  # 3 = Closed
            try:
                resp = await api_put(f"problems/{problem_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "problem": resp.json()}
            except Exception as e:
                return handle_error(e, "close problem")

        if action == "restore":
            if not problem_id:
                return {"error": "problem_id required for restore"}
            try:
                resp = await api_put(f"problems/{problem_id}/restore", json={})
                resp.raise_for_status()
                return {"success": True, "problem": resp.json()}
            except Exception as e:
                return handle_error(e, "restore problem")

        if action == "filter":
            if not query:
                return {"error": "query required for filter (e.g. \"priority:3 AND status:1\")"}
            try:
                resp = await api_get(
                    "problems",
                    params={"query": f'"{query}"', "page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "filter problems")

        if action == "get_fields":
            try:
                resp = await api_get("problem_form_fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get problem fields")

        return {
            "error": f"Unknown action '{action}'. Valid: list, get, create, update, delete, "
            "filter, close, restore, get_fields"
        }

    # ── Problem Notes ──

    @mcp.tool()
    async def manage_problem_note(
        action: str,
        problem_id: int,
        note_id: Optional[int] = None,
        body: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manage notes on a Freshservice problem.

        Args:
            action: One of 'list', 'get', 'create', 'update', 'delete'.
            problem_id: Problem ID (always required).
            note_id: Note ID (required for get/update/delete).
            body: Note body HTML (required for create/update).
        """
        action = action.lower().strip()
        base = f"problems/{problem_id}/notes"

        if action == "list":
            try:
                resp = await api_get(base)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list problem notes")

        if action == "get":
            if not note_id:
                return {"error": "note_id required for get"}
            try:
                resp = await api_get(f"{base}/{note_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get problem note")

        if action == "create":
            if not body:
                return {"error": "body required for create"}
            try:
                resp = await api_post(base, json={"body": body})
                resp.raise_for_status()
                return {"success": True, "note": resp.json()}
            except Exception as e:
                return handle_error(e, "create problem note")

        if action == "update":
            if not note_id or not body:
                return {"error": "note_id and body required for update"}
            try:
                resp = await api_put(f"{base}/{note_id}", json={"body": body})
                resp.raise_for_status()
                return {"success": True, "note": resp.json()}
            except Exception as e:
                return handle_error(e, "update problem note")

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
                return handle_error(e, "delete problem note")

        return {"error": f"Unknown action '{action}'. Valid: list, get, create, update, delete"}

    # ── Problem Tasks ──

    @mcp.tool()
    async def manage_problem_task(
        action: str,
        problem_id: int,
        task_id: Optional[int] = None,
        # task fields
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[int] = None,
        due_date: Optional[str] = None,
        notify_before: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Manage tasks on a Freshservice problem.

        Args:
            action: One of 'list', 'get', 'create', 'update', 'delete'.
            problem_id: Problem ID (always required).
            task_id: Task ID (required for get/update/delete).
            title: Task title (required for create).
            description: Task description.
            status: 1=Open, 2=In Progress, 3=Completed.
            due_date: ISO datetime due date.
            notify_before: Hours to notify before due date.
            group_id: Assigned group ID.
        """
        action = action.lower().strip()
        base = f"problems/{problem_id}/tasks"

        if action == "list":
            try:
                resp = await api_get(base)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list problem tasks")

        if action == "get":
            if not task_id:
                return {"error": "task_id required for get"}
            try:
                resp = await api_get(f"{base}/{task_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get problem task")

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
                return handle_error(e, "create problem task")

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
                return handle_error(e, "update problem task")

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
                return handle_error(e, "delete problem task")

        return {"error": f"Unknown action '{action}'. Valid: list, get, create, update, delete"}

    # ── Problem Time Entries ──

    @mcp.tool()
    async def manage_problem_time_entry(
        action: str,
        problem_id: int,
        time_entry_id: Optional[int] = None,
        # time entry fields
        agent_id: Optional[int] = None,
        note: Optional[str] = None,
        time_spent: Optional[str] = None,
        executed_at: Optional[str] = None,
        task_id: Optional[int] = None,
        billable: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Manage time entries on a Freshservice problem.

        Args:
            action: One of 'list', 'get', 'create', 'update', 'delete'.
            problem_id: Problem ID (always required).
            time_entry_id: Time entry ID (required for get/update/delete).
            agent_id: Agent who performed the work.
            note: Description of work performed.
            time_spent: Time in "hh:mm" format (required for create).
            executed_at: ISO datetime when work was performed.
            task_id: Associated task ID.
            billable: Whether the time is billable.
        """
        action = action.lower().strip()
        base = f"problems/{problem_id}/time_entries"

        if action == "list":
            try:
                resp = await api_get(base)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list problem time entries")

        if action == "get":
            if not time_entry_id:
                return {"error": "time_entry_id required for get"}
            try:
                resp = await api_get(f"{base}/{time_entry_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get problem time entry")

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
                return handle_error(e, "create problem time entry")

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
                return handle_error(e, "update problem time entry")

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
                return handle_error(e, "delete problem time entry")

        return {"error": f"Unknown action '{action}'. Valid: list, get, create, update, delete"}
