"""Freshservice MCP — Requesters & Requester Groups tools (consolidated).

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  • read_requester       / manage_requester        — list/get/filter/get_fields vs create/update/add_to_group
  • read_requester_group / manage_requester_group  — list/get/list_members vs create/update
"""
from typing import Any, Dict, List, Optional

from ..http_client import api_get, api_post, api_put, handle_error, parse_link_header
from ._split import normalize_action, reject_unless_in


def register_requesters_tools(mcp) -> None:
    """Register requester-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  requester — read/manage split                                      #
    # ------------------------------------------------------------------ #
    _READ_REQUESTER = {"get", "list", "filter", "get_fields"}
    _WRITE_REQUESTER = {"create", "update", "add_to_group"}

    async def _requester_handler(
        action: str,
        requester_id: Optional[int],
        first_name: Optional[str],
        last_name: Optional[str],
        job_title: Optional[str],
        primary_email: Optional[str],
        secondary_emails: Optional[List[str]],
        work_phone_number: Optional[str],
        mobile_phone_number: Optional[str],
        department_ids: Optional[List[int]],
        can_see_all_tickets_from_associated_departments: Optional[bool],
        reporting_manager_id: Optional[int],
        address: Optional[str],
        time_zone: Optional[str],
        time_format: Optional[str],
        language: Optional[str],
        location_id: Optional[int],
        background_information: Optional[str],
        custom_fields: Optional[Dict[str, Any]],
        query: Optional[str],
        include_agents: bool,
        group_id: Optional[int],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        if action == "get_fields":
            try:
                resp = await api_get("requester_fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get requester fields")

        if action == "list":
            try:
                resp = await api_get("requesters", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "requesters": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                    },
                }
            except Exception as e:
                return handle_error(e, "list requesters")

        if action == "get":
            if not requester_id:
                return {"error": "requester_id required for get"}
            try:
                resp = await api_get(f"requesters/{requester_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get requester")

        if action == "filter":
            if not query:
                return {"error": "query required for filter"}
            params: Dict[str, Any] = {
                "query": query,
            }
            if include_agents:
                params["include_agents"] = "true"
            try:
                resp = await api_get("requesters", params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "filter requesters")

        if action == "create":
            if not first_name:
                return {"error": "first_name required for create"}
            data: Dict[str, Any] = {"first_name": first_name}
            for k, v in [("last_name", last_name), ("job_title", job_title),
                         ("primary_email", primary_email),
                         ("secondary_emails", secondary_emails),
                         ("work_phone_number", work_phone_number),
                         ("mobile_phone_number", mobile_phone_number),
                         ("department_ids", department_ids),
                         ("can_see_all_tickets_from_associated_departments",
                          can_see_all_tickets_from_associated_departments),
                         ("reporting_manager_id", reporting_manager_id),
                         ("address", address), ("time_zone", time_zone),
                         ("time_format", time_format), ("language", language),
                         ("location_id", location_id),
                         ("background_information", background_information),
                         ("custom_fields", custom_fields)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_post("requesters", json=data)
                resp.raise_for_status()
                return {"success": True, "requester": resp.json()}
            except Exception as e:
                return handle_error(e, "create requester")

        if action == "update":
            if not requester_id:
                return {"error": "requester_id required for update"}
            data: Dict[str, Any] = {}
            for k, v in [("first_name", first_name), ("last_name", last_name),
                         ("job_title", job_title), ("primary_email", primary_email),
                         ("secondary_emails", secondary_emails),
                         ("work_phone_number", work_phone_number),
                         ("mobile_phone_number", mobile_phone_number),
                         ("department_ids", department_ids),
                         ("can_see_all_tickets_from_associated_departments",
                          can_see_all_tickets_from_associated_departments),
                         ("reporting_manager_id", reporting_manager_id),
                         ("address", address), ("time_zone", time_zone),
                         ("time_format", time_format), ("language", language),
                         ("location_id", location_id),
                         ("background_information", background_information),
                         ("custom_fields", custom_fields)]:
                if v is not None:
                    data[k] = v
            if not data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"requesters/{requester_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "requester": resp.json()}
            except Exception as e:
                return handle_error(e, "update requester")

        if action == "add_to_group":
            if not requester_id or not group_id:
                return {"error": "requester_id and group_id required for add_to_group"}
            try:
                resp = await api_post(f"requester_groups/{group_id}/members/{requester_id}")
                resp.raise_for_status()
                return {"success": True, "message": "Requester added to group"}
            except Exception as e:
                return handle_error(e, "add requester to group")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_requester(
        action: str,
        requester_id: Optional[int] = None,
        query: Optional[str] = None,
        include_agents: bool = False,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice requesters.

        Actions: list, get, filter, get_fields

        Required per action:
          get: requester_id
          filter: query

        Optional: include_agents (filter), page, per_page (list).
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_REQUESTER, "read_requester", "manage_requester")
        if err:
            return err
        return await _requester_handler(
            action, requester_id, None, None, None, None, None, None, None, None,
            None, None, None, None, None, None, None, None, None,
            query, include_agents, None, page, per_page,
        )

    @mcp.tool()
    async def manage_requester(
        action: str,
        requester_id: Optional[int] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        job_title: Optional[str] = None,
        primary_email: Optional[str] = None,
        secondary_emails: Optional[List[str]] = None,
        work_phone_number: Optional[str] = None,
        mobile_phone_number: Optional[str] = None,
        department_ids: Optional[List[int]] = None,
        can_see_all_tickets_from_associated_departments: Optional[bool] = None,
        reporting_manager_id: Optional[int] = None,
        address: Optional[str] = None,
        time_zone: Optional[str] = None,
        time_format: Optional[str] = None,
        language: Optional[str] = None,
        location_id: Optional[int] = None,
        background_information: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        group_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice requesters.

        Actions: create, update, add_to_group

        Required per action:
          create: first_name
          update: requester_id
          add_to_group: requester_id, group_id

        Optional: last_name, job_title, primary_email, secondary_emails,
        work_phone_number, mobile_phone_number, department_ids,
        reporting_manager_id, address, time_zone, time_format, language,
        location_id, background_information, custom_fields,
        can_see_all_tickets_from_associated_departments.
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _WRITE_REQUESTER, "manage_requester", "read_requester")
        if err:
            return err
        return await _requester_handler(
            action, requester_id, first_name, last_name, job_title, primary_email,
            secondary_emails, work_phone_number, mobile_phone_number, department_ids,
            can_see_all_tickets_from_associated_departments, reporting_manager_id,
            address, time_zone, time_format, language, location_id,
            background_information, custom_fields, None, False, group_id, 1, 30,
        )

    # ------------------------------------------------------------------ #
    #  requester_group — read/manage split                                #
    # ------------------------------------------------------------------ #
    _READ_REQUESTER_GROUP = {"list", "get", "list_members"}
    _WRITE_REQUESTER_GROUP = {"create", "update"}

    async def _requester_group_handler(
        action: str,
        group_id: Optional[int],
        name: Optional[str],
        description: Optional[str],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        if action == "list":
            try:
                resp = await api_get("requester_groups", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "requester_groups": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                    },
                }
            except Exception as e:
                return handle_error(e, "list requester groups")

        if action == "get":
            if not group_id:
                return {"error": "group_id required for get"}
            try:
                resp = await api_get(f"requester_groups/{group_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get requester group")

        if action == "create":
            if not name:
                return {"error": "name required for create"}
            data: Dict[str, Any] = {"name": name}
            if description is not None:
                data["description"] = description
            try:
                resp = await api_post("requester_groups", json=data)
                resp.raise_for_status()
                return {"success": True, "requester_group": resp.json()}
            except Exception as e:
                return handle_error(e, "create requester group")

        if action == "update":
            if not group_id:
                return {"error": "group_id required for update"}
            data: Dict[str, Any] = {}
            if name is not None:
                data["name"] = name
            if description is not None:
                data["description"] = description
            if not data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"requester_groups/{group_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "requester_group": resp.json()}
            except Exception as e:
                return handle_error(e, "update requester group")

        if action == "list_members":
            if not group_id:
                return {"error": "group_id required for list_members"}
            try:
                resp = await api_get(f"requester_groups/{group_id}/members")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list requester group members")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_requester_group(
        action: str,
        group_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice requester groups.

        Actions: list, get, list_members

        Required per action:
          get / list_members: group_id

        Optional: page, per_page (list).
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _READ_REQUESTER_GROUP, "read_requester_group", "manage_requester_group")
        if err:
            return err
        return await _requester_group_handler(action, group_id, None, None, page, per_page)

    @mcp.tool()
    async def manage_requester_group(
        action: str,
        group_id: Optional[int] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice requester groups.

        Actions: create, update

        Required per action:
          create: name
          update: group_id

        Optional: description.
        """
        action = normalize_action(action)
        err = reject_unless_in(action, _WRITE_REQUESTER_GROUP, "manage_requester_group", "read_requester_group")
        if err:
            return err
        return await _requester_group_handler(action, group_id, name, description, 1, 30)
