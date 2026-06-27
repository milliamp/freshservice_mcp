"""Freshservice MCP — Miscellaneous tools (consolidated).

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently. Tools that have no write
actions are exposed only as read_*.

Tools:
  - read_canned_response       — list + get (responses & folders)
  - read_workspace             — list + get
  - read_agent_role            — list + get
  - read_business_hour         — list + get
  - read_sla_policy            — list + get
  - read_alert  / manage_alert — list/get vs delete
  - read_audit_log             — export
  - read_onboarding_request /
    manage_onboarding_request  — list/get/get_tickets/get_fields vs create
  - read_offboarding_request /
    manage_offboarding_request — list/get/get_fields vs create
"""
from typing import Any, Dict, Optional

from ..http_client import (
    api_delete,
    api_get,
    api_post,
    handle_error,
    parse_link_header,
)
from ._split import normalize_action, reject_unless_in


def register_misc_tools(mcp) -> None:  # noqa: C901
    """Register miscellaneous tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  canned_response — read only                                        #
    # ------------------------------------------------------------------ #
    _READ_CANNED = {"list", "get", "list_folders", "get_folder"}

    @mcp.tool()
    async def read_canned_response(
        action: str,
        response_id: Optional[int] = None,
        folder_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read canned responses and folders.

        Args:
            action: 'list', 'get', 'list_folders', 'get_folder'
            response_id: Required for get
            folder_id: Required for get_folder
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_CANNED, "read_canned_response", "(no write counterpart)")
        if err:
            return err

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

        return {"error": "unreachable"}

    # ------------------------------------------------------------------ #
    #  workspace — read only                                              #
    # ------------------------------------------------------------------ #
    _READ_WORKSPACE = {"list", "get"}

    @mcp.tool()
    async def read_workspace(
        action: str,
        workspace_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read workspaces.

        Args:
            action: 'list', 'get'
            workspace_id: Required for get
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_WORKSPACE, "read_workspace", "(no write counterpart)")
        if err:
            return err

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

        return {"error": "unreachable"}

    # ------------------------------------------------------------------ #
    #  agent_role — read only                                             #
    # ------------------------------------------------------------------ #
    _READ_AGENT_ROLE = {"list", "get"}

    @mcp.tool()
    async def read_agent_role(
        action: str,
        role_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read Freshservice agent roles.

        Args:
            action: 'list', 'get'
            role_id: Required for get
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_AGENT_ROLE, "read_agent_role", "(no write counterpart)")
        if err:
            return err

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

        return {"error": "unreachable"}

    # ------------------------------------------------------------------ #
    #  business_hour — read only                                          #
    # ------------------------------------------------------------------ #
    _READ_BUSINESS_HOUR = {"list", "get"}

    @mcp.tool()
    async def read_business_hour(
        action: str,
        business_hour_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read Freshservice business hours configurations.

        Args:
            action: 'list', 'get'
            business_hour_id: Required for get
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_BUSINESS_HOUR, "read_business_hour", "(no write counterpart)")
        if err:
            return err

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

        return {"error": "unreachable"}

    # ------------------------------------------------------------------ #
    #  sla_policy — read only                                             #
    # ------------------------------------------------------------------ #
    _READ_SLA_POLICY = {"list", "get"}

    @mcp.tool()
    async def read_sla_policy(
        action: str,
        sla_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read Freshservice SLA policies.

        Args:
            action: 'list', 'get'
            sla_id: Required for get
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_SLA_POLICY, "read_sla_policy", "(no write counterpart)")
        if err:
            return err

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

        return {"error": "unreachable"}

    # ------------------------------------------------------------------ #
    #  alert — read/manage split                                          #
    # ------------------------------------------------------------------ #
    _READ_ALERT = {"list", "get"}
    _WRITE_ALERT = {"delete"}

    async def _alert_handler(
        action: str,
        alert_id: Optional[int],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
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

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_alert(
        action: str,
        alert_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice alerts.

        Args:
            action: 'list', 'get'
            alert_id: Required for get
            page: Page number (list)
            per_page: Items per page 1-100 (list)
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_ALERT, "read_alert", "manage_alert")
        if err:
            return err
        return await _alert_handler(action, alert_id, page, per_page)

    @mcp.tool()
    async def manage_alert(
        action: str,
        alert_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice alerts.

        Args:
            action: 'delete'
            alert_id: Required
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _WRITE_ALERT, "manage_alert", "read_alert")
        if err:
            return err
        return await _alert_handler(action, alert_id, page=1, per_page=30)

    # ------------------------------------------------------------------ #
    #  audit_log — read only (export is a read of historical data)        #
    # ------------------------------------------------------------------ #
    _READ_AUDIT = {"export"}

    @mcp.tool()
    async def read_audit_log(
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
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_AUDIT, "read_audit_log", "(no write counterpart)")
        if err:
            return err

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

        return {"error": "unreachable"}

    # ------------------------------------------------------------------ #
    #  onboarding_request — read/manage split                             #
    # ------------------------------------------------------------------ #
    _READ_ONBOARDING = {"list", "get", "get_tickets", "get_fields"}
    _WRITE_ONBOARDING = {"create"}

    async def _onboarding_handler(
        action: str,
        onboarding_request_id: Optional[int],
        fields: Optional[Dict[str, Any]],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
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

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_onboarding_request(
        action: str,
        onboarding_request_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice onboarding requests.

        Args:
            action: 'list', 'get', 'get_tickets', 'get_fields'
            onboarding_request_id: Required for get, get_tickets
            page: Page number (list)
            per_page: Items per page 1-100 (list)
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_ONBOARDING, "read_onboarding_request", "manage_onboarding_request")
        if err:
            return err
        return await _onboarding_handler(action, onboarding_request_id, None, page, per_page)

    @mcp.tool()
    async def manage_onboarding_request(
        action: str,
        fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice onboarding requests.

        Args:
            action: 'create'
            fields: Request field data dict (required for create)
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _WRITE_ONBOARDING, "manage_onboarding_request", "read_onboarding_request")
        if err:
            return err
        return await _onboarding_handler(action, None, fields, page=1, per_page=30)

    # ------------------------------------------------------------------ #
    #  offboarding_request — read/manage split                            #
    # ------------------------------------------------------------------ #
    _READ_OFFBOARDING = {"list", "get", "get_fields"}
    _WRITE_OFFBOARDING = {"create"}

    async def _offboarding_handler(
        action: str,
        offboarding_request_id: Optional[int],
        fields: Optional[Dict[str, Any]],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
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

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_offboarding_request(
        action: str,
        offboarding_request_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice offboarding requests.

        Args:
            action: 'list', 'get', 'get_fields'
            offboarding_request_id: Required for get
            page: Page number (list)
            per_page: Items per page 1-100 (list)
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_OFFBOARDING, "read_offboarding_request", "manage_offboarding_request")
        if err:
            return err
        return await _offboarding_handler(action, offboarding_request_id, None, page, per_page)

    @mcp.tool()
    async def manage_offboarding_request(
        action: str,
        fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice offboarding requests.

        Args:
            action: 'create'
            fields: Request field data dict (required for create)
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _WRITE_OFFBOARDING, "manage_offboarding_request", "read_offboarding_request")
        if err:
            return err
        return await _offboarding_handler(action, None, fields, page=1, per_page=30)
