"""Freshservice MCP — Status Page tools.

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  • read_status_page / manage_status_page                     —
        list_pages/list_components/get_component/list_maintenance/
        get_maintenance/list_maintenance_updates/list_maintenance_statuses/
        list_incidents/get_incident/list_incident_updates/
        list_incident_statuses/list_subscribers/get_subscriber
      vs create_maintenance/update_maintenance/delete_maintenance/
        create_maintenance_update/update_maintenance_update/
        delete_maintenance_update/create_incident/update_incident/
        delete_incident/create_incident_update/update_incident_update/
        delete_incident_update/create_subscriber/update_subscriber/
        delete_subscriber
  • read_maintenance_window / manage_maintenance_window       —
        list/get vs create/update/delete

URL patterns per official Freshservice API v2 docs
(https://api.freshservice.com/v2/#status-page):

  Pages & lists (no entity prefix):
    GET  status/pages?workspace_id=...
    GET  status/pages/{sp}/service-components
    GET  status/pages/{sp}/service-components/{id}
    GET  status/pages/{sp}/maintenances
    GET  status/pages/{sp}/incidents
    GET  status/pages/{sp}/maintenances/statuses
    GET  status/pages/{sp}/incidents/statuses

  Maintenance — from a Change:
    POST|GET|PUT|DELETE  changes/{cid}/status/pages/{sp}/maintenances[/{id}]
    POST|GET|PUT|DELETE  changes/{cid}/status/pages/{sp}/maintenances/{mid}/updates[/{uid}]

  Maintenance — from a Maintenance Window:
    POST|GET|PUT|DELETE  maintenance-windows/{mwid}/status/pages/{sp}/maintenances[/{id}]
    POST|GET|PUT|DELETE  maintenance-windows/{mwid}/status/pages/{sp}/maintenances/{mid}/updates[/{uid}]

  Incidents — from a Ticket:
    POST|GET|PUT|DELETE  tickets/{tid}/status/pages/{sp}/incidents[/{id}]
    POST|GET|PUT|DELETE  tickets/{tid}/status/pages/{sp}/incidents/{iid}/updates[/{uid}]

  Subscribers:
    GET|POST  status/pages/{sp}/subscribers
    GET|PUT|DELETE  status/pages/{sp}/subscribers/{sid}
"""
from typing import Any, Dict, List, Optional

import httpx

from ..http_client import (
    api_delete,
    api_get,
    api_post,
    api_put,
    gather_enrichments,
    handle_error,
)
from ._split import normalize_action, reject_unless_in

# Module-level caches for auto-discovered IDs
_cached_workspace_id: Optional[int] = None
_cached_status_page_id: Optional[int] = None


async def _resolve_workspace_id() -> Optional[int]:
    """Return the primary workspace_id (cached)."""
    global _cached_workspace_id
    if _cached_workspace_id:
        return _cached_workspace_id
    try:
        resp = await api_get("workspaces")
        resp.raise_for_status()
        data = resp.json()
        workspaces = data.get("workspaces", data if isinstance(data, list) else [])
        if workspaces:
            _cached_workspace_id = workspaces[0]["id"]
            return _cached_workspace_id
    except Exception:
        pass
    return None


async def _resolve_status_page_id(explicit_id: Optional[int]) -> Optional[int]:
    """Return the status_page_id to use (auto-discovers if not given)."""
    global _cached_status_page_id
    if explicit_id:
        return explicit_id
    if _cached_status_page_id:
        return _cached_status_page_id
    try:
        workspace_id = await _resolve_workspace_id()
        params: Dict[str, Any] = {}
        if workspace_id:
            params["workspace_id"] = workspace_id
        resp = await api_get("status/pages", params=params or None)
        resp.raise_for_status()
        data = resp.json()
        pages = data.get("status_pages", data if isinstance(data, list) else [])
        if pages:
            _cached_status_page_id = pages[0]["id"]
            return _cached_status_page_id
    except Exception:
        pass
    return None


