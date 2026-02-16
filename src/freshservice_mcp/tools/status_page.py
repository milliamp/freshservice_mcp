"""Freshservice MCP — Status Page tools (maintenance windows, incidents, components).

Exposes 1 tool:
  • manage_status_page — list pages, list components, CRUD maintenance, CRUD incidents
"""
from typing import Any, Dict, List, Optional

from ..http_client import api_delete, api_get, api_post, api_put, handle_error


def register_status_page_tools(mcp) -> None:
    """Register status page tools on *mcp*."""

    @mcp.tool()
    async def manage_status_page(
        action: str,
        # identifiers
        status_page_id: Optional[int] = None,
        change_id: Optional[int] = None,
        maintenance_id: Optional[int] = None,
        incident_id: Optional[int] = None,
        update_id: Optional[int] = None,
        component_id: Optional[int] = None,
        # maintenance / incident fields
        title: Optional[str] = None,
        description: Optional[str] = None,
        scheduled_start_time: Optional[str] = None,
        scheduled_end_time: Optional[str] = None,
        impacted_services: Optional[List[Dict[str, Any]]] = None,
        notification: Optional[Dict[str, Any]] = None,
        is_private: Optional[bool] = None,
        # incident-specific
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        affected_services: Optional[List[Dict[str, Any]]] = None,
        # updates
        body: Optional[str] = None,
        update_status: Optional[str] = None,
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
            status_page_id: Status page ID (required for most actions)
            change_id: Change ID to link maintenance to (create_maintenance)
            maintenance_id: Maintenance ID (get/update/delete maintenance, maintenance updates)
            incident_id: Incident ID (get/update/delete incident, incident updates)
            update_id: Update ID (update/delete maintenance/incident updates)
            component_id: Service component ID (get_component)
            title: Title (create maintenance/incident)
            description: HTML description
            scheduled_start_time: ISO datetime (maintenance)
            scheduled_end_time: ISO datetime (maintenance)
            impacted_services: List of impacted services [{id, status}] where status:
                1=Operational, 5=Under maintenance, 10=Degraded, 20=Partial outage, 30=Major outage
            notification: Notification config dict (maintenance/incident)
            is_private: Private maintenance/incident (default false)
            start_time: ISO datetime (incident)
            end_time: ISO datetime (incident)
            affected_services: List of affected services for incidents
            body: Update body text (maintenance/incident updates)
            update_status: Status string for updates
            page/per_page: Pagination
        """
        action = action.lower().strip()

        # ── List status pages ──
        if action == "list_pages":
            try:
                resp = await api_get("status_pages")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list status pages")

        # ── Components ──
        if action == "list_components":
            if not status_page_id:
                return {"error": "status_page_id required for list_components"}
            try:
                resp = await api_get(
                    f"status_pages/{status_page_id}/components",
                    params={"page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list status page components")

        if action == "get_component":
            if not status_page_id or not component_id:
                return {"error": "status_page_id and component_id required for get_component"}
            try:
                resp = await api_get(f"status_pages/{status_page_id}/components/{component_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get status page component")

        # ── Maintenance — CRUD ──
        if action == "list_maintenance":
            if not status_page_id:
                return {"error": "status_page_id required for list_maintenance"}
            try:
                resp = await api_get(
                    f"status_pages/{status_page_id}/maintenances",
                    params={"page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list maintenances")

        if action == "create_maintenance":
            if not status_page_id or not change_id:
                return {"error": "status_page_id and change_id required for create_maintenance"}
            data: Dict[str, Any] = {}
            if title:
                data["title"] = title
            if description:
                data["description"] = description
            if scheduled_start_time:
                data["scheduled_start_time"] = scheduled_start_time
            if scheduled_end_time:
                data["scheduled_end_time"] = scheduled_end_time
            if impacted_services:
                data["impacted_services"] = impacted_services
            if notification:
                data["notification"] = notification
            if is_private is not None:
                data["is_private"] = is_private
            try:
                resp = await api_post(
                    f"status_pages/{status_page_id}/maintenances/changes/{change_id}",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "maintenance": resp.json()}
            except Exception as e:
                return handle_error(e, "create maintenance")

        if action == "get_maintenance":
            if not status_page_id or not change_id or not maintenance_id:
                return {"error": "status_page_id, change_id, and maintenance_id required"}
            try:
                resp = await api_get(
                    f"status_pages/{status_page_id}/maintenances/changes/{change_id}/{maintenance_id}"
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get maintenance")

        if action == "update_maintenance":
            if not status_page_id or not change_id or not maintenance_id:
                return {"error": "status_page_id, change_id, and maintenance_id required"}
            data = {}
            for k, v in [("title", title), ("description", description),
                         ("scheduled_start_time", scheduled_start_time),
                         ("scheduled_end_time", scheduled_end_time),
                         ("impacted_services", impacted_services),
                         ("notification", notification)]:
                if v is not None:
                    data[k] = v
            if is_private is not None:
                data["is_private"] = is_private
            try:
                resp = await api_put(
                    f"status_pages/{status_page_id}/maintenances/changes/{change_id}/{maintenance_id}",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "maintenance": resp.json()}
            except Exception as e:
                return handle_error(e, "update maintenance")

        if action == "delete_maintenance":
            if not status_page_id or not change_id or not maintenance_id:
                return {"error": "status_page_id, change_id, and maintenance_id required"}
            try:
                resp = await api_delete(
                    f"status_pages/{status_page_id}/maintenances/changes/{change_id}/{maintenance_id}"
                )
                if resp.status_code == 204:
                    return {"success": True, "message": "Maintenance deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete maintenance")

        # ── Maintenance Updates ──
        if action == "list_maintenance_updates":
            if not status_page_id or not change_id or not maintenance_id:
                return {"error": "status_page_id, change_id, and maintenance_id required"}
            try:
                resp = await api_get(
                    f"status_pages/{status_page_id}/maintenances/changes/{change_id}/{maintenance_id}/updates"
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list maintenance updates")

        if action == "create_maintenance_update":
            if not status_page_id or not change_id or not maintenance_id or not body:
                return {"error": "status_page_id, change_id, maintenance_id, and body required"}
            data = {"body": body}
            if update_status:
                data["status"] = update_status
            try:
                resp = await api_post(
                    f"status_pages/{status_page_id}/maintenances/changes/{change_id}/{maintenance_id}/updates",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "update": resp.json()}
            except Exception as e:
                return handle_error(e, "create maintenance update")

        if action == "update_maintenance_update":
            if not status_page_id or not change_id or not maintenance_id or not update_id:
                return {"error": "status_page_id, change_id, maintenance_id, and update_id required"}
            data = {}
            if body:
                data["body"] = body
            if update_status:
                data["status"] = update_status
            try:
                resp = await api_put(
                    f"status_pages/{status_page_id}/maintenances/changes/{change_id}/{maintenance_id}/updates/{update_id}",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "update": resp.json()}
            except Exception as e:
                return handle_error(e, "update maintenance update")

        if action == "delete_maintenance_update":
            if not status_page_id or not change_id or not maintenance_id or not update_id:
                return {"error": "status_page_id, change_id, maintenance_id, and update_id required"}
            try:
                resp = await api_delete(
                    f"status_pages/{status_page_id}/maintenances/changes/{change_id}/{maintenance_id}/updates/{update_id}"
                )
                if resp.status_code == 204:
                    return {"success": True, "message": "Maintenance update deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete maintenance update")

        # ── Maintenance Statuses ──
        if action == "list_maintenance_statuses":
            if not status_page_id:
                return {"error": "status_page_id required"}
            try:
                resp = await api_get(f"status_pages/{status_page_id}/maintenance_statuses")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list maintenance statuses")

        # ── Incidents — CRUD ──
        if action == "list_incidents":
            if not status_page_id:
                return {"error": "status_page_id required"}
            try:
                resp = await api_get(
                    f"status_pages/{status_page_id}/incidents",
                    params={"page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list incidents")

        if action == "create_incident":
            if not status_page_id or not title:
                return {"error": "status_page_id and title required for create_incident"}
            data = {"title": title}
            for k, v in [("description", description), ("start_time", start_time),
                         ("end_time", end_time), ("notification", notification)]:
                if v is not None:
                    data[k] = v
            if affected_services:
                data["affected_services"] = affected_services
            if is_private is not None:
                data["is_private"] = is_private
            try:
                resp = await api_post(f"status_pages/{status_page_id}/incidents", json=data)
                resp.raise_for_status()
                return {"success": True, "incident": resp.json()}
            except Exception as e:
                return handle_error(e, "create incident")

        if action == "get_incident":
            if not status_page_id or not incident_id:
                return {"error": "status_page_id and incident_id required"}
            try:
                resp = await api_get(f"status_pages/{status_page_id}/incidents/{incident_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get incident")

        if action == "update_incident":
            if not status_page_id or not incident_id:
                return {"error": "status_page_id and incident_id required"}
            data = {}
            for k, v in [("title", title), ("description", description),
                         ("start_time", start_time), ("end_time", end_time),
                         ("notification", notification)]:
                if v is not None:
                    data[k] = v
            if affected_services:
                data["affected_services"] = affected_services
            if is_private is not None:
                data["is_private"] = is_private
            try:
                resp = await api_put(f"status_pages/{status_page_id}/incidents/{incident_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "incident": resp.json()}
            except Exception as e:
                return handle_error(e, "update incident")

        if action == "delete_incident":
            if not status_page_id or not incident_id:
                return {"error": "status_page_id and incident_id required"}
            try:
                resp = await api_delete(f"status_pages/{status_page_id}/incidents/{incident_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Incident deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete incident")

        # ── Incident Updates ──
        if action == "list_incident_updates":
            if not status_page_id or not incident_id:
                return {"error": "status_page_id and incident_id required"}
            try:
                resp = await api_get(f"status_pages/{status_page_id}/incidents/{incident_id}/updates")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list incident updates")

        if action == "create_incident_update":
            if not status_page_id or not incident_id or not body:
                return {"error": "status_page_id, incident_id, and body required"}
            data = {"body": body}
            if update_status:
                data["status"] = update_status
            try:
                resp = await api_post(
                    f"status_pages/{status_page_id}/incidents/{incident_id}/updates",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "update": resp.json()}
            except Exception as e:
                return handle_error(e, "create incident update")

        if action == "update_incident_update":
            if not status_page_id or not incident_id or not update_id:
                return {"error": "status_page_id, incident_id, and update_id required"}
            data = {}
            if body:
                data["body"] = body
            if update_status:
                data["status"] = update_status
            try:
                resp = await api_put(
                    f"status_pages/{status_page_id}/incidents/{incident_id}/updates/{update_id}",
                    json=data,
                )
                resp.raise_for_status()
                return {"success": True, "update": resp.json()}
            except Exception as e:
                return handle_error(e, "update incident update")

        if action == "delete_incident_update":
            if not status_page_id or not incident_id or not update_id:
                return {"error": "status_page_id, incident_id, and update_id required"}
            try:
                resp = await api_delete(
                    f"status_pages/{status_page_id}/incidents/{incident_id}/updates/{update_id}"
                )
                if resp.status_code == 204:
                    return {"success": True, "message": "Incident update deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete incident update")

        # ── Incident Statuses ──
        if action == "list_incident_statuses":
            if not status_page_id:
                return {"error": "status_page_id required"}
            try:
                resp = await api_get(f"status_pages/{status_page_id}/incident_statuses")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list incident statuses")

        return {
            "error": f"Unknown action '{action}'. Valid: list_pages, list_components, "
            "get_component, list_maintenance, create_maintenance, get_maintenance, "
            "update_maintenance, delete_maintenance, list_maintenance_updates, "
            "create_maintenance_update, update_maintenance_update, delete_maintenance_update, "
            "list_maintenance_statuses, list_incidents, create_incident, get_incident, "
            "update_incident, delete_incident, list_incident_updates, create_incident_update, "
            "update_incident_update, delete_incident_update, list_incident_statuses"
        }
