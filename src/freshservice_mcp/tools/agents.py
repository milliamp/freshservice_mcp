"""Freshservice MCP — Agents & Groups tools (consolidated).

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  • read_agent       / manage_agent        — list/get/filter/get_fields vs create/update
  • read_agent_group / manage_agent_group  — list/get vs create/update
"""
from typing import Any, Dict, List, Optional

from ..http_client import api_get, api_post, api_put, handle_error, parse_link_header
from ._split import normalize_action, reject_unless_in


def register_agents_tools(mcp) -> None:
    """Register agent-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  agent — read/manage split                                          #
    # ------------------------------------------------------------------ #
    _READ_AGENT = {"get", "list", "filter", "get_fields"}
    _WRITE_AGENT = {"create", "update"}

    async def _agent_handler(
        action: str,
        agent_id: Optional[int],
        first_name: Optional[str],
        last_name: Optional[str],
        email: Optional[str],
        occasional: Optional[bool],
        job_title: Optional[str],
        work_phone_number: Optional[int],
        mobile_phone_number: Optional[int],
        department_ids: Optional[List[int]],
        can_see_all_tickets_from_associated_departments: Optional[bool],
        reporting_manager_id: Optional[int],
        address: Optional[str],
        time_zone: Optional[str],
        time_format: Optional[str],
        language: Optional[str],
        location_id: Optional[int],
        background_information: Optional[str],
        scoreboard_level_id: Optional[int],
        query: Optional[str],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        if action == "get_fields":
            try:
                resp = await api_get("agent_fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get agent fields")

        if action == "list":
            try:
                resp = await api_get("agents", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "agents": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                    },
                }
            except Exception as e:
                return handle_error(e, "list agents")

        if action == "get":
            if not agent_id:
                return {"error": "agent_id required for get"}
            try:
                resp = await api_get(f"agents/{agent_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get agent")

        if action == "filter":
            if not query:
                return {"error": "query required for filter"}
            all_agents: List[Any] = []
            current_page = 1
            while True:
                try:
                    params: Dict[str, Any] = {
                        "query": f'"{query}"',
                        "page": current_page,
                    }
                    resp = await api_get("agents", params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    agents = data.get("agents", [])
                    if not agents:
                        break
                    all_agents.extend(agents)
                    link = resp.headers.get("Link", "")
                    if 'rel="next"' not in link:
                        break
                    current_page += 1
                except Exception as e:
                    return handle_error(e, "filter agents")
            return {"agents": all_agents, "total": len(all_agents)}

        if action == "create":
            if not first_name:
                return {"error": "first_name required for create"}
            data: Dict[str, Any] = {"first_name": first_name}
            for k, v in [("last_name", last_name), ("email", email),
                         ("occasional", occasional), ("job_title", job_title),
                         ("work_phone_number", work_phone_number),
                         ("mobile_phone_number", mobile_phone_number),
                         ("department_ids", department_ids),
                         ("reporting_manager_id", reporting_manager_id),
                         ("address", address), ("time_zone", time_zone),
                         ("time_format", time_format), ("language", language),
                         ("location_id", location_id),
                         ("background_information", background_information),
                         ("scoreboard_level_id", scoreboard_level_id),
                         ("can_see_all_tickets_from_associated_departments",
                          can_see_all_tickets_from_associated_departments)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_post("agents", json=data)
                resp.raise_for_status()
                return {"success": True, "agent": resp.json()}
            except Exception as e:
                return handle_error(e, "create agent")

        if action == "update":
            if not agent_id:
                return {"error": "agent_id required for update"}
            data: Dict[str, Any] = {}
            for k, v in [("first_name", first_name), ("last_name", last_name),
                         ("email", email), ("occasional", occasional),
                         ("job_title", job_title),
                         ("work_phone_number", work_phone_number),
                         ("mobile_phone_number", mobile_phone_number),
                         ("department_ids", department_ids),
                         ("reporting_manager_id", reporting_manager_id),
                         ("address", address), ("time_zone", time_zone),
                         ("time_format", time_format), ("language", language),
                         ("location_id", location_id),
                         ("background_information", background_information),
                         ("scoreboard_level_id", scoreboard_level_id),
                         ("can_see_all_tickets_from_associated_departments",
                          can_see_all_tickets_from_associated_departments)]:
                if v is not None:
                    data[k] = v
            if not data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"agents/{agent_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "agent": resp.json()}
            except Exception as e:
                return handle_error(e, "update agent")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_agent(
        action: str,
        agent_id: Optional[int] = None,
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice agents.

        Actions: list, get, filter, get_fields

        Required per action:
          get: agent_id
          filter: query

        Optional: page, per_page (list).
        """
        action = normalize_action(action, _READ_AGENT)
        err = reject_unless_in(action, _READ_AGENT, "read_agent", "manage_agent")
        if err:
            return err
        return await _agent_handler(
            action, agent_id, None, None, None, None, None, None, None, None,
            None, None, None, None, None, None, None, None, None, query, page, per_page,
        )

    @mcp.tool()
    async def manage_agent(
        action: str,
        agent_id: Optional[int] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        occasional: Optional[bool] = None,
        job_title: Optional[str] = None,
        work_phone_number: Optional[int] = None,
        mobile_phone_number: Optional[int] = None,
        department_ids: Optional[List[int]] = None,
        can_see_all_tickets_from_associated_departments: Optional[bool] = None,
        reporting_manager_id: Optional[int] = None,
        address: Optional[str] = None,
        time_zone: Optional[str] = None,
        time_format: Optional[str] = None,
        language: Optional[str] = None,
        location_id: Optional[int] = None,
        background_information: Optional[str] = None,
        scoreboard_level_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice agents.

        Actions: create, update

        Required per action:
          create: first_name
          update: agent_id

        Optional: last_name, email, occasional, job_title, work_phone_number,
        mobile_phone_number, department_ids, reporting_manager_id, address,
        time_zone, time_format, language, location_id, background_information,
        scoreboard_level_id, can_see_all_tickets_from_associated_departments.
        """
        action = normalize_action(action, _WRITE_AGENT)
        err = reject_unless_in(action, _WRITE_AGENT, "manage_agent", "read_agent")
        if err:
            return err
        return await _agent_handler(
            action, agent_id, first_name, last_name, email, occasional, job_title,
            work_phone_number, mobile_phone_number, department_ids,
            can_see_all_tickets_from_associated_departments, reporting_manager_id,
            address, time_zone, time_format, language, location_id,
            background_information, scoreboard_level_id, None, 1, 30,
        )

    # ------------------------------------------------------------------ #
    #  agent_group — read/manage split                                    #
    # ------------------------------------------------------------------ #
    _READ_AGENT_GROUP = {"list", "get"}
    _WRITE_AGENT_GROUP = {"create", "update"}

    async def _agent_group_handler(
        action: str,
        group_id: Optional[int],
        name: Optional[str],
        description: Optional[str],
        agent_ids: Optional[List[int]],
        auto_ticket_assign: Optional[bool],
        escalate_to: Optional[int],
        unassigned_for: Optional[str],
        group_fields: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if action == "list":
            try:
                resp = await api_get("groups")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list agent groups")

        if action == "get":
            if not group_id:
                return {"error": "group_id required for get"}
            try:
                resp = await api_get(f"groups/{group_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get agent group")

        if action == "create":
            if not name:
                return {"error": "name required for create"}
            data: Dict[str, Any] = {"name": name}
            for k, v in [("description", description), ("agent_ids", agent_ids),
                         ("auto_ticket_assign", auto_ticket_assign),
                         ("escalate_to", escalate_to),
                         ("unassigned_for", unassigned_for)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_post("groups", json=data)
                resp.raise_for_status()
                return {"success": True, "group": resp.json()}
            except Exception as e:
                return handle_error(e, "create agent group")

        if action == "update":
            if not group_id:
                return {"error": "group_id required for update"}
            data = group_fields or {}
            for k, v in [("name", name), ("description", description),
                         ("agent_ids", agent_ids),
                         ("auto_ticket_assign", auto_ticket_assign),
                         ("escalate_to", escalate_to),
                         ("unassigned_for", unassigned_for)]:
                if v is not None:
                    data[k] = v
            if not data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"groups/{group_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "group": resp.json()}
            except Exception as e:
                return handle_error(e, "update agent group")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_agent_group(
        action: str,
        group_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read Freshservice agent groups.

        Actions: list, get

        Required per action:
          get: group_id
        """
        action = normalize_action(action, _READ_AGENT_GROUP)
        err = reject_unless_in(action, _READ_AGENT_GROUP, "read_agent_group", "manage_agent_group")
        if err:
            return err
        return await _agent_group_handler(action, group_id, None, None, None, None, None, None, None)

    @mcp.tool()
    async def manage_agent_group(
        action: str,
        group_id: Optional[int] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        agent_ids: Optional[List[int]] = None,
        auto_ticket_assign: Optional[bool] = None,
        escalate_to: Optional[int] = None,
        unassigned_for: Optional[str] = None,
        group_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice agent groups.

        Actions: create, update

        Required per action:
          create: name
          update: group_id

        Optional: description, agent_ids, auto_ticket_assign, escalate_to,
        unassigned_for (e.g. '30m', '1h'), group_fields (alt fields dict
        for update).
        """
        action = normalize_action(action, _WRITE_AGENT_GROUP)
        err = reject_unless_in(action, _WRITE_AGENT_GROUP, "manage_agent_group", "read_agent_group")
        if err:
            return err
        return await _agent_group_handler(
            action, group_id, name, description, agent_ids, auto_ticket_assign,
            escalate_to, unassigned_for, group_fields,
        )
