"""Freshservice MCP — Problem Management tools (consolidated).

Each consolidated tool is exposed as a read_/manage_ pair so MCP clients
can grant read-only or read-write access independently.

Tools:
  • read_problem / manage_problem
      — problem CRUD plus sub-entities: notes, tasks, time entries.
"""
from typing import Any, Dict, List, Optional

from ..http_client import api_delete, api_get, api_post, api_put, handle_error
from ._split import reject_unless_in


def register_problem_tools(mcp) -> None:  # noqa: C901
    """Register problem management tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  problem + sub-entities — consolidated read/manage split            #
    # ------------------------------------------------------------------ #
    _READ_PROBLEM = {
        # parent
        "get", "list", "filter", "get_fields",
        # notes
        "list_notes", "get_note",
        # tasks
        "list_tasks", "get_task",
        # time entries
        "list_time_entries", "get_time_entry",
    }
    _WRITE_PROBLEM = {
        # parent
        "create", "update", "delete", "close", "restore",
        # notes
        "add_note", "update_note", "delete_note",
        # tasks
        "add_task", "update_task", "delete_task",
        # time entries
        "add_time_entry", "update_time_entry", "delete_time_entry",
    }

    async def _problem_handler(  # noqa: C901
        action: str,
        # parent
        problem_id: Optional[int],
        subject: Optional[str],
        description: Optional[str],
        priority: Optional[int],
        status: Optional[int],
        impact: Optional[int],
        due_by: Optional[str],
        requester_id: Optional[int],
        query: Optional[str],
        page: int,
        per_page: int,
        # sub-entity ids
        note_id: Optional[int],
        task_id: Optional[int],
        time_entry_id: Optional[int],
        # shared sub-entity fields
        body: Optional[str],
        title: Optional[str],
        time_spent: Optional[str],
        # long-tail
        payload: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        pl: Dict[str, Any] = payload or {}

        # ── parent ─────────────────────────────────────────────────────
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
            required = {"requester_id": requester_id, "subject": subject,
                        "description": description, "priority": priority,
                        "status": status, "impact": impact, "due_by": due_by}
            missing = [k for k, v in required.items() if v in (None, "")]
            if missing:
                return {"error": f"Required for create: {', '.join(missing)}"}
            data: Dict[str, Any] = dict(required)
            for k in ("agent_id", "group_id", "department_id", "category",
                      "sub_category", "item_category", "assets",
                      "custom_fields", "analysis_fields", "known_error"):
                if k in pl:
                    data[k] = pl[k]
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
                          ("status", status), ("impact", impact), ("due_by", due_by)]:
                if v is not None:
                    data[k] = v
            for k in ("agent_id", "group_id", "department_id", "category",
                      "sub_category", "item_category", "assets",
                      "custom_fields", "analysis_fields", "known_error"):
                if k in pl:
                    data[k] = pl[k]
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
            try:
                resp = await api_put(f"problems/{problem_id}", json={"status": 3})
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
                return {"error": "query required for filter"}
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

        # ── notes ──────────────────────────────────────────────────────
        if action in {"list_notes", "get_note", "add_note", "update_note", "delete_note"}:
            if not problem_id:
                return {"error": "problem_id required for note actions"}
            base = f"problems/{problem_id}/notes"

            if action == "list_notes":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list problem notes")

            if action == "get_note":
                if not note_id:
                    return {"error": "note_id required for get_note"}
                try:
                    resp = await api_get(f"{base}/{note_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get problem note")

            if action == "add_note":
                if not body:
                    return {"error": "body required for add_note"}
                try:
                    resp = await api_post(base, json={"body": body})
                    resp.raise_for_status()
                    return {"success": True, "note": resp.json()}
                except Exception as e:
                    return handle_error(e, "add problem note")

            if action == "update_note":
                if not note_id or not body:
                    return {"error": "note_id and body required for update_note"}
                try:
                    resp = await api_put(f"{base}/{note_id}", json={"body": body})
                    resp.raise_for_status()
                    return {"success": True, "note": resp.json()}
                except Exception as e:
                    return handle_error(e, "update problem note")

            if action == "delete_note":
                if not note_id:
                    return {"error": "note_id required for delete_note"}
                try:
                    resp = await api_delete(f"{base}/{note_id}")
                    if resp.status_code == 204:
                        return {"success": True, "message": f"Note {note_id} deleted"}
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "delete problem note")

        # ── tasks ──────────────────────────────────────────────────────
        if action in {"list_tasks", "get_task", "add_task", "update_task", "delete_task"}:
            if not problem_id:
                return {"error": "problem_id required for task actions"}
            base = f"problems/{problem_id}/tasks"

            if action == "list_tasks":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list problem tasks")

            if action == "get_task":
                if not task_id:
                    return {"error": "task_id required for get_task"}
                try:
                    resp = await api_get(f"{base}/{task_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get problem task")

            if action == "add_task":
                if not title:
                    return {"error": "title required for add_task"}
                data: Dict[str, Any] = {"title": title}
                if description is not None:
                    data["description"] = description
                if status is not None:
                    data["status"] = status
                for k in ("due_date", "notify_before", "group_id"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_post(base, json=data)
                    resp.raise_for_status()
                    return {"success": True, "task": resp.json()}
                except Exception as e:
                    return handle_error(e, "add problem task")

            if action == "update_task":
                if not task_id:
                    return {"error": "task_id required for update_task"}
                data = {}
                if title is not None:
                    data["title"] = title
                if description is not None:
                    data["description"] = description
                if status is not None:
                    data["status"] = status
                for k in ("due_date", "notify_before", "group_id"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_put(f"{base}/{task_id}", json=data)
                    resp.raise_for_status()
                    return {"success": True, "task": resp.json()}
                except Exception as e:
                    return handle_error(e, "update problem task")

            if action == "delete_task":
                if not task_id:
                    return {"error": "task_id required for delete_task"}
                try:
                    resp = await api_delete(f"{base}/{task_id}")
                    if resp.status_code == 204:
                        return {"success": True, "message": f"Task {task_id} deleted"}
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "delete problem task")

        # ── time entries ───────────────────────────────────────────────
        if action in {"list_time_entries", "get_time_entry", "add_time_entry",
                       "update_time_entry", "delete_time_entry"}:
            if not problem_id:
                return {"error": "problem_id required for time entry actions"}
            base = f"problems/{problem_id}/time_entries"

            if action == "list_time_entries":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list problem time entries")

            if action == "get_time_entry":
                if not time_entry_id:
                    return {"error": "time_entry_id required for get_time_entry"}
                try:
                    resp = await api_get(f"{base}/{time_entry_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get problem time entry")

            if action == "add_time_entry":
                if not time_spent:
                    return {"error": "time_spent required for add_time_entry ('hh:mm')"}
                data: Dict[str, Any] = {"time_spent": time_spent}
                if body is not None:
                    data["note"] = body
                for k in ("te_agent_id", "executed_at", "task_id", "billable"):
                    if k in pl:
                        api_key = "agent_id" if k == "te_agent_id" else k
                        data[api_key] = pl[k]
                try:
                    resp = await api_post(base, json=data)
                    resp.raise_for_status()
                    return {"success": True, "time_entry": resp.json()}
                except Exception as e:
                    return handle_error(e, "create problem time entry")

            if action == "update_time_entry":
                if not time_entry_id:
                    return {"error": "time_entry_id required for update_time_entry"}
                data = {}
                if time_spent is not None:
                    data["time_spent"] = time_spent
                if body is not None:
                    data["note"] = body
                for k in ("te_agent_id", "executed_at", "task_id", "billable"):
                    if k in pl:
                        api_key = "agent_id" if k == "te_agent_id" else k
                        data[api_key] = pl[k]
                try:
                    resp = await api_put(f"{base}/{time_entry_id}", json=data)
                    resp.raise_for_status()
                    return {"success": True, "time_entry": resp.json()}
                except Exception as e:
                    return handle_error(e, "update problem time entry")

            if action == "delete_time_entry":
                if not time_entry_id:
                    return {"error": "time_entry_id required for delete_time_entry"}
                try:
                    resp = await api_delete(f"{base}/{time_entry_id}")
                    if resp.status_code == 204:
                        return {"success": True, "message": f"Time entry {time_entry_id} deleted"}
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "delete problem time entry")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_problem(
        action: str,
        problem_id: Optional[int] = None,
        note_id: Optional[int] = None,
        task_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice problems and their sub-entities.

        Actions:
          get, list, filter, get_fields,
          list_notes, get_note,
          list_tasks, get_task,
          list_time_entries, get_time_entry

        Required per action:
          get: problem_id
          filter: query
          list_notes / list_tasks / list_time_entries: problem_id
          get_note: problem_id, note_id
          get_task: problem_id, task_id
          get_time_entry: problem_id, time_entry_id

        Optional: page, per_page (list/filter).
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _READ_PROBLEM, "read_problem", "manage_problem")
        if err:
            return err
        return await _problem_handler(
            action,
            problem_id=problem_id,
            subject=None, description=None, priority=None, status=None,
            impact=None, due_by=None, requester_id=None,
            query=query, page=page, per_page=per_page,
            note_id=note_id, task_id=task_id, time_entry_id=time_entry_id,
            body=None, title=None, time_spent=None,
            payload=None,
        )

    @mcp.tool()
    async def manage_problem(
        action: str,
        problem_id: Optional[int] = None,
        # parent fields
        subject: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        status: Optional[int] = None,
        impact: Optional[int] = None,
        due_by: Optional[str] = None,
        requester_id: Optional[int] = None,
        # sub-entity ids
        note_id: Optional[int] = None,
        task_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        # shared sub-entity fields
        body: Optional[str] = None,
        title: Optional[str] = None,
        time_spent: Optional[str] = None,
        # long-tail
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on problems and their sub-entities.

        Actions:
          Problem: create, update, delete, close, restore
          Notes: add_note, update_note, delete_note
          Tasks: add_task, update_task, delete_task
          Time entries: add_time_entry, update_time_entry, delete_time_entry

        Required per action:
          create: requester_id, subject, description, priority, status,
                  impact, due_by
          update / delete / close / restore: problem_id
          add_note: problem_id, body
          update_note: problem_id, note_id, body
          delete_note: problem_id, note_id
          add_task: problem_id, title
          update_task / delete_task: problem_id, task_id
          add_time_entry: problem_id, time_spent
          update_time_entry / delete_time_entry: problem_id, time_entry_id

        Optional fields:
          priority: 1=Low,2=Medium,3=High,4=Urgent (problem/task)
          status: problem 1=Open,2=ChangeRequested,3=Closed;
                  task 1=Open,2=InProgress,3=Done
          impact: 1=Low,2=Medium,3=High
          body: note body / time-entry note text
          title / description: task fields

        payload (long-tail keys) — pass only those that apply:
          - agent_id, group_id, department_id, known_error, category,
            sub_category, item_category, assets, analysis_fields,
            custom_fields (problem create/update)
          - due_date, notify_before, group_id (task)
          - te_agent_id, executed_at, task_id, billable (time entry)
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _WRITE_PROBLEM, "manage_problem", "read_problem")
        if err:
            return err
        return await _problem_handler(
            action,
            problem_id=problem_id,
            subject=subject, description=description, priority=priority, status=status,
            impact=impact, due_by=due_by, requester_id=requester_id,
            query=None, page=1, per_page=30,
            note_id=note_id, task_id=task_id, time_entry_id=time_entry_id,
            body=body, title=title, time_spent=time_spent,
            payload=payload,
        )
