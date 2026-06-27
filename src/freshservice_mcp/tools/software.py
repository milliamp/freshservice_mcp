"""Freshservice MCP — Software tools (consolidated).

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  - read_software / manage_software — list/get/list_licenses vs create/update
"""
from typing import Any, Dict, List, Optional

from ..http_client import api_get, api_post, api_put, handle_error, parse_link_header
from ._split import reject_unless_in


def register_software_tools(mcp) -> None:
    """Register software-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  software — read/manage split                                       #
    # ------------------------------------------------------------------ #
    _READ_SOFTWARE = {"list", "get", "list_licenses"}
    _WRITE_SOFTWARE = {"create", "update"}

    async def _software_handler(
        action: str,
        software_id: Optional[int],
        name: Optional[str],
        description: Optional[str],
        application_type: Optional[str],
        status: Optional[str],
        publisher_id: Optional[int],
        managed_by_id: Optional[int],
        notes: Optional[str],
        category: Optional[str],
        sources: Optional[List[Dict[str, Any]]],
        custom_fields: Optional[Dict[str, Any]],
        workspace_id: Optional[int],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
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
            params = {"page": page, "per_page": per_page}
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

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_software(
        action: str,
        software_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice software / applications.

        Actions: list, get, list_licenses

        Required per action:
          get: software_id

        Optional: workspace_id, page, per_page (list / list_licenses).
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _READ_SOFTWARE, "read_software", "manage_software")
        if err:
            return err
        return await _software_handler(
            action, software_id, None, None, None, None, None, None, None, None,
            None, None, workspace_id, page, per_page,
        )

    @mcp.tool()
    async def manage_software(
        action: str,
        software_id: Optional[int] = None,
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
    ) -> Dict[str, Any]:
        """Write actions on Freshservice software / applications.

        Actions: create, update

        Required per action:
          create: name
          update: software_id

        Optional: description, application_type, status, publisher_id,
        managed_by_id, notes, category, sources, custom_fields.
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _WRITE_SOFTWARE, "manage_software", "read_software")
        if err:
            return err
        return await _software_handler(
            action, software_id, name, description, application_type, status,
            publisher_id, managed_by_id, notes, category, sources, custom_fields,
            workspace_id=None, page=1, per_page=30,
        )
