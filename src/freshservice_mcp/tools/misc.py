"""Freshservice MCP — Miscellaneous tools (consolidated).

Exposes 9 tools:
  - manage_canned_response    — list + get (responses & folders)
  - manage_workspace          — list + get
  - manage_agent_role         — list + get (read-only)
  - manage_business_hour      — list + get (read-only)
  - manage_sla_policy         — list + get (read-only)
  - manage_alert              — list + get + delete
  - manage_audit_log          — export
  - manage_onboarding_request — list + get + create + get_tickets + get_fields
  - manage_offboarding_request — list + get + create + get_fields
"""
from typing import Any, Dict, List, Optional

from ..http_client import (
    api_delete,
    api_get,
    api_post,
    handle_error,
    parse_link_header,
)


def register_misc_tools(mcp) -> None:  # noqa: C901
    """Register miscellaneous tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  manage_canned_response                                             #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_canned_response(
        action: str,
        response_id: Optional[int] = None,
        folder_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Manage canned responses.

        Args:
            action: 'list', 'get', 'list_folders', 'get_folder'
            response_id: Required for get
            folder_id: Required for get_folder
        """
        action = action.lower().strip()

        if action == "list":
            try:
                resp = await api_get("canned_responses")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list canned responses")

        if action == "get":
            if not response_id:
                return {"error": "response_id required for get"}
            try:
                resp = await api_get(f"canned_responses/{response_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get canned response")

        if action == "list_folders":
            try:
                resp = await api_get("canned_response_folders")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list canned response folders")

        if action == "get_folder":
            if not folder_id:
                return {"error": "folder_id required for get_folder"}
            try:
                resp = await api_get(f"canned_response_folders/{folder_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get canned response folder")

        return {"error": f"Unknown action '{action}'. Valid: list, get, list_folders, get_folder"}

    # ------------------------------------------------------------------ #
    #  manage_workspace                                                   #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_workspace(
        action: str,
        workspace_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Manage workspaces.

        Args:
            action: 'list', 'get'
            workspace_id: Required for get
        """
        action = action.lower().strip()

        if action == "list":
            try:
                resp = await api_get("workspaces")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list workspaces")

        if action == "get":
            if not workspace_id:
                return {"error": "workspace_id required for get"}
            try:
                resp = await api_get(f"workspaces/{workspace_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get workspace")

        return {"error": f"Unknown action '{action}'. Valid: list, get"}

    # ------------------------------------------------------------------ #
    #  manage_agent_role                                                  #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_agent_role(
        action: str,
        role_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Manage Freshservice agent roles (read-only).

        Args:
            action: 'list', 'get'
            role_id: Required for get
        """
        action = action.lower().strip()

        if action == "list":
            try:
                resp = await api_get("roles")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list roles")

        if action == "get":
            if not role_id:
                return {"error": "role_id required for get"}
            try:
                resp = await api_get(f"roles/{role_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get role")

        return {"error": f"Unknown action '{action}'. Valid: list, get"}

    # ------------------------------------------------------------------ #
    #  manage_business_hour                                               #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_business_hour(
        action: str,
        business_hour_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Manage Freshservice business hours configurations (read-only).

        Args:
            action: 'list', 'get'
            business_hour_id: Required for get
        """
        action = action.lower().strip()

        if action == "list":
            try:
                resp = await api_get("business_hours")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list business hours")

        if action == "get":
            if not business_hour_id:
                return {"error": "business_hour_id required for get"}
            try:
                resp = await api_get(f"business_hours/{business_hour_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get business hours")

        return {"error": f"Unknown action '{action}'. Valid: list, get"}

    # ------------------------------------------------------------------ #
    #  manage_sla_policy                                                  #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_sla_policy(
        action: str,
        sla_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Manage Freshservice SLA policies (read-only).

        Args:
            action: 'list', 'get'
            sla_id: Required for get
        """
        action = action.lower().strip()

        if action == "list":
            try:
                resp = await api_get("sla_policies")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list SLA policies")

        if action == "get":
            if not sla_id:
                return {"error": "sla_id required for get"}
            try:
                resp = await api_get(f"sla_policies/{sla_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get SLA policy")

        return {"error": f"Unknown action '{action}'. Valid: list, get"}

    # ------------------------------------------------------------------ #
    #  manage_alert                                                       #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_alert(
        action: str,
        alert_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice alerts.

        Args:
            action: 'list', 'get', 'delete'
            alert_id: Required for get, delete
            page: Page number (list)
            per_page: Items per page 1-100 (list)
        """
        action = action.lower().strip()

        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            try:
                resp = await api_get("alerts", params=params)
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "alerts": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list alerts")

        if action == "get":
            if not alert_id:
                return {"error": "alert_id required for get"}
            try:
                resp = await api_get(f"alerts/{alert_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get alert")

        if action == "delete":
            if not alert_id:
                return {"error": "alert_id required for delete"}
            try:
                resp = await api_delete(f"alerts/{alert_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Alert deleted"}
                return {"error": f"Unexpected status {resp.status_code}"}
            except Exception as e:
                return handle_error(e, "delete alert")

        return {"error": f"Unknown action '{action}'. Valid: list, get, delete"}

    # ------------------------------------------------------------------ #
    #  manage_audit_log                                                   #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_audit_log(
        action: str,
        since: Optional[str] = None,
        before: Optional[str] = None,
        audit_type: Optional[str] = None,
        actor: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Export Freshservice audit logs.

        Args:
            action: 'export'
            since: ISO datetime — start of export window (REQUIRED for export)
            before: ISO datetime — end of export window (REQUIRED for export)
            audit_type: Filter by audit type string (optional)
            actor: Filter by actor, e.g. {"id": 123, "type": "user"} (optional)
        """
        action = action.lower().strip()

        if action == "export":
            if not since or not before:
                return {"error": "since and before are required for export"}
            data: Dict[str, Any] = {"since": since, "before": before}
            if audit_type:
                data["type"] = audit_type
            if actor:
                data["actor"] = actor
            try:
                resp = await api_post("audit_log/export", json=data)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "export audit log")

        return {"error": f"Unknown action '{action}'. Valid: export"}

    # ------------------------------------------------------------------ #
    #  manage_onboarding_request                                          #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_onboarding_request(
        action: str,
        onboarding_request_id: Optional[int] = None,
        fields: Optional[Dict[str, Any]] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice onboarding requests.

        Args:
            action: 'list', 'get', 'create', 'get_tickets', 'get_fields'
            onboarding_request_id: Required for get, get_tickets
            fields: Request field data dict (create)
            page: Page number (list)
            per_page: Items per page 1-100 (list)
        """
        action = action.lower().strip()

        if action == "get_fields":
            try:
                resp = await api_get("onboarding_requests/form")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get onboarding request fields")

        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            try:
                resp = await api_get("onboarding_requests", params=params)
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "onboarding_requests": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list onboarding requests")

        if action == "get":
            if not onboarding_request_id:
                return {"error": "onboarding_request_id required for get"}
            try:
                resp = await api_get(f"onboarding_requests/{onboarding_request_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get onboarding request")

        if action == "create":
            if not fields:
                return {"error": "fields dict required for create"}
            try:
                resp = await api_post("onboarding_requests", json=fields)
                resp.raise_for_status()
                return {"success": True, "onboarding_request": resp.json()}
            except Exception as e:
                return handle_error(e, "create onboarding request")

        if action == "get_tickets":
            if not onboarding_request_id:
                return {"error": "onboarding_request_id required for get_tickets"}
            try:
                resp = await api_get(f"onboarding_requests/{onboarding_request_id}/tickets")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get onboarding request tickets")

        return {"error": f"Unknown action '{action}'. Valid: list, get, create, get_tickets, get_fields"}

    # ------------------------------------------------------------------ #
    #  manage_offboarding_request                                         #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_offboarding_request(
        action: str,
        offboarding_request_id: Optional[int] = None,
        fields: Optional[Dict[str, Any]] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice offboarding requests.

        Args:
            action: 'list', 'get', 'create', 'get_fields'
            offboarding_request_id: Required for get
            fields: Request field data dict (create)
            page: Page number (list)
            per_page: Items per page 1-100 (list)
        """
        action = action.lower().strip()

        if action == "get_fields":
            try:
                resp = await api_get("offboarding_requests/form")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get offboarding request fields")

        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            try:
                resp = await api_get("offboarding_requests", params=params)
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "offboarding_requests": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list offboarding requests")

        if action == "get":
            if not offboarding_request_id:
                return {"error": "offboarding_request_id required for get"}
            try:
                resp = await api_get(f"offboarding_requests/{offboarding_request_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get offboarding request")

        if action == "create":
            if not fields:
                return {"error": "fields dict required for create"}
            try:
                resp = await api_post("offboarding_requests", json=fields)
                resp.raise_for_status()
                return {"success": True, "offboarding_request": resp.json()}
            except Exception as e:
                return handle_error(e, "create offboarding request")

        return {"error": f"Unknown action '{action}'. Valid: list, get, create, get_fields"}
