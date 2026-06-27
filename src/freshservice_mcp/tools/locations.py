"""Freshservice MCP — Location tools.

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  - read_location / manage_location — list/get/filter vs create/update/delete
"""
from typing import Any, Dict, Optional

from ..http_client import api_delete, api_get, api_post, api_put, handle_error
from ._split import reject_unless_in


def register_locations_tools(mcp) -> None:
    """Register location tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  location — read/manage split                                       #
    # ------------------------------------------------------------------ #
    _READ_LOCATION = {"list", "get", "filter"}
    _WRITE_LOCATION = {"create", "update", "delete"}

    async def _location_handler(
        action: str,
        location_id: Optional[int],
        name: Optional[str],
        line1: Optional[str],
        line2: Optional[str],
        city: Optional[str],
        state: Optional[str],
        country: Optional[str],
        zipcode: Optional[str],
        contact_name: Optional[str],
        email: Optional[str],
        phone: Optional[str],
        parent_location_id: Optional[int],
        query: Optional[str],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
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

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_location(
        action: str,
        location_id: Optional[int] = None,
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice locations.

        Actions: list, get, filter

        Required per action:
          get: location_id
          filter: query (e.g. "name:'New York'")

        Optional: page, per_page.
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _READ_LOCATION, "read_location", "manage_location")
        if err:
            return err
        return await _location_handler(
            action, location_id, None, None, None, None, None, None, None,
            None, None, None, None, query, page, per_page,
        )

    @mcp.tool()
    async def manage_location(
        action: str,
        location_id: Optional[int] = None,
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
    ) -> Dict[str, Any]:
        """Write actions on Freshservice locations.

        Actions: create, update, delete

        Required per action:
          create: name
          update / delete: location_id

        Optional: line1, line2, city, state, country, zipcode (address);
        contact_name, email, phone, parent_location_id.
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _WRITE_LOCATION, "manage_location", "read_location")
        if err:
            return err
        return await _location_handler(
            action, location_id, name, line1, line2, city, state, country, zipcode,
            contact_name, email, phone, parent_location_id, query=None,
            page=1, per_page=30,
        )
