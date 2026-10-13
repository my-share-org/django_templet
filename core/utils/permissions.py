"""
Shared authorization utilities and DRF permission classes.
Provides reusable public authorization checking functions and DRF integrations.
"""
from typing import Any, Iterable, Optional, Sequence, Union
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from authentication.services.permissions import (
    clear_permission_cache,
    get_user_effective_permissions,
    get_user_roles,
    has_all_permissions,
    has_all_roles,
    has_any_permission,
    has_any_role,
    has_permission,
    has_role,
)

__all__ = [
    "has_role",
    "has_any_role",
    "has_all_roles",
    "has_permission",
    "has_any_permission",
    "has_all_permissions",
    "get_user_roles",
    "get_user_effective_permissions",
    "clear_permission_cache",
    "check_object_permission",
    "HasRole",
    "HasPermission",
    "AuthorizePermission",
]


def check_object_permission(
    user: Any,
    permission: str,
    obj: Any,
    backend: Optional[Any] = None,
) -> bool:
    """
    Evaluates object-level authorization for a specific record.
    If the object has an `is_accessible_by(user)` or similar check, it is evaluated.
    Otherwise checks user.has_perm(permission, obj).
    """
    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    if getattr(user, "is_superuser", False):
        return True

    # 1. Custom model-level object permission hook
    if hasattr(obj, "has_object_permission"):
        return bool(obj.has_object_permission(user, permission))

    # 2. Standard ownership / user-field check on object
    if hasattr(obj, "user_id") and getattr(obj, "user_id") == getattr(user, "id", None):
        return True
    if hasattr(obj, "user") and getattr(obj, "user") == user:
        return True

    # 3. Standard Django has_perm with obj
    return user.has_perm(permission, obj)


class HasRole(BasePermission):
    """
    DRF permission class that validates user roles.

    Usage:
        permission_classes = [HasRole("SUPER_ADMIN")]
        permission_classes = [HasRole("PROJECT_MANAGER", "DEVELOPER", require_all=False)]
    """
    message = "You do not have the required role to access this resource."

    def __init__(self, *roles: str, require_all: bool = False):
        self.roles = list(roles)
        self.require_all = require_all

    def __call__(self):
        return self

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if not self.roles:
            return False

        if self.require_all:
            return has_all_roles(user, self.roles)
        return has_any_role(user, self.roles)


class HasPermission(BasePermission):
    """
    DRF permission class that validates user effective permissions.

    Usage:
        permission_classes = [HasPermission("projects.view_project")]
        permission_classes = [HasPermission("projects.view_project", "projects.change_project", require_all=True)]
    """
    message = "You do not have the required permission to perform this action."

    def __init__(self, *permissions: str, require_all: bool = True):
        self.permissions = list(permissions)
        self.require_all = require_all

    def __call__(self):
        return self

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if not self.permissions:
            return False

        if self.require_all:
            return has_all_permissions(user, self.permissions)
        return has_any_permission(user, self.permissions)


class AuthorizePermission(BasePermission):
    """
    Comprehensive DRF permission class supporting combined Role and Permission policies
    with configurable logical operators (AND / OR).

    Usage:
        permission_classes = [AuthorizePermission(roles=["ADMIN"], permissions=["projects.view_project"], operator="AND")]
        permission_classes = [AuthorizePermission(roles=["SUPER_ADMIN"], permissions=["projects.view_project"], operator="OR")]
    """
    message = "You are not authorized to perform this action."

    def __init__(
        self,
        roles: Optional[Sequence[str]] = None,
        permissions: Optional[Sequence[str]] = None,
        operator: str = "AND",
        require_all_roles: bool = False,
        require_all_permissions: bool = True,
    ):
        op = operator.strip().upper()
        if op not in ("AND", "OR"):
            raise ValueError(f"Invalid operator '{operator}'. Must be 'AND' or 'OR'.")

        self.roles = list(roles) if roles else []
        self.permissions = list(permissions) if permissions else []
        self.operator = op
        self.require_all_roles = require_all_roles
        self.require_all_permissions = require_all_permissions

        if not self.roles and not self.permissions:
            raise ValueError(
                "AuthorizePermission requires at least one role or permission specification."
            )

    def __call__(self):
        return self

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or not user.is_active:
            return False

        role_passed = None
        if self.roles:
            if self.require_all_roles:
                role_passed = has_all_roles(user, self.roles)
            else:
                role_passed = has_any_role(user, self.roles)

        perm_passed = None
        if self.permissions:
            if self.require_all_permissions:
                perm_passed = has_all_permissions(user, self.permissions)
            else:
                perm_passed = has_any_permission(user, self.permissions)

        if role_passed is not None and perm_passed is not None:
            if self.operator == "OR":
                return role_passed or perm_passed
            return role_passed and perm_passed

        if role_passed is not None:
            return role_passed
        if perm_passed is not None:
            return perm_passed

        return False
