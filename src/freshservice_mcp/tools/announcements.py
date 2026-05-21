"""Freshservice MCP — Announcements tools.

Exposes 1 tool:
  - manage_announcement — CRUD + list
"""
from typing import Any, Dict, List, Optional

from ..http_client import (
    api_delete,
    api_get,
    api_post,
    api_put,
    handle_error,
    parse_link_header,
)


def register_announcements_tools(mcp) -> None:
    """Register announcement-related tools on *mcp*."""

    @mcp.tool()
    async def manage_announcement(
        action: str,
        announcement_id: Optional[int] = None,
        title: Optional[str] = None,
        body_html: Optional[str] = None,
        visible_from: Optional[str] = None,
        visible_till: Optional[str] = None,
        visibility: Optional[str] = None,
        departments: Optional[List[int]] = None,
        groups: Optional[List[int]] = None,
        send_email: Optional[bool] = None,
        additional_emails: Optional[List[str]] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice announcements.

        Args:
            action: One of 'create', 'update', 'delete', 'get', 'list'
            announcement_id: Required for get, update, delete
            title: Announcement title (create - REQUIRED)
            body_html: Announcement body in HTML (create - REQUIRED)
            visible_from: ISO datetime when announcement becomes visible (create - REQUIRED)
            visible_till: ISO datetime when announcement expires
            visibility: One of 'everyone', 'agents_only', 'agents_and_groups'
                        (create - REQUIRED)
            departments: List of department IDs to target
            groups: List of group IDs to target
            send_email: Whether to send email notification (bool)
            additional_emails: List of additional email addresses to notify
            page: Page number (list)
            per_page: Items per page 1-100 (list)
        """
        action = action.lower().strip()

        # ---------- list ----------
        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            try:
                resp = await api_get("announcements", params=params)
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "announcements": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list announcements")

        # ---------- get ----------
        if action == "get":
            if not announcement_id:
                return {"error": "announcement_id required for get"}
            try:
                resp = await api_get(f"announcements/{announcement_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get announcement")

        # ---------- create ----------
        if action == "create":
            if not title or not body_html or not visible_from or not visibility:
                return {"error": "title, body_html, visible_from, and visibility are required for create"}
            data: Dict[str, Any] = {
                "title": title,
                "body_html": body_html,
                "visible_from": visible_from,
                "visibility": visibility,
            }
            if visible_till:
                data["visible_till"] = visible_till
            if departments:
                data["departments"] = departments
            if groups:
                data["groups"] = groups
            if send_email is not None:
                data["send_email"] = send_email
            if additional_emails:
                data["additional_emails"] = additional_emails
            try:
                resp = await api_post("announcements", json=data)
                resp.raise_for_status()
                return {"success": True, "announcement": resp.json()}
            except Exception as e:
                return handle_error(e, "create announcement")

        # ---------- update ----------
        if action == "update":
            if not announcement_id:
                return {"error": "announcement_id required for update"}
            update_data: Dict[str, Any] = {}
            for k, v in [("title", title), ("body_html", body_html),
                         ("visible_from", visible_from), ("visible_till", visible_till),
                         ("visibility", visibility)]:
                if v is not None:
                    update_data[k] = v
            if departments is not None:
                update_data["departments"] = departments
            if groups is not None:
                update_data["groups"] = groups
            if send_email is not None:
                update_data["send_email"] = send_email
            if additional_emails is not None:
                update_data["additional_emails"] = additional_emails
            if not update_data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"announcements/{announcement_id}", json=update_data)
                resp.raise_for_status()
                return {"success": True, "announcement": resp.json()}
            except Exception as e:
                return handle_error(e, "update announcement")

        # ---------- delete ----------
        if action == "delete":
            if not announcement_id:
                return {"error": "announcement_id required for delete"}
            try:
                resp = await api_delete(f"announcements/{announcement_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Announcement deleted"}
                return {"error": f"Unexpected status {resp.status_code}"}
            except Exception as e:
                return handle_error(e, "delete announcement")

        return {"error": f"Unknown action '{action}'. Valid: create, update, delete, get, list"}
