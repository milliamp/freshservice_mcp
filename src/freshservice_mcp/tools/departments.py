"""Freshservice MCP — Department & Location tools.

Exposes 2 tools:
  • manage_department — CRUD + list + filter departments
  • manage_location  — CRUD + list + filter locations
"""
from typing import Any, Dict, List, Optional

from ..http_client import api_delete, api_get, api_post, api_put, handle_error


def register_department_tools(mcp) -> None:
    """Register department and location tools on *mcp*."""

    @mcp.tool()
    async def manage_department(
        action: str,
        department_id: Optional[int] = None,
        # creation / update fields
        name: Optional[str] = None,
        description: Optional[str] = None,
        head_user_id: Optional[int] = None,
        prime_user_id: Optional[int] = None,
        domains: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        # filter / pagination
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice departments.

        Args:
            action: One of 'list', 'get', 'create', 'update', 'delete',
                    'filter', 'get_fields'.
            department_id: Department ID (required for get/update/delete).
            name: Department name (required for create).
            description: Description text.
            head_user_id: User ID of department head.
            prime_user_id: User ID of department prime contact.
            domains: List of email domains for the department.
            custom_fields: Custom field values dict.
            query: Filter query string for 'filter' action
                   (e.g. "name:'Engineering'").
            page/per_page: Pagination.
        """
        action = action.lower().strip()

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

        return {
            "error": f"Unknown action '{action}'. Valid: list, get, create, update, delete, "
            "filter, get_fields"
        }

    @mcp.tool()
    async def manage_location(
        action: str,
        location_id: Optional[int] = None,
        # creation / update fields
        name: Optional[str] = None,
        line1: Optional[str] = None,
        line2: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        zipcode: Optional[str] = None,
        contact_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        parent_location_id: Optional[int] = None,
        # filter / pagination
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice locations.

        Args:
            action: One of 'list', 'get', 'create', 'update', 'delete', 'filter'.
            location_id: Location ID (required for get/update/delete).
            name: Location name (required for create).
            line1/line2/city/state/country/zipcode: Address fields.
            contact_name: Contact person name.
            email: Contact email.
            phone: Contact phone.
            parent_location_id: Parent location ID for hierarchical locations.
            query: Filter query for 'filter' action (e.g. "name:'New York'").
            page/per_page: Pagination.
        """
        action = action.lower().strip()

        if action == "list":
            try:
                resp = await api_get("locations", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list locations")

        if action == "get":
            if not location_id:
                return {"error": "location_id required for get"}
            try:
                resp = await api_get(f"locations/{location_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get location")

        if action == "create":
            if not name:
                return {"error": "name required for create"}
            data: Dict[str, Any] = {"name": name}
            addr: Dict[str, str] = {}
            for k, v in [("line1", line1), ("line2", line2), ("city", city),
                         ("state", state), ("country", country), ("zipcode", zipcode)]:
                if v:
                    addr[k] = v
            if addr:
                data["address"] = addr
            for k, v in [("contact_name", contact_name), ("email", email),
                         ("phone", phone), ("parent_location_id", parent_location_id)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_post("locations", json=data)
                resp.raise_for_status()
                return {"success": True, "location": resp.json()}
            except Exception as e:
                return handle_error(e, "create location")

        if action == "update":
            if not location_id:
                return {"error": "location_id required for update"}
            data = {}
            if name:
                data["name"] = name
            addr = {}
            for k, v in [("line1", line1), ("line2", line2), ("city", city),
                         ("state", state), ("country", country), ("zipcode", zipcode)]:
                if v is not None:
                    addr[k] = v
            if addr:
                data["address"] = addr
            for k, v in [("contact_name", contact_name), ("email", email),
                         ("phone", phone), ("parent_location_id", parent_location_id)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_put(f"locations/{location_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "location": resp.json()}
            except Exception as e:
                return handle_error(e, "update location")

        if action == "delete":
            if not location_id:
                return {"error": "location_id required for delete"}
            try:
                resp = await api_delete(f"locations/{location_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": f"Location {location_id} deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete location")

        if action == "filter":
            if not query:
                return {"error": "query required for filter (e.g. \"name:'New York'\")"}
            try:
                resp = await api_get(
                    "locations",
                    params={"query": f'"{query}"', "page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "filter locations")

        return {
            "error": f"Unknown action '{action}'. Valid: list, get, create, update, delete, filter"
        }
