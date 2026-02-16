"""Freshservice MCP — Status Page tools.

Exposes 1 tool:
  • manage_status_page — list pages, service components, CRUD maintenance
    (from change or maintenance-window), CRUD incidents (from ticket),
    maintenance/incident updates, statuses, and subscriber management.

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

from ..http_client import api_delete, api_get, api_post, api_put, handle_error

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


def register_status_page_tools(mcp) -> None:
    """Register status page tools on *mcp*."""

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
        component_id: Optional[int] = None,
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
        # pagination
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Unified Status Page operations: maintenance windows, incidents, components.

        Args:
            action: One of:
              Pages:        'list_pages'
              Components:   'list_components', 'get_component'
              Maintenance:  'list_maintenance', 'create_maintenance', 'update_maintenance',
                            'get_maintenance', 'delete_maintenance'
              Maintenance Updates: 'create_maintenance_update', 'list_maintenance_updates',
                            'update_maintenance_update', 'delete_maintenance_update'
              Incidents:    'list_incidents', 'create_incident', 'update_incident',
                            'get_incident', 'delete_incident'
              Incident Updates: 'create_incident_update', 'list_incident_updates',
                            'update_incident_update', 'delete_incident_update'
              Statuses:     'list_incident_statuses', 'list_maintenance_statuses'
              Subscribers:  'list_subscribers', 'get_subscriber', 'create_subscriber',
                            'update_subscriber', 'delete_subscriber'
            status_page_id: Status page ID (auto-discovered if omitted).
            change_id: Change ID — maintenance CRUD from a change.
            maintenance_window_id: Maintenance Window ID — maintenance CRUD from a MW.
                Supply either change_id OR maintenance_window_id for maintenance
                create/update/get/delete and their updates.
            ticket_id: Ticket ID — incident CRUD (required for create/update/get/delete,
                not needed for list_incidents).
            maintenance_id: Maintenance ID (get/update/delete maintenance, maintenance updates)
            incident_id: Incident ID (get/update/delete incident, incident updates)
            update_id: Update ID (update/delete maintenance/incident updates)
            component_id: Service component ID (get_component)
            subscriber_id: Subscriber ID (get/update/delete subscriber)
            title: Title (create maintenance/incident) — Mandatory
            description: HTML description
            started_at: ISO datetime — start time (maintenance/incident)
            ended_at: ISO datetime — end time (maintenance)
            impacted_services: [{id, status}] — 1=Operational, 5=Under maintenance,
                10=Degraded, 20=Partial outage, 30=Major outage — Mandatory for create_maintenance
            notifications: Array of notification dicts [{trigger, options: {value}}]
                trigger: 1=On start, 2=Before start, 3=On complete
            is_private: Private maintenance/incident (default false)
            body: Update body text (maintenance/incident updates)
            update_status: Status string for updates
            email: Subscriber email (create_subscriber — Mandatory)
            service_ids: List of service IDs the subscriber is subscribed to
            subscribe_all_services: true = notify for all services
            subscriber_type: 1=External, 2=Agent, 3=Requester
            timezone: Subscriber timezone (e.g. "UTC")
            page/per_page: Pagination
        """
        action = action.lower().strip()

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
        # Docs: GET status/pages/{sp}/service-components[/{id}]
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
        # List:   GET status/pages/{sp}/maintenances  (no prefix needed)
        # CRUD:   {changes/{cid} | maintenance-windows/{mwid}}/status/pages/{sp}/maintenances[/{id}]
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
                return {"error": "change_id or maintenance_window_id required for create_maintenance"}
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
            try:
                resp = await api_get(
                    f"{prefix}/status/pages/{sp}/maintenances/{maintenance_id}"
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get maintenance")

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
        # URL: {prefix}/status/pages/{sp}/maintenances/{mid}/updates[/{uid}]
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
        # Docs: GET status/pages/{sp}/maintenances/statuses
        if action == "list_maintenance_statuses":
            try:
                resp = await api_get(f"status/pages/{sp}/maintenances/statuses")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list maintenance statuses")

        # ── Incidents — CRUD ──
        # List:   GET status/pages/{sp}/incidents  (no prefix)
        # CRUD:   tickets/{tid}/status/pages/{sp}/incidents[/{id}]
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
            try:
                resp = await api_get(
                    f"tickets/{ticket_id}/status/pages/{sp}/incidents/{incident_id}"
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get incident")

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
        # URL: tickets/{tid}/status/pages/{sp}/incidents/{iid}/updates[/{uid}]
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
        # Docs: GET status/pages/{sp}/incidents/statuses
        if action == "list_incident_statuses":
            try:
                resp = await api_get(f"status/pages/{sp}/incidents/statuses")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list incident statuses")

        # ── Subscribers ──
        # Docs: GET|POST status/pages/{sp}/subscribers[/{sid}]
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

        return {
            "error": f"Unknown action '{action}'. Valid: list_pages, list_components, "
            "get_component, list_maintenance, create_maintenance, get_maintenance, "
            "update_maintenance, delete_maintenance, list_maintenance_updates, "
            "create_maintenance_update, update_maintenance_update, delete_maintenance_update, "
            "list_maintenance_statuses, list_incidents, create_incident, get_incident, "
            "update_incident, delete_incident, list_incident_updates, create_incident_update, "
            "update_incident_update, delete_incident_update, list_incident_statuses, "
            "list_subscribers, get_subscriber, create_subscriber, update_subscriber, "
            "delete_subscriber"
        }
