"""Freshservice MCP — Department tools.

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  - read_department / manage_department — list/get/filter/get_fields vs
                                          create/update/delete
"""
from typing import Any, Dict, List, Optional

from ..http_client import api_delete, api_get, api_post, api_put, handle_error
from ._split import normalize_action, reject_unless_in


def register_department_tools(mcp) -> None:
    """Register department tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  department — read/manage split                                     #
    # ------------------------------------------------------------------ #
    _READ_DEPARTMENT = {"list", "get", "filter", "get_fields"}
    _WRITE_DEPARTMENT = {"create", "update", "delete"}

    async def _department_handler(
        action: str,
        department_id: Optional[int],
        name: Optional[str],
        description: Optional[str],
        head_user_id: Optional[int],
        prime_user_id: Optional[int],
        domains: Optional[List[str]],
        custom_fields: Optional[Dict[str, Any]],
        query: Optional[str],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        if action == "list":
            try:
                resp = await api_get("departments", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list departments")

        if action == "get":
            if not department_id:
                return {"error": "department_id required for get"}
            try:
                resp = await api_get(f"departments/{department_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get department")

        if action == "create":
            if not name:
                return {"error": "name required for create"}
            data: Dict[str, Any] = {"name": name}
            if description:
                data["description"] = description
            if head_user_id:
                data["head_user_id"] = head_user_id
            if prime_user_id:
                data["prime_user_id"] = prime_user_id
            if domains:
                data["domains"] = domains
            if custom_fields:
                data["custom_fields"] = custom_fields
            try:
                resp = await api_post("departments", json=data)
                resp.raise_for_status()
                return {"success": True, "department": resp.json()}
            except Exception as e:
                return handle_error(e, "create department")

        if action == "update":
            if not department_id:
                return {"error": "department_id required for update"}
            data = {}
            for k, v in [("name", name), ("description", description),
                         ("head_user_id", head_user_id), ("prime_user_id", prime_user_id),
                         ("domains", domains), ("custom_fields", custom_fields)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_put(f"departments/{department_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "department": resp.json()}
            except Exception as e:
                return handle_error(e, "update department")

        if action == "delete":
            if not department_id:
                return {"error": "department_id required for delete"}
            try:
                resp = await api_delete(f"departments/{department_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": f"Department {department_id} deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete department")

        if action == "filter":
            if not query:
                return {"error": "query required for filter (e.g. \"name:'Engineering'\")"}
            try:
                resp = await api_get(
                    "departments",
                    params={"query": f'"{query}"', "page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "filter departments")

        if action == "get_fields":
            try:
                resp = await api_get("department_fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get department fields")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_department(
        action: str,
        department_id: Optional[int] = None,
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice departments.

        Actions: list, get, filter, get_fields

        Required per action:
          get: department_id
          filter: query (e.g. "name:'Engineering'")

        Optional: page, per_page.
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_DEPARTMENT, "read_department", "manage_department")
        if err:
            return err
        return await _department_handler(
            action, department_id, None, None, None, None, None, None,
            query, page, per_page,
        )

    @mcp.tool()
    async def manage_department(
        action: str,
        department_id: Optional[int] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        head_user_id: Optional[int] = None,
        prime_user_id: Optional[int] = None,
        domains: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice departments.

        Actions: create, update, delete

        Required per action:
          create: name
          update / delete: department_id

        Optional: description, head_user_id, prime_user_id, domains
        (email domains list), custom_fields.
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _WRITE_DEPARTMENT, "manage_department", "read_department")
        if err:
            return err
        return await _department_handler(
            action, department_id, name, description, head_user_id, prime_user_id,
            domains, custom_fields, query=None, page=1, per_page=30,
        )
