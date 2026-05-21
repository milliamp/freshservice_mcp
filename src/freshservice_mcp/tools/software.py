"""Freshservice MCP — Software tools (consolidated).

Exposes 1 tool:
  • manage_software — CRUD + list + list_licenses
"""
from typing import Any, Dict, List, Optional

from ..http_client import api_get, api_post, api_put, handle_error, parse_link_header


def register_software_tools(mcp) -> None:
    """Register software-related tools on *mcp*."""

    @mcp.tool()
    async def manage_software(
        action: str,
        software_id: Optional[int] = None,
        # create / update fields
        name: Optional[str] = None,
        description: Optional[str] = None,
        application_type: Optional[str] = None,
        status: Optional[str] = None,
        publisher_id: Optional[int] = None,
        managed_by_id: Optional[int] = None,
        notes: Optional[str] = None,
        category: Optional[str] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        # list / list_licenses
        workspace_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Unified software operations.

        Args:
            action: One of 'create', 'update', 'get', 'list', 'list_licenses'
            software_id: Software/application ID (get, update)
            name: Software name (create — MANDATORY)
            description: Software description
            application_type: Type of application
            status: Software status
            publisher_id: Publisher ID
            managed_by_id: ID of the agent managing this software
            notes: Additional notes
            category: Software category
            sources: List of source dicts
            custom_fields: Custom field key-value pairs
            workspace_id: Workspace filter (list, list_licenses)
            page: Page number (list, list_licenses)
            per_page: Items per page 1-100 (list, list_licenses)
        """
        action = action.lower().strip()

        # ---------- list ----------
        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            if workspace_id is not None:
                params["workspace_id"] = workspace_id
            try:
                resp = await api_get("applications", params=params)
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "software": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list software")

        # ---------- get ----------
        if action == "get":
            if not software_id:
                return {"error": "software_id required for get"}
            try:
                resp = await api_get(f"applications/{software_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get software")

        # ---------- create ----------
        if action == "create":
            if not name:
                return {"error": "name is required for create"}
            data: Dict[str, Any] = {"name": name}
            for k, v in [
                ("description", description),
                ("application_type", application_type),
                ("status", status),
                ("publisher_id", publisher_id),
                ("managed_by_id", managed_by_id),
                ("notes", notes),
                ("category", category),
                ("sources", sources),
                ("custom_fields", custom_fields),
            ]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_post("applications", json=data)
                resp.raise_for_status()
                return {"success": True, "software": resp.json()}
            except Exception as e:
                return handle_error(e, "create software")

        # ---------- update ----------
        if action == "update":
            if not software_id:
                return {"error": "software_id required for update"}
            data: Dict[str, Any] = {}
            for k, v in [
                ("name", name),
                ("description", description),
                ("application_type", application_type),
                ("status", status),
                ("publisher_id", publisher_id),
                ("managed_by_id", managed_by_id),
                ("notes", notes),
                ("category", category),
                ("sources", sources),
                ("custom_fields", custom_fields),
            ]:
                if v is not None:
                    data[k] = v
            if not data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"applications/{software_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "software": resp.json()}
            except Exception as e:
                return handle_error(e, "update software")

        # ---------- list_licenses ----------
        if action == "list_licenses":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            if workspace_id is not None:
                params["workspace_id"] = workspace_id
            try:
                resp = await api_get("software_installations", params=params)
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "licenses": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list software licenses")

        return {"error": f"Unknown action '{action}'. Valid: create, update, get, list, list_licenses"}
