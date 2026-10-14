"""
System-defined role constants and predefined role definitions.
Maintains backward-compatibility by re-exporting definitions from system_roles.py.
"""
from authentication.system_roles import (
    DEFAULT_SYSTEM_ROLES,
    RoleDefinition,
    SYSTEM_ROLES,
    SystemRole,
)

__all__ = [
    "SystemRole",
    "RoleDefinition",
    "SYSTEM_ROLES",
    "DEFAULT_SYSTEM_ROLES",
]
