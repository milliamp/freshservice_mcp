"""Freshservice MCP — Tickets tools (consolidated).

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  • read_ticket / manage_ticket
      — ticket CRUD plus sub-entities: conversations, tasks, time entries,
        and approvals. One action dispatch table per tool.
  • read_service_catalog / manage_service_catalog
      — service-catalog browsing + service-request placement (sibling of
        tickets; not folded into manage_ticket).
"""
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Union

from ..config import (
    TicketPriority,
    TicketSource,
    TicketStatus,
)
from ..http_client import (
    api_delete,
    api_get,
    api_post,
    api_post_multipart,
    api_put,
    build_attachment_parts,
    gather_enrichments,
    handle_error,
    parse_link_header,
)
from ._split import normalize_action, reject_unless_in


def _validate_pagination(page: int, per_page: int) -> Optional[Dict[str, Any]]:
    if page < 1:
        return {"error": "Page number must be greater than 0"}
    if per_page < 1 or per_page > 100:
        return {"error": "Page size must be between 1 and 100"}
    return None


def register_tickets_tools(mcp) -> None:  # noqa: C901
    """Register ticket-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  ticket + sub-entities — consolidated read/manage split             #
    # ------------------------------------------------------------------ #
    _READ_TICKET = {
        # parent
        "get", "list", "filter", "get_fields",
        # conversations
        "list_conversations",
        # tasks
        "list_tasks", "get_task",
        # time entries
        "list_time_entries", "get_time_entry",
        # approvals
        "list_approvals", "get_approval",
    }
    _WRITE_TICKET = {
        # parent
        "create", "update", "delete",
        # conversations
        "reply", "add_note", "update_conversation",
        # tasks
        "add_task", "update_task", "delete_task",
        # time entries
        "add_time_entry", "update_time_entry", "delete_time_entry",
        # approvals
        "add_approval", "approve", "reject", "remind",
    }

    async def _ticket_handler(  # noqa: C901
        action: str,
        # parent
        ticket_id: Optional[int],
        subject: Optional[str],
        description: Optional[str],
        priority: Optional[Union[int, str]],
        status: Optional[Union[int, str]],
        email: Optional[str],
        requester_id: Optional[int],
        ticket_fields: Optional[Dict[str, Any]],
        query: Optional[str],
        page: int,
        per_page: int,
        workspace_id: Optional[int],
        # sub-entity ids
        conversation_id: Optional[int],
        task_id: Optional[int],
        time_entry_id: Optional[int],
        approval_id: Optional[int],
        # shared sub-entity fields
        body: Optional[str],
        title: Optional[str],
        time_spent: Optional[str],
        approver_id: Optional[int],
        # long-tail
        payload: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        pl: Dict[str, Any] = payload or {}

        # ── parent ticket ──────────────────────────────────────────────
        if action == "get_fields":
            try:
                resp = await api_get("ticket_form_fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "fetch ticket fields")

        if action == "list":
            err = _validate_pagination(page, per_page)
            if err:
                return err
            try:
                resp = await api_get("tickets", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "tickets": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list tickets")

        if action == "filter":
            if not query:
                return {"error": "query is required for filter action"}
            encoded_query = urllib.parse.quote(f'"{query}"')
            url = f"tickets/filter?query={encoded_query}&page={page}"
            if workspace_id is not None:
                url += f"&workspace_id={workspace_id}"
            try:
                resp = await api_get(url)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "filter tickets")

        if action == "get":
            if not ticket_id:
                return {"error": "ticket_id is required for get action"}
            # Native Freshservice include params: stats + requester come back
            # embedded in the main response, saving a round trip.
            try:
                resp = await api_get(
                    f"tickets/{ticket_id}",
                    params={"include": "stats,requester"},
                )
                resp.raise_for_status()
                result = resp.json()
            except Exception as e:
                return handle_error(e, "get ticket")

            # Parallel sub-fetches for tasks and approvals (always),
            # and requested_items for Service Requests.
            jobs: Dict[str, str] = {
                "tasks": f"tickets/{ticket_id}/tasks",
                "approvals": f"tickets/{ticket_id}/approvals",
            }
            if result.get("ticket", {}).get("type") == "Service Request":
                jobs["requested_items"] = f"tickets/{ticket_id}/requested_items"
            result.update(await gather_enrichments(jobs))
            return result

        if action == "create":
            if not subject or not description:
                return {"error": "subject and description are required for create"}
            if not email and not requester_id:
                return {"error": "Either email or requester_id must be provided"}
            try:
                source_val = int(pl["source"]) if "source" in pl else TicketSource.PORTAL.value
                priority_val = int(priority) if priority else TicketPriority.LOW.value
                status_val = int(status) if status else TicketStatus.OPEN.value
            except (ValueError, TypeError):
                return {"error": "Invalid value for source, priority, or status"}
            data: Dict[str, Any] = {
                "subject": subject,
                "description": description,
                "source": source_val,
                "priority": priority_val,
                "status": status_val,
            }
            if email:
                data["email"] = email
            if requester_id:
                data["requester_id"] = requester_id
            if "custom_fields" in pl:
                data["custom_fields"] = pl["custom_fields"]
            try:
                resp = await api_post("tickets", json=data)
                resp.raise_for_status()
                return {"success": True, "ticket": resp.json()}
            except Exception as e:
                return handle_error(e, "create ticket")

        if action == "update":
            if not ticket_id:
                return {"error": "ticket_id is required for update"}
            fields = dict(ticket_fields) if ticket_fields else {}
            if priority is not None:
                fields["priority"] = int(priority)
            if status is not None:
                fields["status"] = int(status)
            if subject is not None:
                fields["subject"] = subject
            if description is not None:
                fields["description"] = description
            if "custom_fields" in pl:
                fields["custom_fields"] = pl["custom_fields"]
            if not fields:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"tickets/{ticket_id}", json=fields)
                resp.raise_for_status()
                return {"success": True, "ticket": resp.json()}
            except Exception as e:
                return handle_error(e, "update ticket")

        if action == "delete":
            if not ticket_id:
                return {"error": "ticket_id is required for delete"}
            try:
                resp = await api_delete(f"tickets/{ticket_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Ticket deleted successfully"}
                return {"error": f"Unexpected status {resp.status_code}"}
            except Exception as e:
                return handle_error(e, "delete ticket")

        # ── conversations ──────────────────────────────────────────────
        if action == "list_conversations":
            if not ticket_id:
                return {"error": "ticket_id required for list_conversations"}
            try:
                resp = await api_get(f"tickets/{ticket_id}/conversations")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list conversations")

        if action == "reply":
            if not ticket_id or not body:
                return {"error": "ticket_id and body required for reply"}
            # from_email is only sent when explicitly provided. Letting
            # Freshservice fall back to the account's default support email
            # avoids HTTP 400 from passing a non-configured address.
            attachment_paths = pl.get("attachments")
            if isinstance(attachment_paths, str):
                attachment_paths = [attachment_paths]
            try:
                if attachment_paths:
                    files = build_attachment_parts(attachment_paths)
                    form: List[Tuple[str, str]] = [("body", body.strip())]
                    if "from_email" in pl:
                        form.append(("from_email", str(pl["from_email"])))
                    if "user_id" in pl:
                        form.append(("user_id", str(pl["user_id"])))
                    for email in pl.get("cc_emails") or []:
                        form.append(("cc_emails[]", str(email)))
                    for email in pl.get("bcc_emails") or []:
                        form.append(("bcc_emails[]", str(email)))
                    resp = await api_post_multipart(
                        f"tickets/{ticket_id}/reply", data=form, files=files,
                    )
                else:
                    data = {"body": body.strip()}
                    for k in ("from_email", "user_id", "cc_emails", "bcc_emails"):
                        if k in pl:
                            data[k] = pl[k]
                    resp = await api_post(f"tickets/{ticket_id}/reply", json=data)
                resp.raise_for_status()
                return resp.json()
            except FileNotFoundError as e:
                return {"error": str(e)}
            except Exception as e:
                return handle_error(e, "reply to ticket")

        if action == "add_note":
            if not ticket_id or not body:
                return {"error": "ticket_id and body required for add_note"}
            attachment_paths = pl.get("attachments")
            if isinstance(attachment_paths, str):
                attachment_paths = [attachment_paths]
            try:
                if attachment_paths:
                    files = build_attachment_parts(attachment_paths)
                    form = [("body", body)]
                    if "private" in pl:
                        form.append(("private", str(bool(pl["private"])).lower()))
                    resp = await api_post_multipart(
                        f"tickets/{ticket_id}/notes", data=form, files=files,
                    )
                else:
                    data = {"body": body}
                    if "private" in pl:
                        data["private"] = pl["private"]
                    resp = await api_post(f"tickets/{ticket_id}/notes", json=data)
                resp.raise_for_status()
                return resp.json()
            except FileNotFoundError as e:
                return {"error": str(e)}
            except Exception as e:
                return handle_error(e, "add ticket note")

        if action == "update_conversation":
            if not conversation_id or not body:
                return {"error": "conversation_id and body required for update_conversation"}
            try:
                resp = await api_put(f"conversations/{conversation_id}", json={"body": body})
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "update conversation")

        # ── tasks ──────────────────────────────────────────────────────
        if action in {"list_tasks", "get_task", "add_task", "update_task", "delete_task"}:
            if not ticket_id:
                return {"error": "ticket_id required for task actions"}
            base = f"tickets/{ticket_id}/tasks"

            if action == "list_tasks":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list ticket tasks")

            if action == "get_task":
                if not task_id:
                    return {"error": "task_id required for get_task"}
                try:
                    resp = await api_get(f"{base}/{task_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get ticket task")

            if action == "add_task":
                if not title:
                    return {"error": "title required for add_task"}
                data = {"title": title}
                if description is not None:
                    data["description"] = description
                if status is not None:
                    data["status"] = int(status)
                for k in ("due_date", "notify_before", "group_id", "agent_id"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_post(base, json=data)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "add ticket task")

            if action == "update_task":
                if not task_id:
                    return {"error": "task_id required for update_task"}
                data = {}
                if title is not None:
                    data["title"] = title
                if description is not None:
                    data["description"] = description
                if status is not None:
                    data["status"] = int(status)
                for k in ("due_date", "notify_before", "group_id", "agent_id"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_put(f"{base}/{task_id}", json=data)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "update ticket task")

            if action == "delete_task":
                if not task_id:
                    return {"error": "task_id required for delete_task"}
                try:
                    resp = await api_delete(f"{base}/{task_id}")
                    if resp.status_code == 204:
                        return {"success": True, "message": "Task deleted"}
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "delete ticket task")

        # ── time entries ───────────────────────────────────────────────
        if action in {"list_time_entries", "get_time_entry", "add_time_entry",
                       "update_time_entry", "delete_time_entry"}:
            if not ticket_id:
                return {"error": "ticket_id required for time entry actions"}
            base = f"tickets/{ticket_id}/time_entries"

            if action == "list_time_entries":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list time entries")

            if action == "get_time_entry":
                if not time_entry_id:
                    return {"error": "time_entry_id required for get_time_entry"}
                try:
                    resp = await api_get(f"{base}/{time_entry_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get time entry")

            if action == "add_time_entry":
                te_agent_id = pl.get("te_agent_id")
                if not te_agent_id or not time_spent:
                    return {"error": "payload.te_agent_id and time_spent required for add_time_entry"}
                data = {"agent_id": te_agent_id, "time_spent": time_spent}
                if body is not None:
                    data["note"] = body
                for k in ("executed_at", "task_id", "billable", "timer_running"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_post(base, json=data)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "create time entry")

            if action == "update_time_entry":
                if not time_entry_id:
                    return {"error": "time_entry_id required for update_time_entry"}
                data = {}
                if time_spent is not None:
                    data["time_spent"] = time_spent
                if body is not None:
                    data["note"] = body
                for k in ("executed_at", "billable", "timer_running"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_put(f"{base}/{time_entry_id}", json=data)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "update time entry")

            if action == "delete_time_entry":
                if not time_entry_id:
                    return {"error": "time_entry_id required for delete_time_entry"}
                try:
                    resp = await api_delete(f"{base}/{time_entry_id}")
                    if resp.status_code == 204:
                        return {"success": True, "message": "Time entry deleted"}
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "delete time entry")

        # ── approvals ──────────────────────────────────────────────────
        if action in {"list_approvals", "get_approval", "add_approval",
                       "approve", "reject", "remind"}:
            if not ticket_id:
                return {"error": "ticket_id required for approval actions"}
            base = f"tickets/{ticket_id}/approvals"

            if action == "list_approvals":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list ticket approvals")

            if action == "get_approval":
                if not approval_id:
                    return {"error": "approval_id required for get_approval"}
                try:
                    resp = await api_get(f"{base}/{approval_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get ticket approval")

            if action == "add_approval":
                if not approver_id:
                    return {"error": "approver_id required for add_approval"}
                data = {"approver_id": approver_id}
                for k in ("approval_type", "email_content"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_post(base, json=data)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "create ticket approval")

            if action in {"approve", "reject", "remind"}:
                if not approval_id:
                    return {"error": f"approval_id required for {action}"}
                try:
                    resp = await api_put(f"{base}/{approval_id}/{action}")
                    resp.raise_for_status()
                    return {"success": True, "message": f"Approval {action} sent"}
                except Exception as e:
                    return handle_error(e, f"{action} ticket approval")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_ticket(
        action: Optional[str] = None,
        ticket_id: Optional[int] = None,
        task_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        approval_id: Optional[int] = None,
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
        workspace_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read Freshservice tickets and their sub-entities.

        Actions:
          get, list, filter, get_fields,
          list_conversations,
          list_tasks, get_task,
          list_time_entries, get_time_entry,
          list_approvals, get_approval

        Synonyms accepted: view/show/read → get, find/search → filter,
        index/all → list.

        Required per action:
          get: ticket_id
          filter: query
          list_conversations / list_tasks / list_time_entries / list_approvals: ticket_id
          get_task: ticket_id, task_id
          get_time_entry: ticket_id, time_entry_id
          get_approval: ticket_id, approval_id

        Optional: page, per_page (list/filter), workspace_id (filter).

        Default action: if not provided, inferred from params —
          ticket_id → get, query → filter, otherwise list.

        Notes:
          - get auto-enriches with stats + requester (native ?include= on
            the main fetch), plus parallel sub-fetches for tasks, approvals,
            and (on Service Requests) requested_items with their
            custom_fields. Failed sub-fetches surface as _<key>_warning.
          - get_fields returns ticket form fields incl. instance-specific
            status/priority choices — call before filter.
          - filter: query is URL-encoded and wrapped in double quotes.
            Use 'agent_id' (not 'responder_id'). Logical ops: AND, OR.
            Relational: :>, :<. Null: field:null.
            Example: "agent_id:120002355359 AND status:2"
        """
        action = normalize_action(action, _READ_TICKET)
        if not action:
            # Smart default: infer from which params the caller supplied.
            if ticket_id:
                action = "get"
            elif query:
                action = "filter"
            else:
                action = "list"
        err = reject_unless_in(action, _READ_TICKET, "read_ticket", "manage_ticket")
        if err:
            return err
        return await _ticket_handler(
            action,
            ticket_id=ticket_id,
            subject=None, description=None, priority=None, status=None,
            email=None, requester_id=None, ticket_fields=None,
            query=query, page=page, per_page=per_page, workspace_id=workspace_id,
            conversation_id=None, task_id=task_id,
            time_entry_id=time_entry_id, approval_id=approval_id,
            body=None, title=None, time_spent=None, approver_id=None,
            payload=None,
        )

    @mcp.tool()
    async def manage_ticket(
        action: str,
        ticket_id: Optional[int] = None,
        # parent ticket fields
        subject: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[Union[int, str]] = None,
        status: Optional[Union[int, str]] = None,
        email: Optional[str] = None,
        requester_id: Optional[int] = None,
        ticket_fields: Optional[Dict[str, Any]] = None,
        # sub-entity ids
        conversation_id: Optional[int] = None,
        task_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        approval_id: Optional[int] = None,
        # shared sub-entity fields
        body: Optional[str] = None,
        title: Optional[str] = None,
        time_spent: Optional[str] = None,
        approver_id: Optional[int] = None,
        # long-tail
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on tickets and their sub-entities.

        Actions:
          Ticket: create, update, delete
          Conversation: reply, add_note, update_conversation
          Task: add_task, update_task, delete_task
          Time entry: add_time_entry, update_time_entry, delete_time_entry
          Approval: add_approval, approve, reject, remind

        Required per action:
          create: subject, description, (email OR requester_id)
          update / delete: ticket_id
          reply / add_note: ticket_id, body
          update_conversation: conversation_id, body
          add_task: ticket_id, title
          update_task / delete_task: ticket_id, task_id
          add_time_entry: ticket_id, time_spent, payload.te_agent_id
          update_time_entry / delete_time_entry: ticket_id, time_entry_id
          add_approval: ticket_id, approver_id
          approve / reject / remind: ticket_id, approval_id

        Optional fields:
          - priority: 1=Low,2=Medium,3=High,4=Urgent (ticket/task)
          - status: ticket 2=Open,3=Pending,4=Resolved,5=Closed; task 1=Open,2=InProgress,3=Done
          - ticket_fields: dict of bulk-update fields
          - title: task title
          - body: conversation/note body, or time-entry note

        payload (long-tail keys) — pass only those that apply to the action:
          - source: ticket source enum (create)
          - custom_fields: dict of custom field values (create/update)
          - from_email, user_id, cc_emails, bcc_emails (reply)
              from_email is OPTIONAL: omit it and Freshservice uses the
              account's default support email. Only pass it if it is a
              configured support address — an arbitrary value will 400.
          - private (add_note): True = internal/agent-only note
          - attachments (reply/add_note): local file path string or list
              of paths. Sent as multipart/form-data. Freshservice caps:
              15 files / 40 MB total.
          - due_date, notify_before, group_id, agent_id (add_task/update_task)
          - te_agent_id (add_time_entry — REQUIRED in payload)
          - executed_at, task_id, billable, timer_running (time entries)
          - approval_type, email_content (add_approval)
        """
        action = normalize_action(action, _WRITE_TICKET)
        err = reject_unless_in(action, _WRITE_TICKET, "manage_ticket", "read_ticket")
        if err:
            return err
        return await _ticket_handler(
            action,
            ticket_id=ticket_id,
            subject=subject, description=description, priority=priority, status=status,
            email=email, requester_id=requester_id, ticket_fields=ticket_fields,
            query=None, page=1, per_page=30, workspace_id=None,
            conversation_id=conversation_id, task_id=task_id,
            time_entry_id=time_entry_id, approval_id=approval_id,
            body=body, title=title, time_spent=time_spent, approver_id=approver_id,
            payload=payload,
        )

    # ------------------------------------------------------------------ #
    #  service_catalog — read/manage split (sibling to tickets)           #
    # ------------------------------------------------------------------ #
    _READ_SERVICE_CATALOG = {"list_items", "get_requested_items"}
    _WRITE_SERVICE_CATALOG = {"place_request"}

    async def _service_catalog_handler(
        action: str,
        ticket_id: Optional[int],
        display_id: Optional[int],
        email: Optional[str],
        requested_for: Optional[str],
        quantity: int,
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        if action == "list_items":
            err = _validate_pagination(page, per_page)
            if err:
                return err
            all_items: List[Any] = []
            current_page = page
            try:
                while True:
                    resp = await api_get("service_catalog/items", params={"page": current_page, "per_page": per_page})
                    resp.raise_for_status()
                    all_items.append(resp.json())
                    pagination_info = parse_link_header(resp.headers.get("Link", ""))
                    if not pagination_info.get("next"):
                        break
                    current_page = pagination_info["next"]
                return {"success": True, "items": all_items}
            except Exception as e:
                return handle_error(e, "list service items")

        if action == "get_requested_items":
            if not ticket_id:
                return {"error": "ticket_id required"}
            try:
                ticket_resp = await api_get(f"tickets/{ticket_id}")
                ticket_resp.raise_for_status()
                if ticket_resp.json().get("ticket", {}).get("type") != "Service Request":
                    return {"error": "Requested items can only be fetched for service requests"}
                resp = await api_get(f"tickets/{ticket_id}/requested_items")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get requested items")

        if action == "place_request":
            if not display_id or not email:
                return {"error": "display_id and email required for place_request"}
            data: Dict[str, Any] = {"email": email, "quantity": quantity}
            if requested_for:
                data["requested_for"] = requested_for
            try:
                resp = await api_post(f"service_catalog/items/{display_id}/place_request", json=data)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "place service request")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_service_catalog(
        action: str,
        ticket_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice service catalog.

        Actions: list_items, get_requested_items
        Required per action:
          get_requested_items: ticket_id
        Optional: page, per_page (list_items).
        """
        action = normalize_action(action, _READ_SERVICE_CATALOG)
        err = reject_unless_in(action, _READ_SERVICE_CATALOG, "read_service_catalog", "manage_service_catalog")
        if err:
            return err
        return await _service_catalog_handler(
            action, ticket_id, display_id=None, email=None, requested_for=None,
            quantity=1, page=page, per_page=per_page,
        )

    @mcp.tool()
    async def manage_service_catalog(
        action: str,
        display_id: Optional[int] = None,
        email: Optional[str] = None,
        requested_for: Optional[str] = None,
        quantity: int = 1,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice service catalog.

        Actions: place_request
        Required per action:
          place_request: display_id, email
        Optional: requested_for (target user email), quantity (default 1).
        """
        action = normalize_action(action, _WRITE_SERVICE_CATALOG)
        err = reject_unless_in(action, _WRITE_SERVICE_CATALOG, "manage_service_catalog", "read_service_catalog")
        if err:
            return err
        return await _service_catalog_handler(
            action, ticket_id=None, display_id=display_id, email=email,
            requested_for=requested_for, quantity=quantity, page=1, per_page=30,
        )
