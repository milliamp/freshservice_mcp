"""Freshservice MCP — Tickets tools (consolidated).

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  • read_ticket / manage_ticket
      — get/list/filter/get_fields vs create/update/delete
  • read_ticket_conversation / manage_ticket_conversation
      — list vs reply/add_note/update
  • read_service_catalog / manage_service_catalog
      — list_items/get_requested_items vs place_request
  • read_ticket_task / manage_ticket_task
      — view/list vs create/update/delete
  • read_ticket_time_entry / manage_ticket_time_entry
      — view/list vs create/update/delete
  • read_ticket_approval / manage_ticket_approval
      — list/view vs create/approve/reject/remind
"""
import urllib.parse
from typing import Any, Dict, List, Optional, Union

from ..config import (
    FRESHSERVICE_DOMAIN,
    TicketPriority,
    TicketSource,
    TicketStatus,
)
from ..http_client import (
    api_delete,
    api_get,
    api_post,
    api_put,
    handle_error,
    parse_link_header,
)
from ._split import reject_unless_in


# ── helpers ────────────────────────────────────────────────────────────────
def _validate_pagination(page: int, per_page: int) -> Optional[Dict[str, Any]]:
    if page < 1:
        return {"error": "Page number must be greater than 0"}
    if per_page < 1 or per_page > 100:
        return {"error": "Page size must be between 1 and 100"}
    return None


