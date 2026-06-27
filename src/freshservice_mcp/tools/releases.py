"""Freshservice MCP — Release Management tools (consolidated).

Each consolidated tool is exposed as a read_/manage_ pair so MCP clients
can grant read-only or read-write access independently.

Tools:
  • read_release / manage_release
      — release CRUD plus sub-entities: notes, tasks, time entries.
"""
from typing import Any, Dict, List, Optional

from ..http_client import (
    api_delete,
    api_get,
    api_post,
    api_put,
    gather_enrichments,
    handle_error,
)
from ._split import normalize_action, reject_unless_in


def register_release_tools(mcp) -> None:  # noqa: C901
    """Register release management tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  release + sub-entities — consolidated read/manage split            #
    # ------------------------------------------------------------------ #
    _READ_RELEASE = {
        # parent
        "get", "list", "filter", "get_fields",
        # notes
        "list_notes", "get_note",
        # tasks
        "list_tasks", "get_task",
        # time entries
        "list_time_entries", "get_time_entry",
    }
    _WRITE_RELEASE = {
        # parent
        "create", "update", "delete", "restore",
        # notes
        "add_note", "update_note", "delete_note",
        # tasks
        "add_task", "update_task", "delete_task",
        # time entries
        "add_time_entry", "update_time_entry", "delete_time_entry",
    }

    async def _release_handler(  # noqa: C901
        action: str,
        # parent
        release_id: Optional[int],
        subject: Optional[str],
        description: Optional[str],
        priority: Optional[int],
        status: Optional[int],
        release_type: Optional[int],
        planned_start_date: Optional[str],
        planned_end_date: Optional[str],
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
                result = resp.json()
            except Exception as e:
                return handle_error(e, "get release")
            # Parallel sub-fetches for notes and tasks.
            result.update(await gather_enrichments({
                "notes": f"releases/{release_id}/notes",
                "tasks": f"releases/{release_id}/tasks",
            }))
            return result

        if action == "create":
            required = {"subject": subject, "description": description,
                        "priority": priority, "status": status,
                        "release_type": release_type,
                        "planned_start_date": planned_start_date,
                        "planned_end_date": planned_end_date}
            missing = [k for k, v in required.items() if v in (None, "")]
            if missing:
                return {"error": f"Required for create: {', '.join(missing)}"}
            data: Dict[str, Any] = dict(required)
            for k in ("work_start_date", "work_end_date", "agent_id", "group_id",
                      "department_id", "category", "sub_category", "item_category",
                      "assets", "custom_fields"):
                if k in pl:
                    data[k] = pl[k]
            # planning_fields cannot be set on create — defer to a follow-up PUT
            deferred_planning = pl.get("planning_fields")
            try:
                resp = await api_post("releases", json=data)
                resp.raise_for_status()
                result = resp.json()
            except Exception as e:
                return handle_error(e, "create release")

            if deferred_planning:
                new_id = result.get("release", {}).get("id")
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
                          ("planned_end_date", planned_end_date)]:
                if v is not None:
                    data[k] = v
            for k in ("work_start_date", "work_end_date", "agent_id", "group_id",
                      "department_id", "category", "sub_category", "item_category",
                      "assets", "custom_fields", "planning_fields"):
                if k in pl:
                    data[k] = pl[k]
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

        # ── notes ──────────────────────────────────────────────────────
        if action in {"list_notes", "get_note", "add_note", "update_note", "delete_note"}:
            if not release_id:
                return {"error": "release_id required for note actions"}
            base = f"releases/{release_id}/notes"

            if action == "list_notes":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list release notes")

            if action == "get_note":
                if not note_id:
                    return {"error": "note_id required for get_note"}
                try:
                    resp = await api_get(f"{base}/{note_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get release note")

            if action == "add_note":
                if not body:
                    return {"error": "body required for add_note"}
                try:
                    resp = await api_post(base, json={"body": body})
                    resp.raise_for_status()
                    return {"success": True, "note": resp.json()}
                except Exception as e:
                    return handle_error(e, "add release note")

            if action == "update_note":
                if not note_id or not body:
                    return {"error": "note_id and body required for update_note"}
                try:
                    resp = await api_put(f"{base}/{note_id}", json={"body": body})
                    resp.raise_for_status()
                    return {"success": True, "note": resp.json()}
                except Exception as e:
                    return handle_error(e, "update release note")

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
                    return handle_error(e, "delete release note")

        # ── tasks ──────────────────────────────────────────────────────
        if action in {"list_tasks", "get_task", "add_task", "update_task", "delete_task"}:
            if not release_id:
                return {"error": "release_id required for task actions"}
            base = f"releases/{release_id}/tasks"

            if action == "list_tasks":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list release tasks")

            if action == "get_task":
                if not task_id:
                    return {"error": "task_id required for get_task"}
                try:
                    resp = await api_get(f"{base}/{task_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get release task")

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
                    return handle_error(e, "add release task")

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
                    return handle_error(e, "update release task")

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
                    return handle_error(e, "delete release task")

        # ── time entries ───────────────────────────────────────────────
        if action in {"list_time_entries", "get_time_entry", "add_time_entry",
                       "update_time_entry", "delete_time_entry"}:
            if not release_id:
                return {"error": "release_id required for time entry actions"}
            base = f"releases/{release_id}/time_entries"

            if action == "list_time_entries":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list release time entries")

            if action == "get_time_entry":
                if not time_entry_id:
                    return {"error": "time_entry_id required for get_time_entry"}
                try:
                    resp = await api_get(f"{base}/{time_entry_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get release time entry")

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
                    return handle_error(e, "create release time entry")

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
                    return handle_error(e, "update release time entry")

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
                    return handle_error(e, "delete release time entry")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_release(
        action: Optional[str] = None,
        release_id: Optional[int] = None,
        note_id: Optional[int] = None,
        task_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice releases and their sub-entities.

        Actions:
          get, list, filter, get_fields,
          list_notes, get_note,
          list_tasks, get_task,
          list_time_entries, get_time_entry

        Synonyms accepted: view/show/read → get, find/search → filter,
        index/all → list.

        Required per action:
          get: release_id
          filter: query
          list_notes / list_tasks / list_time_entries: release_id
          get_note: release_id, note_id
          get_task: release_id, task_id
          get_time_entry: release_id, time_entry_id

        Optional: page, per_page (list/filter).

        Default action: if not provided, inferred from params —
          release_id → get, query → filter, otherwise list.

        Notes:
          - get auto-enriches with notes and tasks (parallel sub-fetches).
            Failed sub-fetches surface as _<key>_warning.
        """
        action = normalize_action(action)
        if not action:
            if release_id:
                action = "get"
            elif query:
                action = "filter"
            else:
                action = "list"
        err = reject_unless_in(action, _READ_RELEASE, "read_release", "manage_release")
        if err:
            return err
        return await _release_handler(
            action,
            release_id=release_id,
            subject=None, description=None, priority=None, status=None,
            release_type=None, planned_start_date=None, planned_end_date=None,
            query=query, page=page, per_page=per_page,
            note_id=note_id, task_id=task_id, time_entry_id=time_entry_id,
            body=None, title=None, time_spent=None,
            payload=None,
        )

    @mcp.tool()
    async def manage_release(
        action: str,
        release_id: Optional[int] = None,
        # parent fields
        subject: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        status: Optional[int] = None,
        release_type: Optional[int] = None,
        planned_start_date: Optional[str] = None,
        planned_end_date: Optional[str] = None,
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
        """Write actions on releases and their sub-entities.

        Actions:
          Release: create, update, delete, restore
          Notes: add_note, update_note, delete_note
          Tasks: add_task, update_task, delete_task
          Time entries: add_time_entry, update_time_entry, delete_time_entry

        Required per action:
          create: subject, description, priority, status, release_type,
                  planned_start_date, planned_end_date
          update / delete / restore: release_id
          add_note: release_id, body
          update_note: release_id, note_id, body
          delete_note: release_id, note_id
          add_task: release_id, title
          update_task / delete_task: release_id, task_id
          add_time_entry: release_id, time_spent
          update_time_entry / delete_time_entry: release_id, time_entry_id

        Optional fields:
          priority: 1=Low,2=Medium,3=High,4=Urgent
          status: release 1=Open,2=OnHold,3=InProgress,4=Incomplete,5=Completed;
                  task 1=Open,2=InProgress,3=Done
          release_type: 1=Minor,2=Standard,3=Major,4=Emergency
          body: note body / time-entry note text
          title / description: task fields

        payload (long-tail keys) — pass only those that apply:
          - work_start_date, work_end_date, agent_id, group_id,
            department_id, category, sub_category, item_category, assets,
            custom_fields, planning_fields (release create/update;
            planning_fields is applied via follow-up PUT on create)
          - due_date, notify_before, group_id (task)
          - te_agent_id, executed_at, task_id, billable (time entry)
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _WRITE_RELEASE, "manage_release", "read_release")
        if err:
            return err
        return await _release_handler(
            action,
            release_id=release_id,
            subject=subject, description=description, priority=priority, status=status,
            release_type=release_type,
            planned_start_date=planned_start_date, planned_end_date=planned_end_date,
            query=None, page=1, per_page=30,
            note_id=note_id, task_id=task_id, time_entry_id=time_entry_id,
            body=body, title=title, time_spent=time_spent,
            payload=payload,
        )
