"""
System Roles Definition — Single Source of Truth for Predefined Roles.

To add, edit, or configure system roles:
1. Update `SYSTEM_ROLES` in this file.
2. Run `python manage.py sync_roles` (or a deployment migration) to synchronize changes.
"""
from dataclasses import dataclass, field
from typing import Final, List, Tuple


class SystemRole:
    """
    Standard predefined system role codes.
    Always use these constants or exact uppercase strings for programmatic checks.
    """
    SUPER_ADMIN: Final[str] = "SUPER_ADMIN"
    ADMIN: Final[str] = "ADMIN"
    PROJECT_MANAGER: Final[str] = "PROJECT_MANAGER"
    DEVELOPER: Final[str] = "DEVELOPER"
    USER: Final[str] = "USER"

    ALL: Final[Tuple[str, ...]] = (
        SUPER_ADMIN,
        ADMIN,
        PROJECT_MANAGER,
        DEVELOPER,
        USER,
    )


@dataclass(frozen=True)
class RoleDefinition:
    """Schema for a system-defined role."""
    code: str
    name: str
    description: str
    is_system: bool = True
    permissions: Tuple[str, ...] = field(default_factory=tuple)


# The canonical list of all system roles and their default permission definitions.
SYSTEM_ROLES: Tuple[RoleDefinition, ...] = (
    RoleDefinition(
        code=SystemRole.SUPER_ADMIN,
        name="Super Administrator",
        description="Full system administration, configuration management, and user lifecycle control.",
        is_system=True,
        permissions=(),
    ),
    RoleDefinition(
        code=SystemRole.ADMIN,
        name="Administrator",
        description="General administrative access for day-to-day operations and staff management.",
        is_system=True,
        permissions=(),
    ),
    RoleDefinition(
        code=SystemRole.PROJECT_MANAGER,
        name="Project Manager",
        description="Management of projects, team assignments, deliverables, and workflow status.",
        is_system=True,
        permissions=(),
    ),
    RoleDefinition(
        code=SystemRole.DEVELOPER,
        name="Developer",
        description="Technical and development access for building, integrating, and reviewing features.",
        is_system=True,
        permissions=(),
    ),
    RoleDefinition(
        code=SystemRole.USER,
        name="Standard User",
        description="Default authenticated user with standard self-service privileges.",
        is_system=True,
        permissions=(),
    ),
)


# Dictionary list for backward-compatibility with existing seed migrations and scripts
DEFAULT_SYSTEM_ROLES = [
    {
        "code": r.code,
        "name": r.name,
        "description": r.description,
        "is_system": r.is_system,
        "permissions": list(r.permissions),
    }
    for r in SYSTEM_ROLES
]
