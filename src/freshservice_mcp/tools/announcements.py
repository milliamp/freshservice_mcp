"""Freshservice MCP — Announcements tools.

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  - read_announcement / manage_announcement — list/get vs create/update/delete
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
from ._split import normalize_action, reject_unless_in


def register_announcements_tools(mcp) -> None:
    """Register announcement-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  announcement — read/manage split                                   #
    # ------------------------------------------------------------------ #
    _READ_ANNOUNCEMENT = {"list", "get"}
    _WRITE_ANNOUNCEMENT = {"create", "update", "delete"}

    async def _announcement_handler(
        action: str,
        announcement_id: Optional[int],
        title: Optional[str],
        body_html: Optional[str],
        visible_from: Optional[str],
        visible_till: Optional[str],
        visibility: Optional[str],
        departments: Optional[List[int]],
        groups: Optional[List[int]],
        send_email: Optional[bool],
        additional_emails: Optional[List[str]],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
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

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_announcement(
        action: str,
        announcement_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice announcements.

        Actions: list, get

        Required per action:
          get: announcement_id

        Optional: page, per_page (list).
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_ANNOUNCEMENT, "read_announcement", "manage_announcement")
        if err:
            return err
        return await _announcement_handler(
            action, announcement_id, None, None, None, None, None,
            None, None, None, None, page, per_page,
        )

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
    ) -> Dict[str, Any]:
        """Write actions on Freshservice announcements.

        Actions: create, update, delete

        Required per action:
          create: title, body_html, visible_from (ISO datetime), visibility
            (everyone | agents_only | agents_and_groups)
          update / delete: announcement_id

        Optional: visible_till (ISO datetime), departments (ids), groups (ids),
        send_email (bool), additional_emails.
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _WRITE_ANNOUNCEMENT, "manage_announcement", "read_announcement")
        if err:
            return err
        return await _announcement_handler(
            action, announcement_id, title, body_html, visible_from, visible_till,
            visibility, departments, groups, send_email, additional_emails,
            page=1, per_page=30,
        )