# ── registration ───────────────────────────────────────────────────────────
def register_tickets_tools(mcp) -> None:  # noqa: C901
    """Register ticket-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  ticket — read/manage split                                         #
    # ------------------------------------------------------------------ #
    _READ_TICKET = {"get", "list", "filter", "get_fields"}
    _WRITE_TICKET = {"create", "update", "delete"}

    async def _ticket_handler(
        action: str,
        ticket_id: Optional[int],
        subject: Optional[str],
        description: Optional[str],
        source: Optional[Union[int, str]],
        priority: Optional[Union[int, str]],
        status: Optional[Union[int, str]],
        email: Optional[str],
        requester_id: Optional[int],
        custom_fields: Optional[Dict[str, Any]],
        ticket_fields: Optional[Dict[str, Any]],
        query: Optional[str],
        page: int,
        per_page: int,
        workspace_id: Optional[int],
    ) -> Dict[str, Any]:
        # ---------- get_fields ----------
        if action == "get_fields":
            try:
                resp = await api_get("ticket_form_fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "fetch ticket fields")

        # ---------- list ----------
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

        # ---------- filter ----------
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

        # ---------- get ----------
        if action == "get":
            if not ticket_id:
                return {"error": "ticket_id is required for get action"}
            try:
                resp = await api_get(f"tickets/{ticket_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get ticket")

        # ---------- create ----------
        if action == "create":
            if not subject or not description:
                return {"error": "subject and description are required for create action"}
            if not email and not requester_id:
                return {"error": "Either email or requester_id must be provided"}
            try:
                source_val = int(source) if source else TicketSource.PORTAL.value
                priority_val = int(priority) if priority else TicketPriority.LOW.value
                status_val = int(status) if status else TicketStatus.OPEN.value
            except ValueError:
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
            if custom_fields:
                data["custom_fields"] = custom_fields

            try:
                resp = await api_post("tickets", json=data)
                resp.raise_for_status()
                return {"success": True, "ticket": resp.json()}
            except Exception as e:
                return handle_error(e, "create ticket")

        # ---------- update ----------
        if action == "update":
            if not ticket_id:
                return {"error": "ticket_id is required for update action"}
            fields = ticket_fields or {}
            if priority is not None:
                fields["priority"] = int(priority)
            if status is not None:
                fields["status"] = int(status)
            if subject is not None:
                fields["subject"] = subject
            if description is not None:
                fields["description"] = description
            if custom_fields:
                fields["custom_fields"] = custom_fields
            if not fields:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"tickets/{ticket_id}", json=fields)
                resp.raise_for_status()
                return {"success": True, "ticket": resp.json()}
            except Exception as e:
                return handle_error(e, "update ticket")

        # ---------- delete ----------
        if action == "delete":
            if not ticket_id:
                return {"error": "ticket_id is required for delete action"}
            try:
                resp = await api_delete(f"tickets/{ticket_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Ticket deleted successfully"}
                return {"error": f"Unexpected status {resp.status_code}"}
            except Exception as e:
                return handle_error(e, "delete ticket")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_ticket(
        action: str,
        ticket_id: Optional[int] = None,
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
        workspace_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read Freshservice tickets.

        Args:
            action: One of 'get', 'list', 'filter', 'get_fields'
            ticket_id: Required for get
            query: Filter query string, e.g. "priority:3 AND status:2" (filter)
            page: Page number (list/filter)
            per_page: Items per page 1-100 (list)
            workspace_id: Workspace filter (filter)

        Action-specific notes:

        **get_fields**: Retrieves all ticket form fields including metadata, types,
        and possible values. Essential for discovering valid status/priority values
        since these are *user-configurable* per Freshservice instance. Always call
        get_fields before constructing filter queries to ensure correct values.
        Returns field definitions with names, types, labels, choice options for
        dropdowns (status, priority, source), and custom field configurations.

        **filter**: Filters tickets using structured queries. The query is
        automatically URL-encoded and wrapped in double quotes.

        Supported filter fields:
            agent_id, requester_id, status, priority, group_id, department_id,
            source, type, category, sub_category, item_category, created_at,
            updated_at, due_by, fr_due_by, workspace_id, and custom fields.

        Query syntax:
            - Logical operators: AND, OR
            - Format: "field:value AND field:value"
            - Relational: :> (>=), :< (<=) for dates/numbers
            - Dates: ISO 8601 (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
            - Null check: field:null

        Examples:
            "agent_id:120002355359 AND status:2"
            "priority:4 AND status:2"
            "created_at:>'2025-01-01'"
            "(status:2 OR status:3) AND priority:4"
            "agent_id:null AND status:2"

        Common errors:
            - Use 'agent_id' for filtering (NOT 'responder_id')
            - Status/priority values are instance-specific — call get_fields first
            - "invalid char in json text" → check query syntax and field names
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _READ_TICKET, "read_ticket", "manage_ticket")
        if err:
            return err
        return await _ticket_handler(
            action,
            ticket_id,
            subject=None,
            description=None,
            source=None,
            priority=None,
            status=None,
            email=None,
            requester_id=None,
            custom_fields=None,
            ticket_fields=None,
            query=query,
            page=page,
            per_page=per_page,
            workspace_id=workspace_id,
        )

    @mcp.tool()
    async def manage_ticket(
        action: str,
        ticket_id: Optional[int] = None,
        subject: Optional[str] = None,
        description: Optional[str] = None,
        source: Optional[Union[int, str]] = None,
        priority: Optional[Union[int, str]] = None,
        status: Optional[Union[int, str]] = None,
        email: Optional[str] = None,
        requester_id: Optional[int] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        ticket_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice tickets.

        Args:
            action: One of 'create', 'update', 'delete'
            ticket_id: Required for update, delete
            subject: Ticket subject (create)
            description: Ticket body — HTML (create)
            source: Source enum (1=Email,2=Portal,3=Phone…) (create)
            priority: 1=Low,2=Medium,3=High,4=Urgent (create/update)
            status: 2=Open,3=Pending,4=Resolved,5=Closed (create/update)
            email: Requester email (create — required if no requester_id)
            requester_id: Requester ID (create — required if no email)
            custom_fields: Key-value custom field pairs
            ticket_fields: Dict of fields to update (update action)
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _WRITE_TICKET, "manage_ticket", "read_ticket")
        if err:
            return err
        return await _ticket_handler(
            action,
            ticket_id,
            subject=subject,
            description=description,
            source=source,
            priority=priority,
            status=status,
            email=email,
            requester_id=requester_id,
            custom_fields=custom_fields,
            ticket_fields=ticket_fields,
            query=None,
            page=1,
            per_page=30,
            workspace_id=None,
        )

    # ------------------------------------------------------------------ #
    #  ticket_conversation — read/manage split                            #
    # ------------------------------------------------------------------ #
    _READ_TICKET_CONVERSATION = {"list"}
    _WRITE_TICKET_CONVERSATION = {"reply", "add_note", "update"}

    async def _ticket_conversation_handler(
        action: str,
        ticket_id: Optional[int],
        conversation_id: Optional[int],
        body: Optional[str],
        from_email: Optional[str],
        user_id: Optional[int],
        cc_emails: Optional[List[str]],
        bcc_emails: Optional[List[str]],
    ) -> Dict[str, Any]:
        if action == "list":
            if not ticket_id:
                return {"error": "ticket_id required"}
            try:
                resp = await api_get(f"tickets/{ticket_id}/conversations")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list conversations")

        if action == "reply":
            if not ticket_id or not body:
                return {"error": "ticket_id and body required for reply"}
            payload: Dict[str, Any] = {
                "body": body.strip(),
                "from_email": from_email or f"helpdesk@{FRESHSERVICE_DOMAIN}",
            }
            if user_id is not None:
                payload["user_id"] = user_id
            if cc_emails:
                payload["cc_emails"] = cc_emails
            if bcc_emails:
                payload["bcc_emails"] = bcc_emails
            try:
                resp = await api_post(f"tickets/{ticket_id}/reply", json=payload)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "reply to ticket")

        if action == "add_note":
            if not ticket_id or not body:
                return {"error": "ticket_id and body required for add_note"}
            try:
                resp = await api_post(f"tickets/{ticket_id}/notes", json={"body": body})
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "add ticket note")

        if action == "update":
            if not conversation_id or not body:
                return {"error": "conversation_id and body required for update"}
            try:
                resp = await api_put(f"conversations/{conversation_id}", json={"body": body})
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "update conversation")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_ticket_conversation(
        action: str,
        ticket_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read ticket conversations.

        Args:
            action: 'list'
            ticket_id: Required for list
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _READ_TICKET_CONVERSATION, "read_ticket_conversation", "manage_ticket_conversation")
        if err:
            return err
        return await _ticket_conversation_handler(
            action,
            ticket_id,
            conversation_id=None,
            body=None,
            from_email=None,
            user_id=None,
            cc_emails=None,
            bcc_emails=None,
        )

    @mcp.tool()
    async def manage_ticket_conversation(
        action: str,
        ticket_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        body: Optional[str] = None,
        from_email: Optional[str] = None,
        user_id: Optional[int] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Write actions on ticket conversations — replies, notes, updates.

        Args:
            action: 'reply', 'add_note', 'update'
            ticket_id: Required for reply, add_note
            conversation_id: Required for update
            body: HTML body content (reply, add_note, update)
            from_email: Sender email (reply)
            user_id: Agent user ID (reply)
            cc_emails: CC email list (reply)
            bcc_emails: BCC email list (reply)
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _WRITE_TICKET_CONVERSATION, "manage_ticket_conversation", "read_ticket_conversation")
        if err:
            return err
        return await _ticket_conversation_handler(
            action,
            ticket_id,
            conversation_id=conversation_id,
            body=body,
            from_email=from_email,
            user_id=user_id,
            cc_emails=cc_emails,
            bcc_emails=bcc_emails,
        )

    # ------------------------------------------------------------------ #
    #  service_catalog — read/manage split                                #
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
                # verify it's a service request first
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
            payload: Dict[str, Any] = {"email": email, "quantity": quantity}
            if requested_for:
                payload["requested_for"] = requested_for
            try:
                resp = await api_post(f"service_catalog/items/{display_id}/place_request", json=payload)
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

        Args:
            action: 'list_items', 'get_requested_items'
            ticket_id: Ticket ID (get_requested_items)
            page: Page number (list_items)
            per_page: Items per page (list_items)
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _READ_SERVICE_CATALOG, "read_service_catalog", "manage_service_catalog")
        if err:
            return err
        return await _service_catalog_handler(
            action,
            ticket_id,
            display_id=None,
            email=None,
            requested_for=None,
            quantity=1,
            page=page,
            per_page=per_page,
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

        Args:
            action: 'place_request'
            display_id: Service item display ID (place_request)
            email: Requester email (place_request)
            requested_for: Email of person for whom request is placed (place_request)
            quantity: Number of items (place_request, default 1)
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _WRITE_SERVICE_CATALOG, "manage_service_catalog", "read_service_catalog")
        if err:
            return err
        return await _service_catalog_handler(
            action,
            ticket_id=None,
            display_id=display_id,
            email=email,
            requested_for=requested_for,
            quantity=quantity,
            page=1,
            per_page=30,
        )

    # ------------------------------------------------------------------ #
    #  ticket_task — read/manage split                                    #
    # ------------------------------------------------------------------ #
    _READ_TICKET_TASK = {"view", "list"}
    _WRITE_TICKET_TASK = {"create", "update", "delete"}

    async def _ticket_task_handler(
        action: str,
        ticket_id: int,
        task_id: Optional[int],
        title: Optional[str],
        description: Optional[str],
        status: Optional[int],
        due_date: Optional[str],
        notify_before: Optional[int],
        group_id: Optional[int],
        agent_id: Optional[int],
    ) -> Dict[str, Any]:
        base = f"tickets/{ticket_id}/tasks"

        if action == "list":
            try:
                resp = await api_get(base)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list ticket tasks")

        if action == "create":
            if not title:
                return {"error": "title required for create"}
            data: Dict[str, Any] = {"title": title}
            for k, v in [("description", description), ("status", status),
                         ("due_date", due_date), ("notify_before", notify_before),
                         ("group_id", group_id), ("agent_id", agent_id)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_post(base, json=data)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "create ticket task")

        if action == "view":
            if not task_id:
                return {"error": "task_id required for view"}
            try:
                resp = await api_get(f"{base}/{task_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "view ticket task")

        if action == "update":
            if not task_id:
                return {"error": "task_id required for update"}
            data = {}
            for k, v in [("title", title), ("description", description),
                         ("status", status), ("due_date", due_date),
                         ("notify_before", notify_before), ("group_id", group_id),
                         ("agent_id", agent_id)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_put(f"{base}/{task_id}", json=data)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "update ticket task")

        if action == "delete":
            if not task_id:
                return {"error": "task_id required for delete"}
            try:
                resp = await api_delete(f"{base}/{task_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Task deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete ticket task")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_ticket_task(
        action: str,
        ticket_id: int,
        task_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read tasks on a ticket.

        Args:
            action: 'view', 'list'
            ticket_id: The ticket ID (REQUIRED)
            task_id: Required for view
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _READ_TICKET_TASK, "read_ticket_task", "manage_ticket_task")
        if err:
            return err
        return await _ticket_task_handler(
            action,
            ticket_id,
            task_id=task_id,
            title=None,
            description=None,
            status=None,
            due_date=None,
            notify_before=None,
            group_id=None,
            agent_id=None,
        )

    @mcp.tool()
    async def manage_ticket_task(
        action: str,
        ticket_id: int,
        task_id: Optional[int] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[int] = None,
        due_date: Optional[str] = None,
        notify_before: Optional[int] = None,
        group_id: Optional[int] = None,
        agent_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Write actions on tasks of a ticket.

        Args:
            action: 'create', 'update', 'delete'
            ticket_id: The ticket ID (REQUIRED)
            task_id: Required for update, delete
            title: Task title (create)
            description: Task description (create/update)
            status: 1=Open, 2=In Progress, 3=Completed (create/update)
            due_date: ISO datetime (create/update)
            notify_before: Seconds to notify before due date (create/update)
            group_id: Group ID (create/update)
            agent_id: Agent ID (create/update)
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _WRITE_TICKET_TASK, "manage_ticket_task", "read_ticket_task")
        if err:
            return err
        return await _ticket_task_handler(
            action,
            ticket_id,
            task_id=task_id,
            title=title,
            description=description,
            status=status,
            due_date=due_date,
            notify_before=notify_before,
            group_id=group_id,
            agent_id=agent_id,
        )

    # ------------------------------------------------------------------ #
    #  ticket_time_entry — read/manage split                              #
    # ------------------------------------------------------------------ #
    _READ_TICKET_TIME_ENTRY = {"view", "list"}
    _WRITE_TICKET_TIME_ENTRY = {"create", "update", "delete"}

    async def _ticket_time_entry_handler(
        action: str,
        ticket_id: int,
        time_entry_id: Optional[int],
        te_agent_id: Optional[int],
        time_spent: Optional[str],
        note: Optional[str],
        executed_at: Optional[str],
        billable: Optional[bool],
        timer_running: Optional[bool],
        task_id: Optional[int],
    ) -> Dict[str, Any]:
        base = f"tickets/{ticket_id}/time_entries"

        if action == "list":
            try:
                resp = await api_get(base)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list time entries")

        if action == "create":
            if not te_agent_id or not time_spent:
                return {"error": "te_agent_id and time_spent are required for create"}
            data: Dict[str, Any] = {"agent_id": te_agent_id, "time_spent": time_spent}
            for k, v in [("note", note), ("executed_at", executed_at), ("task_id", task_id)]:
                if v is not None:
                    data[k] = v
            if billable is not None:
                data["billable"] = billable
            if timer_running is not None:
                data["timer_running"] = timer_running
            try:
                resp = await api_post(base, json=data)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "create time entry")

        if action == "view":
            if not time_entry_id:
                return {"error": "time_entry_id required for view"}
            try:
                resp = await api_get(f"{base}/{time_entry_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "view time entry")

        if action == "update":
            if not time_entry_id:
                return {"error": "time_entry_id required for update"}
            data = {}
            for k, v in [("time_spent", time_spent), ("note", note), ("executed_at", executed_at)]:
                if v is not None:
                    data[k] = v
            if billable is not None:
                data["billable"] = billable
            if timer_running is not None:
                data["timer_running"] = timer_running
            try:
                resp = await api_put(f"{base}/{time_entry_id}", json=data)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "update time entry")

        if action == "delete":
            if not time_entry_id:
                return {"error": "time_entry_id required for delete"}
            try:
                resp = await api_delete(f"{base}/{time_entry_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Time entry deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete time entry")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_ticket_time_entry(
        action: str,
        ticket_id: int,
        time_entry_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read time entries on a ticket.

        Args:
            action: 'view', 'list'
            ticket_id: The ticket ID (REQUIRED)
            time_entry_id: Required for view
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _READ_TICKET_TIME_ENTRY, "read_ticket_time_entry", "manage_ticket_time_entry")
        if err:
            return err
        return await _ticket_time_entry_handler(
            action,
            ticket_id,
            time_entry_id=time_entry_id,
            te_agent_id=None,
            time_spent=None,
            note=None,
            executed_at=None,
            billable=None,
            timer_running=None,
            task_id=None,
        )

    @mcp.tool()
    async def manage_ticket_time_entry(
        action: str,
        ticket_id: int,
        time_entry_id: Optional[int] = None,
        te_agent_id: Optional[int] = None,
        time_spent: Optional[str] = None,
        note: Optional[str] = None,
        executed_at: Optional[str] = None,
        billable: Optional[bool] = None,
        timer_running: Optional[bool] = None,
        task_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Write actions on time entries of a ticket.

        Args:
            action: 'create', 'update', 'delete'
            ticket_id: The ticket ID (REQUIRED)
            time_entry_id: Required for update, delete
            te_agent_id: Agent ID who did the work (create - REQUIRED)
            time_spent: Format "hh:mm" (create - REQUIRED)
            note: Work description (create/update)
            executed_at: ISO datetime when work was done (create/update)
            billable: Whether this time is billable (create/update)
            timer_running: Whether a timer is running (create/update)
            task_id: Associated task ID (create)
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _WRITE_TICKET_TIME_ENTRY, "manage_ticket_time_entry", "read_ticket_time_entry")
        if err:
            return err
        return await _ticket_time_entry_handler(
            action,
            ticket_id,
            time_entry_id=time_entry_id,
            te_agent_id=te_agent_id,
            time_spent=time_spent,
            note=note,
            executed_at=executed_at,
            billable=billable,
            timer_running=timer_running,
            task_id=task_id,
        )

    # ------------------------------------------------------------------ #
    #  ticket_approval — read/manage split                                #
    # ------------------------------------------------------------------ #
    _READ_TICKET_APPROVAL = {"list", "view"}
    _WRITE_TICKET_APPROVAL = {"create", "approve", "reject", "remind"}

    async def _ticket_approval_handler(
        action: str,
        ticket_id: int,
        approval_id: Optional[int],
        approver_id: Optional[int],
        approval_type: Optional[int],
        email_content: Optional[str],
    ) -> Dict[str, Any]:
        base = f"tickets/{ticket_id}/approvals"

        if action == "list":
            try:
                resp = await api_get(base)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list ticket approvals")

        if action == "create":
            if not approver_id:
                return {"error": "approver_id required for create"}
            data: Dict[str, Any] = {"approver_id": approver_id}
            if approval_type is not None:
                data["approval_type"] = approval_type
            if email_content:
                data["email_content"] = email_content
            try:
                resp = await api_post(base, json=data)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "create ticket approval")

        if action == "view":
            if not approval_id:
                return {"error": "approval_id required for view"}
            try:
                resp = await api_get(f"{base}/{approval_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "view ticket approval")

        if action == "approve":
            if not approval_id:
                return {"error": "approval_id required for approve"}
            try:
                resp = await api_put(f"{base}/{approval_id}/approve")
                resp.raise_for_status()
                return {"success": True, "message": "Approval approved"}
            except Exception as e:
                return handle_error(e, "approve ticket approval")

        if action == "reject":
            if not approval_id:
                return {"error": "approval_id required for reject"}
            try:
                resp = await api_put(f"{base}/{approval_id}/reject")
                resp.raise_for_status()
                return {"success": True, "message": "Approval rejected"}
            except Exception as e:
                return handle_error(e, "reject ticket approval")

        if action == "remind":
            if not approval_id:
                return {"error": "approval_id required for remind"}
            try:
                resp = await api_put(f"{base}/{approval_id}/remind")
                resp.raise_for_status()
                return {"success": True, "message": "Reminder sent"}
            except Exception as e:
                return handle_error(e, "send approval reminder")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_ticket_approval(
        action: str,
        ticket_id: int,
        approval_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read approvals on a ticket.

        Args:
            action: 'list', 'view'
            ticket_id: The ticket ID (REQUIRED)
            approval_id: Required for view
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _READ_TICKET_APPROVAL, "read_ticket_approval", "manage_ticket_approval")
        if err:
            return err
        return await _ticket_approval_handler(
            action,
            ticket_id,
            approval_id=approval_id,
            approver_id=None,
            approval_type=None,
            email_content=None,
        )

    @mcp.tool()
    async def manage_ticket_approval(
        action: str,
        ticket_id: int,
        approval_id: Optional[int] = None,
        approver_id: Optional[int] = None,
        approval_type: Optional[int] = None,
        email_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write actions on approvals of a ticket.

        Args:
            action: 'create', 'approve', 'reject', 'remind'
            ticket_id: The ticket ID (REQUIRED)
            approval_id: Required for approve, reject, remind
            approver_id: Approver user ID (create - REQUIRED)
            approval_type: 1=Everyone, 2=Anyone, 3=Majority, 4=First Responder (create)
            email_content: Custom email content for approval request (create)
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _WRITE_TICKET_APPROVAL, "manage_ticket_approval", "read_ticket_approval")
        if err:
            return err
        return await _ticket_approval_handler(
            action,
            ticket_id,
            approval_id=approval_id,
            approver_id=approver_id,
            approval_type=approval_type,
            email_content=email_content,
        )
