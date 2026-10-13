"""
System-defined role constants and predefined role definitions.
"""
from typing import Final


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

    ALL: Final[tuple[str, ...]] = (
        SUPER_ADMIN,
        ADMIN,
        PROJECT_MANAGER,
        DEVELOPER,
        USER,
    )


DEFAULT_SYSTEM_ROLES = [
    {
        "code": SystemRole.SUPER_ADMIN,
        "name": "Super Administrator",
        "description": "Full system administration and global operational control.",
        "is_system": True,
    },
    {
        "code": SystemRole.ADMIN,
        "name": "Administrator",
        "description": "General system administration and user management.",
        "is_system": True,
    },
    {
        "code": SystemRole.PROJECT_MANAGER,
        "name": "Project Manager",
        "description": "Management of projects, deliverables, and team assignments.",
        "is_system": True,
    },
    {
        "code": SystemRole.DEVELOPER,
        "name": "Developer",
        "description": "Developer-level access for building and reviewing deliverables.",
        "is_system": True,
    },
    {
        "code": SystemRole.USER,
        "name": "Standard User",
        "description": "Standard authenticated user with basic permissions.",
        "is_system": True,
    },
]