def _maint_prefix(change_id: Optional[int], maintenance_window_id: Optional[int]) -> Optional[str]:
    """Return the URL prefix for maintenance CRUD.

    Freshservice supports two sources:
      - From a Change:              changes/{change_id}
      - From a Maintenance Window:  maintenance-windows/{mw_id}
    Returns None if neither ID is provided.
    """
    if change_id:
        return f"changes/{change_id}"
    if maintenance_window_id:
        return f"maintenance-windows/{maintenance_window_id}"
    return None


def register_status_page_tools(mcp) -> None:  # noqa: C901
    """Register status page tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  status_page — read/manage split                                    #
    # ------------------------------------------------------------------ #
    _READ_STATUS_PAGE = {
        "list_pages",
        "list_components", "get_component",
        "list_maintenance", "get_maintenance",
        "list_maintenance_updates",
        "list_maintenance_statuses",
        "list_incidents", "get_incident",
        "list_incident_updates",
        "list_incident_statuses",
        "list_subscribers", "get_subscriber",
    }
    _WRITE_STATUS_PAGE = {
        "create_maintenance", "update_maintenance", "delete_maintenance",
        "create_maintenance_update", "update_maintenance_update", "delete_maintenance_update",
        "create_incident", "update_incident", "delete_incident",
        "create_incident_update", "update_incident_update", "delete_incident_update",
        "create_subscriber", "update_subscriber", "delete_subscriber",
    }

    async def _status_page_handler(
        action: str,
        # identifiers
        status_page_id: Optional[int],
        change_id: Optional[int],
        maintenance_window_id: Optional[int],
        ticket_id: Optional[int],
        maintenance_id: Optional[int],
        incident_id: Optional[int],
        update_id: Optional[int],
        component_id: Optional[int],
        subscriber_id: Optional[int],
        # maintenance / incident fields
        title: Optional[str],
        description: Optional[str],
        started_at: Optional[str],
        ended_at: Optional[str],
        impacted_services: Optional[List[Dict[str, Any]]],
        notifications: Optional[List[Dict[str, Any]]],
        is_private: Optional[bool],
        # updates
        body: Optional[str],
        update_status: Optional[str],
        # subscriber fields
        email: Optional[str],
        service_ids: Optional[List[int]],
        subscribe_all_services: Optional[bool],
        subscriber_type: Optional[int],
        timezone: Optional[str],
        # pagination
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        # Auto-resolve status_page_id for actions that need it
        if action != "list_pages":
            status_page_id = await _resolve_status_page_id(status_page_id)
            if not status_page_id:
                return {
                    "error": "Could not determine status_page_id. "
                    "Use action='list_pages' first, or pass status_page_id explicitly."
                }

        sp = status_page_id  # shorthand

        # ── List status pages ──
        if action == "list_pages":
            try:
                workspace_id = await _resolve_workspace_id()
                params_lp: Dict[str, Any] = {"page": page, "per_page": per_page}
                if workspace_id:
                    params_lp["workspace_id"] = workspace_id
                resp = await api_get("status/pages", params=params_lp)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list status pages")

        # ── Service Components ──
        if action == "list_components":
            try:
                resp = await api_get(
                    f"status/pages/{sp}/service-components",
                    params={"page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list service components")

        if action == "get_component":
            if not component_id:
                return {"error": "component_id required for get_component"}
            try:
                resp = await api_get(f"status/pages/{sp}/service-components/{component_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get service component")

        # ── Maintenance — CRUD ──
        if action == "list_maintenance":
            try:
                resp = await api_get(
                    f"status/pages/{sp}/maintenances",
                    params={"page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list maintenances")

        if action == "create_maintenance":
            prefix = _maint_prefix(change_id, maintenance_window_id)
            if not prefix:
                return {
                    "error": "change_id or maintenance_window_id required for create_maintenance. "
                    "IMPORTANT: If the change has no maintenance_window (empty {}), "
                    "you must first create one via manage_maintenance_window "
                    "action='create' with name, description, start_time, end_time, "
                    "workspace_id. Then pass the returned maintenance_window_id here."
                }
            data: Dict[str, Any] = {}
            for k, v in [("title", title), ("description", description),
                         ("started_at", started_at), ("ended_at", ended_at)]:
                if v is not None:
                    data[k] = v
            if impacted_services is not None:
                data["impacted_services"] = impacted_services
            if notifications is not None:
                data["notifications"] = notifications
            try:
                resp = await api_post(
                    f"{prefix}/status/pages/{sp}/maintenances",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "maintenance": resp.json()}
            except Exception as e:
                return handle_error(e, "create maintenance")

        if action == "get_maintenance":
            prefix = _maint_prefix(change_id, maintenance_window_id)
            if not prefix or not maintenance_id:
                return {"error": "change_id (or maintenance_window_id) and maintenance_id required"}
            base = f"{prefix}/status/pages/{sp}/maintenances/{maintenance_id}"
            try:
                resp = await api_get(base)
                resp.raise_for_status()
                result = resp.json()
            except Exception as e:
                return handle_error(e, "get maintenance")
            # Enrich with the updates timeline — almost always what a reader wants.
            result.update(await gather_enrichments({
                "maintenance_updates": f"{base}/updates",
            }))
            return result

        if action == "update_maintenance":
            prefix = _maint_prefix(change_id, maintenance_window_id)
            if not prefix or not maintenance_id:
                return {"error": "change_id (or maintenance_window_id) and maintenance_id required"}
            data = {}
            for k, v in [("title", title), ("description", description),
                         ("started_at", started_at), ("ended_at", ended_at),
                         ("impacted_services", impacted_services),
                         ("notifications", notifications)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_put(
                    f"{prefix}/status/pages/{sp}/maintenances/{maintenance_id}",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "maintenance": resp.json()}
            except Exception as e:
                return handle_error(e, "update maintenance")

        if action == "delete_maintenance":
            prefix = _maint_prefix(change_id, maintenance_window_id)
            if not prefix or not maintenance_id:
                return {"error": "change_id (or maintenance_window_id) and maintenance_id required"}
            try:
                resp = await api_delete(
                    f"{prefix}/status/pages/{sp}/maintenances/{maintenance_id}"
                )
                if resp.status_code == 204:
                    return {"success": True, "message": "Maintenance deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete maintenance")

        # ── Maintenance Updates ──
        if action == "list_maintenance_updates":
            prefix = _maint_prefix(change_id, maintenance_window_id)
            if not prefix or not maintenance_id:
                return {"error": "change_id (or maintenance_window_id) and maintenance_id required"}
            try:
                resp = await api_get(
                    f"{prefix}/status/pages/{sp}/maintenances/{maintenance_id}/updates"
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list maintenance updates")

        if action == "create_maintenance_update":
            prefix = _maint_prefix(change_id, maintenance_window_id)
            if not prefix or not maintenance_id or not body:
                return {"error": "change_id (or maintenance_window_id), maintenance_id, and body required"}
            data = {"body": body}
            if update_status:
                data["status"] = update_status
            try:
                resp = await api_post(
                    f"{prefix}/status/pages/{sp}/maintenances/{maintenance_id}/updates",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "update": resp.json()}
            except Exception as e:
                return handle_error(e, "create maintenance update")

        if action == "update_maintenance_update":
            prefix = _maint_prefix(change_id, maintenance_window_id)
            if not prefix or not maintenance_id or not update_id:
                return {"error": "change_id (or maintenance_window_id), maintenance_id, and update_id required"}
            data = {}
            if body:
                data["body"] = body
            if update_status:
                data["status"] = update_status
            try:
                resp = await api_put(
                    f"{prefix}/status/pages/{sp}/maintenances/{maintenance_id}/updates/{update_id}",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "update": resp.json()}
            except Exception as e:
                return handle_error(e, "update maintenance update")

        if action == "delete_maintenance_update":
            prefix = _maint_prefix(change_id, maintenance_window_id)
            if not prefix or not maintenance_id or not update_id:
                return {"error": "change_id (or maintenance_window_id), maintenance_id, and update_id required"}
            try:
                resp = await api_delete(
                    f"{prefix}/status/pages/{sp}/maintenances/{maintenance_id}/updates/{update_id}"
                )
                if resp.status_code == 204:
                    return {"success": True, "message": "Maintenance update deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete maintenance update")

        # ── Maintenance Statuses ──
        if action == "list_maintenance_statuses":
            try:
                resp = await api_get(f"status/pages/{sp}/maintenances/statuses")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list maintenance statuses")

        # ── Incidents — CRUD ──
        if action == "list_incidents":
            try:
                resp = await api_get(
                    f"status/pages/{sp}/incidents",
                    params={"page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list incidents")

        if action == "create_incident":
            if not ticket_id:
                return {"error": "ticket_id required for create_incident"}
            if not title:
                return {"error": "title required for create_incident"}
            data = {"title": title}
            for k, v in [("description", description), ("started_at", started_at)]:
                if v is not None:
                    data[k] = v
            if impacted_services is not None:
                data["impacted_services"] = impacted_services
            try:
                resp = await api_post(
                    f"tickets/{ticket_id}/status/pages/{sp}/incidents",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "incident": resp.json()}
            except Exception as e:
                return handle_error(e, "create incident")

        if action == "get_incident":
            if not ticket_id or not incident_id:
                return {"error": "ticket_id and incident_id required"}
            base = f"tickets/{ticket_id}/status/pages/{sp}/incidents/{incident_id}"
            try:
                resp = await api_get(base)
                resp.raise_for_status()
                result = resp.json()
            except Exception as e:
                return handle_error(e, "get incident")
            # Enrich with the updates timeline — almost always what a reader wants.
            result.update(await gather_enrichments({
                "incident_updates": f"{base}/updates",
            }))
            return result

        if action == "update_incident":
            if not ticket_id or not incident_id:
                return {"error": "ticket_id and incident_id required"}
            data = {}
            for k, v in [("title", title), ("description", description),
                         ("started_at", started_at)]:
                if v is not None:
                    data[k] = v
            if impacted_services is not None:
                data["impacted_services"] = impacted_services
            try:
                resp = await api_put(
                    f"tickets/{ticket_id}/status/pages/{sp}/incidents/{incident_id}",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "incident": resp.json()}
            except Exception as e:
                return handle_error(e, "update incident")

        if action == "delete_incident":
            if not ticket_id or not incident_id:
                return {"error": "ticket_id and incident_id required"}
            try:
                resp = await api_delete(
                    f"tickets/{ticket_id}/status/pages/{sp}/incidents/{incident_id}"
                )
                if resp.status_code == 204:
                    return {"success": True, "message": "Incident deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete incident")

        # ── Incident Updates ──
        if action == "list_incident_updates":
            if not ticket_id or not incident_id:
                return {"error": "ticket_id and incident_id required"}
            try:
                resp = await api_get(
                    f"tickets/{ticket_id}/status/pages/{sp}/incidents/{incident_id}/updates"
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list incident updates")

        if action == "create_incident_update":
            if not ticket_id or not incident_id or not body:
                return {"error": "ticket_id, incident_id, and body required"}
            data = {"body": body}
            if update_status:
                data["status"] = update_status
            try:
                resp = await api_post(
                    f"tickets/{ticket_id}/status/pages/{sp}/incidents/{incident_id}/updates",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "update": resp.json()}
            except Exception as e:
                return handle_error(e, "create incident update")

        if action == "update_incident_update":
            if not ticket_id or not incident_id or not update_id:
                return {"error": "ticket_id, incident_id, and update_id required"}
            data = {}
            if body:
                data["body"] = body
            if update_status:
                data["status"] = update_status
            try:
                resp = await api_put(
                    f"tickets/{ticket_id}/status/pages/{sp}/incidents/{incident_id}/updates/{update_id}",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "update": resp.json()}
            except Exception as e:
                return handle_error(e, "update incident update")

        if action == "delete_incident_update":
            if not ticket_id or not incident_id or not update_id:
                return {"error": "ticket_id, incident_id, and update_id required"}
            try:
                resp = await api_delete(
                    f"tickets/{ticket_id}/status/pages/{sp}/incidents/{incident_id}/updates/{update_id}"
                )
                if resp.status_code == 204:
                    return {"success": True, "message": "Incident update deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete incident update")

        # ── Incident Statuses ──
        if action == "list_incident_statuses":
            try:
                resp = await api_get(f"status/pages/{sp}/incidents/statuses")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list incident statuses")

        # ── Subscribers ──
        if action == "list_subscribers":
            try:
                resp = await api_get(
                    f"status/pages/{sp}/subscribers",
                    params={"page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list subscribers")

        if action == "get_subscriber":
            if not subscriber_id:
                return {"error": "subscriber_id required"}
            try:
                resp = await api_get(f"status/pages/{sp}/subscribers/{subscriber_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get subscriber")

        if action == "create_subscriber":
            if not email:
                return {"error": "email required for create_subscriber"}
            data = {"email": email}
            if service_ids is not None:
                data["service_ids"] = service_ids
            if subscribe_all_services is not None:
                data["subscribe_all_services"] = subscribe_all_services
            if subscriber_type is not None:
                data["type"] = subscriber_type
            if timezone:
                data["timezone"] = timezone
            try:
                resp = await api_post(f"status/pages/{sp}/subscribers", json=data)
                resp.raise_for_status()
                return {"success": True, "subscriber": resp.json()}
            except Exception as e:
                return handle_error(e, "create subscriber")

        if action == "update_subscriber":
            if not subscriber_id:
                return {"error": "subscriber_id required"}
            data = {}
            if service_ids is not None:
                data["service_ids"] = service_ids
            if subscribe_all_services is not None:
                data["subscribe_all_services"] = subscribe_all_services
            if subscriber_type is not None:
                data["type"] = subscriber_type
            if timezone:
                data["timezone"] = timezone
            try:
                resp = await api_put(
                    f"status/pages/{sp}/subscribers/{subscriber_id}",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "subscriber": resp.json()}
            except Exception as e:
                return handle_error(e, "update subscriber")

        if action == "delete_subscriber":
            if not subscriber_id:
                return {"error": "subscriber_id required"}
            try:
                resp = await api_delete(f"status/pages/{sp}/subscribers/{subscriber_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Subscriber deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete subscriber")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_status_page(
        action: str,
        status_page_id: Optional[int] = None,
        change_id: Optional[int] = None,
        maintenance_window_id: Optional[int] = None,
        ticket_id: Optional[int] = None,
        maintenance_id: Optional[int] = None,
        incident_id: Optional[int] = None,
        component_id: Optional[int] = None,
        subscriber_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Status Page resources: pages, components, maintenance, incidents, statuses, subscribers.

        Actions: list_pages, list_components, get_component, list_maintenance,
          get_maintenance, list_maintenance_updates, list_maintenance_statuses,
          list_incidents, get_incident, list_incident_updates,
          list_incident_statuses, list_subscribers, get_subscriber

        Required per action:
          get_component: component_id
          get_maintenance / list_maintenance_updates: maintenance_id + (change_id or maintenance_window_id)
          get_incident / list_incident_updates: ticket_id, incident_id
          get_subscriber: subscriber_id

        Optional: status_page_id (auto-discovered), page, per_page.

        Notes:
          - get_incident auto-enriches with incident_updates (the timeline).
          - get_maintenance auto-enriches with maintenance_updates.
          - Failed sub-fetches surface as _<key>_warning rather than failing
            the whole call.
        """
        action = normalize_action(action, _READ_STATUS_PAGE)
        err = reject_unless_in(action, _READ_STATUS_PAGE, "read_status_page", "manage_status_page")
        if err:
            return err
        return await _status_page_handler(
            action,
            status_page_id=status_page_id, change_id=change_id,
            maintenance_window_id=maintenance_window_id, ticket_id=ticket_id,
            maintenance_id=maintenance_id, incident_id=incident_id,
            update_id=None, component_id=component_id,
            subscriber_id=subscriber_id,
            title=None, description=None, started_at=None, ended_at=None,
            impacted_services=None, notifications=None, is_private=None,
            body=None, update_status=None,
            email=None, service_ids=None, subscribe_all_services=None,
            subscriber_type=None, timezone=None,
            page=page, per_page=per_page,
        )

    @mcp.tool()
    async def manage_status_page(
        action: str,
        # identifiers
        status_page_id: Optional[int] = None,
        change_id: Optional[int] = None,
        maintenance_window_id: Optional[int] = None,
        ticket_id: Optional[int] = None,
        maintenance_id: Optional[int] = None,
        incident_id: Optional[int] = None,
        update_id: Optional[int] = None,
        subscriber_id: Optional[int] = None,
        # maintenance / incident fields
        title: Optional[str] = None,
        description: Optional[str] = None,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None,
        impacted_services: Optional[List[Dict[str, Any]]] = None,
        notifications: Optional[List[Dict[str, Any]]] = None,
        is_private: Optional[bool] = None,
        # updates
        body: Optional[str] = None,
        update_status: Optional[str] = None,
        # subscriber fields
        email: Optional[str] = None,
        service_ids: Optional[List[int]] = None,
        subscribe_all_services: Optional[bool] = None,
        subscriber_type: Optional[int] = None,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write actions on Status Page maintenance, incidents, updates, subscribers.

        Actions: {create,update,delete}_{maintenance,maintenance_update,incident,
          incident_update,subscriber}

        Required per action (MW = change_id or maintenance_window_id):
          create_maintenance: MW, title, description, started_at, ended_at, impacted_services
          update/delete_maintenance: MW, maintenance_id
          create_maintenance_update: MW, maintenance_id, body
          update/delete_maintenance_update: MW, maintenance_id, update_id
          create_incident: ticket_id, title
          update/delete_incident: ticket_id, incident_id
          create_incident_update: ticket_id, incident_id, body
          update/delete_incident_update: ticket_id, incident_id, update_id
          create_subscriber: email
          update/delete_subscriber: subscriber_id

        Optional: status_page_id (auto-discovered).

        Enums: impacted_services.status 1=Op, 5=UnderMaint, 10=Degraded,
          20=PartialOut, 30=MajorOut. notifications.trigger 1=OnStart, 2=Before,
          3=OnComplete. subscriber_type 1=External, 2=Agent, 3=Requester.
        """
        action = normalize_action(action, _WRITE_STATUS_PAGE)
        err = reject_unless_in(action, _WRITE_STATUS_PAGE, "manage_status_page", "read_status_page")
        if err:
            return err
        return await _status_page_handler(
            action,
            status_page_id=status_page_id, change_id=change_id,
            maintenance_window_id=maintenance_window_id, ticket_id=ticket_id,
            maintenance_id=maintenance_id, incident_id=incident_id,
            update_id=update_id, component_id=None,
            subscriber_id=subscriber_id,
            title=title, description=description,
            started_at=started_at, ended_at=ended_at,
            impacted_services=impacted_services, notifications=notifications,
            is_private=is_private,
            body=body, update_status=update_status,
            email=email, service_ids=service_ids,
            subscribe_all_services=subscribe_all_services,
            subscriber_type=subscriber_type, timezone=timezone,
            page=1, per_page=30,
        )

    # ------------------------------------------------------------------ #
    #  maintenance_window — read/manage split                             #
    # ------------------------------------------------------------------ #
    _READ_MAINTENANCE_WINDOW = {"list", "get"}
    _WRITE_MAINTENANCE_WINDOW = {"create", "update", "delete"}

    async def _maintenance_window_handler(
        action: str,
        maintenance_window_id: Optional[int],
        change_id: Optional[int],
        name: Optional[str],
        description: Optional[str],
        start_time: Optional[str],
        end_time: Optional[str],
        workspace_id: Optional[int],
        alert_suppression: Optional[bool],
        impacted_services: Optional[List[Dict[str, Any]]],
        notifications: Optional[List[Dict[str, Any]]],
        is_private: Optional[bool],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        if action == "list":
            try:
                params: Dict[str, Any] = {"page": page, "per_page": per_page}
                resp = await api_get("maintenance_windows", params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list maintenance windows")

        if action == "get":
            if not maintenance_window_id:
                return {"error": "maintenance_window_id required for get"}
            try:
                resp = await api_get(f"maintenance_windows/{maintenance_window_id}")
                resp.raise_for_status()
                result = resp.json()
            except Exception as e:
                return handle_error(e, "get maintenance window")
            # If the MW is associated with a change, fetch that change too.
            mw = result.get("maintenance_window") or result
            associated_change_id = (
                (mw or {}).get("change_id")
                or (mw or {}).get("association", {}).get("change_id")
                if isinstance(mw, dict) else None
            )
            if associated_change_id:
                result.update(await gather_enrichments({
                    "change": f"changes/{associated_change_id}",
                }))
            return result

        if action == "create":
            if not name:
                return {"error": "name required for create"}
            if not start_time or not end_time:
                return {"error": "start_time and end_time required for create"}
            # Auto-resolve workspace_id if not provided
            ws = workspace_id or await _resolve_workspace_id()
            data: Dict[str, Any] = {
                "name": name,
                "start_time": start_time,
                "end_time": end_time,
            }
            if ws:
                data["workspace_id"] = ws
            if description is not None:
                data["description"] = description
            if alert_suppression is not None:
                data["alert_suppression"] = alert_suppression
            try:
                resp = await api_post("maintenance_windows", json=data)
                resp.raise_for_status()
                result = resp.json()
                mw = result.get("maintenance_window", result)
                mw_id = mw.get("id")

                # Auto-associate MW with Change if change_id provided
                change_associated = False
                assoc_error = None
                if change_id and mw_id:
                    assoc_payload = {"maintenance_window": {"id": mw_id}}
                    try:
                        assoc_resp = await api_put(
                            f"changes/{change_id}",
                            json=assoc_payload,
                        )
                        assoc_resp.raise_for_status()
                        # Verify association took effect
                        verify = assoc_resp.json()
                        chg = verify.get("change", verify)
                        mw_check = chg.get("maintenance_window", {})
                        if mw_check.get("id") == mw_id:
                            change_associated = True
                        else:
                            assoc_error = (
                                f"PUT returned 200 but maintenance_window.id "
                                f"is {mw_check.get('id')} (expected {mw_id}). "
                                f"change_window_id={chg.get('change_window_id')}"
                            )
                    except httpx.HTTPStatusError as assoc_e:
                        try:
                            err_body = assoc_e.response.json()
                        except Exception:
                            err_body = assoc_e.response.text
                        assoc_error = (
                            f"PUT /changes/{change_id} with {assoc_payload} "
                            f"returned {assoc_e.response.status_code}: {err_body}"
                        )
                    except Exception as assoc_e:
                        assoc_error = (
                            f"PUT /changes/{change_id} with {assoc_payload} "
                            f"failed: {assoc_e}"
                        )

                # Auto-publish on Status Page if impacted_services provided
                sp_published = False
                sp_error = None
                sp_maintenance = None
                if impacted_services and mw_id:
                    sp = await _resolve_status_page_id(None)
                    if not sp:
                        sp_error = "Could not auto-discover status_page_id"
                    else:
                        sp_data: Dict[str, Any] = {
                            "title": name,
                            "description": description or name,
                            "started_at": start_time,
                            "ended_at": end_time,
                            "impacted_services": impacted_services,
                        }
                        if notifications is not None:
                            sp_data["notifications"] = notifications
                        if is_private is not None:
                            sp_data["is_private"] = is_private
                        try:
                            sp_resp = await api_post(
                                f"maintenance-windows/{mw_id}/status/pages/{sp}/maintenances",
                                json=sp_data,
                            )
                            sp_resp.raise_for_status()
                            sp_maintenance = sp_resp.json()
                            sp_published = True
                        except httpx.HTTPStatusError as sp_e:
                            try:
                                err_body = sp_e.response.json()
                            except Exception:
                                err_body = sp_e.response.text
                            sp_error = (
                                f"POST maintenance-windows/{mw_id}/status/pages/{sp}/maintenances "
                                f"returned {sp_e.response.status_code}: {err_body}"
                            )
                        except Exception as sp_e:
                            sp_error = f"Status Page publish failed: {sp_e}"

                response: Dict[str, Any] = {
                    "success": True,
                    "maintenance_window": mw,
                }
                if change_id:
                    response["change_association"] = {
                        "change_id": change_id,
                        "associated": change_associated,
                    }
                    if assoc_error:
                        response["change_association"]["error"] = assoc_error
                if impacted_services:
                    response["status_page"] = {
                        "published": sp_published,
                    }
                    if sp_maintenance:
                        response["status_page"]["maintenance"] = sp_maintenance
                    if sp_error:
                        response["status_page"]["error"] = sp_error

                # Build summary
                steps = [f"Maintenance Window created (id={mw_id})"]
                if change_associated:
                    steps.append(f"associated with Change #{change_id}")
                if sp_published:
                    steps.append("published on Status Page")
                next_steps = []
                if not change_associated and change_id:
                    next_steps.append(f"Association with Change #{change_id} failed — see error")
                if not sp_published and impacted_services:
                    next_steps.append("Status Page publish failed — see error")
                if not impacted_services:
                    next_steps.append(
                        f"To publish on Status Page, call manage_status_page "
                        f"action='create_maintenance' with maintenance_window_id={mw_id}, "
                        "title, description, started_at, ended_at, impacted_services. "
                        "OR re-call this tool with impacted_services."
                    )
                response["summary"] = " → ".join(steps)
                if next_steps:
                    response["next_steps"] = next_steps
                return response
            except Exception as e:
                return handle_error(e, "create maintenance window")

        if action == "update":
            if not maintenance_window_id:
                return {"error": "maintenance_window_id required for update"}
            data = {}
            for k, v in [("name", name), ("description", description),
                         ("start_time", start_time), ("end_time", end_time),
                         ("alert_suppression", alert_suppression)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_put(
                    f"maintenance_windows/{maintenance_window_id}", json=data
                )
                resp.raise_for_status()
                return {"success": True, "maintenance_window": resp.json()}
            except Exception as e:
                return handle_error(e, "update maintenance window")

        if action == "delete":
            if not maintenance_window_id:
                return {"error": "maintenance_window_id required for delete"}
            try:
                resp = await api_delete(
                    f"maintenance_windows/{maintenance_window_id}"
                )
                if resp.status_code in (200, 204):
                    return {"success": True, "message": "Maintenance window deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete maintenance window")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_maintenance_window(
        action: str,
        maintenance_window_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice Maintenance Windows.

        Actions: list, get
        Required per action:
          get: maintenance_window_id
        Optional: page, per_page (list).

        Notes:
          - get auto-enriches with the associated change object when the MW
            is linked to one. Failed enrichment surfaces as _change_warning.
        """
        action = normalize_action(action, _READ_MAINTENANCE_WINDOW)
        err = reject_unless_in(action, _READ_MAINTENANCE_WINDOW, "read_maintenance_window", "manage_maintenance_window")
        if err:
            return err
        return await _maintenance_window_handler(
            action,
            maintenance_window_id=maintenance_window_id,
            change_id=None, name=None, description=None,
            start_time=None, end_time=None, workspace_id=None,
            alert_suppression=None, impacted_services=None,
            notifications=None, is_private=None,
            page=page, per_page=per_page,
        )

    @mcp.tool()
    async def manage_maintenance_window(
        action: str,
        maintenance_window_id: Optional[int] = None,
        change_id: Optional[int] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        workspace_id: Optional[int] = None,
        alert_suppression: Optional[bool] = None,
        impacted_services: Optional[List[Dict[str, Any]]] = None,
        notifications: Optional[List[Dict[str, Any]]] = None,
        is_private: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice Maintenance Windows.

        Actions: create, update, delete

        Required per action:
          create: name, start_time, end_time
          update / delete: maintenance_window_id

        Optional: description, workspace_id (auto-discovered), alert_suppression.

        One-stop create: pass change_id to auto-associate with a Change, and
        impacted_services (+ optional notifications, is_private) to auto-publish
        on the Status Page in the same call. impacted_services status enum
        1=Operational, 5=Under maintenance, 10=Degraded, 20=Partial outage,
        30=Major outage. notifications trigger 1=On start, 2=Before start,
        3=On complete. Component IDs via read_status_page list_components.
        """
        action = normalize_action(action, _WRITE_MAINTENANCE_WINDOW)
        err = reject_unless_in(action, _WRITE_MAINTENANCE_WINDOW, "manage_maintenance_window", "read_maintenance_window")
        if err:
            return err
        return await _maintenance_window_handler(
            action,
            maintenance_window_id=maintenance_window_id,
            change_id=change_id, name=name, description=description,
            start_time=start_time, end_time=end_time,
            workspace_id=workspace_id, alert_suppression=alert_suppression,
            impacted_services=impacted_services, notifications=notifications,
            is_private=is_private,
            page=1, per_page=30,
        )
