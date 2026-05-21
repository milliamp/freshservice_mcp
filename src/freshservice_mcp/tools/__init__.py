"""Freshservice MCP — tools package.

Each sub-module exposes a ``register_*_tools(mcp)`` function.
"""

from .agents import register_agents_tools
from .announcements import register_announcements_tools
from .assets import register_assets_tools
from .changes import register_changes_tools
from .contracts import register_contracts_tools
from .custom_objects import register_custom_objects_tools
from .departments import register_department_tools
from .locations import register_locations_tools
from .misc import register_misc_tools
from .problems import register_problem_tools
from .procurement import register_procurement_tools
from .products import register_products_tools
from .projects import register_project_tools
from .releases import register_release_tools
from .requesters import register_requesters_tools
from .software import register_software_tools
from .solutions import register_solutions_tools
from .status_page import register_status_page_tools
from .tickets import register_tickets_tools

# Mapping from scope name → registration function.
# Used by server.py to selectively load tool modules.
SCOPE_REGISTRY: dict[str, callable] = {
    "tickets": register_tickets_tools,
    "changes": register_changes_tools,
    "assets": register_assets_tools,
    "agents": register_agents_tools,
    "requesters": register_requesters_tools,
    "solutions": register_solutions_tools,
    "products": register_products_tools,
    "problems": register_problem_tools,
    "releases": register_release_tools,
    "departments": register_department_tools,
    "projects": register_project_tools,
    "status_page": register_status_page_tools,
    "software": register_software_tools,
    "procurement": register_procurement_tools,
    "misc": register_misc_tools,
    "locations": register_locations_tools,
    "contracts": register_contracts_tools,
    "announcements": register_announcements_tools,
    "custom_objects": register_custom_objects_tools,
}

__all__ = [
    "SCOPE_REGISTRY",
    "register_agents_tools",
    "register_announcements_tools",
    "register_assets_tools",
    "register_changes_tools",
    "register_contracts_tools",
    "register_custom_objects_tools",
    "register_department_tools",
    "register_locations_tools",
    "register_misc_tools",
    "register_problem_tools",
    "register_procurement_tools",
    "register_products_tools",
    "register_project_tools",
    "register_release_tools",
    "register_requesters_tools",
    "register_software_tools",
    "register_solutions_tools",
    "register_status_page_tools",
    "register_tickets_tools",
]
