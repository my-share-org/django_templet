"""
Role and Permission authorization service.
Provides reusable, deterministic authorization functions and effective permission calculations.
"""
from typing import Any, Iterable, Set, Union
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ObjectDoesNotExist
from authentication.models import Role, UserRole


def _normalize_role_code(role: Union[str, Role]) -> str:
    """Extract and validate normalized role code from string or Role model."""
    if isinstance(role, Role):
        return role.code.strip().upper()
    if isinstance(role, str):
        cleaned = role.strip().upper()
        if not cleaned:
            raise ValueError("Role code cannot be empty.")
        return cleaned
    raise TypeError(f"Role must be a string or Role instance, got {type(role).__name__}.")


def _normalize_permission_code(perm: Union[str, Permission]) -> str:
    """Extract and validate permission string in 'app_label.codename' format."""
    if isinstance(perm, Permission):
        return f"{perm.content_type.app_label}.{perm.codename}"
    if isinstance(perm, str):
        cleaned = perm.strip()
        if not cleaned or "." not in cleaned:
            raise ValueError(
                f"Permission must be in 'app_label.codename' format, got '{perm}'."
            )
        return cleaned
    raise TypeError(f"Permission must be a string or Permission instance, got {type(perm).__name__}.")


def clear_permission_cache(user: Any) -> None:
    """
    Clears all in-memory permission and role caches for the specified user.
    """
    if user is None:
        return
    for attr in (
        "_cached_role_codes",
        "_cached_effective_permissions",
        "_role_perm_cache",
        "_perm_cache",
        "_user_perm_cache",
        "_group_perm_cache",
    ):
        if hasattr(user, attr):
            try:
                delattr(user, attr)
            except AttributeError:
                pass


def get_user_roles(user: Any) -> Set[str]:
    """
    Returns the set of active role codes assigned to the user.
    Caches result on the user instance for the request lifetime.
    Soft-deleted roles and soft-deleted assignments are excluded.
    """
    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return set()

    if not hasattr(user, "_cached_role_codes"):
        active_codes = set(
            Role.objects.filter(
                user_roles__user=user,
                user_roles__deleted_at__isnull=True,
                deleted_at__isnull=True,
            ).values_list("code", flat=True)
        )
        user._cached_role_codes = active_codes

    return user._cached_role_codes


def get_user_effective_permissions(user: Any) -> Set[str]:
    """
    Calculates the complete set of effective permissions ('app_label.codename')
    additively combined across:
    1. Direct user permissions
    2. Direct user groups' permissions
    3. Permissions assigned directly to the user's active roles
    4. Permissions from groups assigned to the user's active roles
    """
    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return set()

    if hasattr(user, "_role_perm_cache"):
        return user._role_perm_cache

    if not hasattr(user, "_cached_effective_permissions"):
        # 1. Direct user permissions
        user_perms = set(
            user.user_permissions.values_list(
                "content_type__app_label", "codename"
            )
        )

        # 2. Permissions from user groups
        user_group_perms = set(
            Permission.objects.filter(
                group__user=user
            ).values_list("content_type__app_label", "codename")
        )

        # 3. Permissions assigned directly to active roles
        role_direct_perms = set(
            Permission.objects.filter(
                roles__user_roles__user=user,
                roles__user_roles__deleted_at__isnull=True,
                roles__deleted_at__isnull=True,
            ).values_list("content_type__app_label", "codename")
        )

        # 4. Permissions from groups assigned to active roles
        role_group_perms = set(
            Permission.objects.filter(
                group__roles__user_roles__user=user,
                group__roles__user_roles__deleted_at__isnull=True,
                group__roles__deleted_at__isnull=True,
            ).values_list("content_type__app_label", "codename")
        )

        combined = user_perms | user_group_perms | role_direct_perms | role_group_perms
        perms_set = {f"{app}.{code}" for app, code in combined}
        user._cached_effective_permissions = perms_set
        user._role_perm_cache = perms_set

    return user._cached_effective_permissions



# =========================================================================
# Public Role-Checking Functions
# =========================================================================

def has_role(user: Any, role: Union[str, Role]) -> bool:
    """
    Returns True if the authenticated, active user has the specified role.
    Unauthenticated or inactive users always return False.
    """
    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    try:
        code = _normalize_role_code(role)
    except (TypeError, ValueError):
        return False

    return code in get_user_roles(user)


def has_any_role(user: Any, roles: Iterable[Union[str, Role]]) -> bool:
    """
    Returns True if the user has at least one of the specified roles.
    Empty collections return False (never grant access for empty input).
    """
    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    if not roles:
        return False

    normalized_codes = set()
    for r in roles:
        try:
            normalized_codes.add(_normalize_role_code(r))
        except (TypeError, ValueError):
            continue

    if not normalized_codes:
        return False

    user_roles = get_user_roles(user)
    return bool(user_roles & normalized_codes)


def has_all_roles(user: Any, roles: Iterable[Union[str, Role]]) -> bool:
    """
    Returns True if the user has ALL of the specified roles.
    Empty collections return False (never grant access for empty input).
    """
    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    if not roles:
        return False

    normalized_codes = set()
    for r in roles:
        try:
            normalized_codes.add(_normalize_role_code(r))
        except (TypeError, ValueError):
            return False

    if not normalized_codes:
        return False

    user_roles = get_user_roles(user)
    return normalized_codes.issubset(user_roles)


# =========================================================================
# Public Permission-Checking Functions
# =========================================================================

def has_permission(user: Any, permission: Union[str, Permission], obj: Any = None) -> bool:
    """
    Returns True if the user possesses the specified permission through any supported source:
    - Direct user permission
    - User group permission
    - Role permission
    - Role group permission
    Superusers automatically have all permissions (Django standard policy).
    Unauthenticated or inactive users always return False.
    """
    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    try:
        perm_code = _normalize_permission_code(permission)
    except (TypeError, ValueError):
        return False

    return perm_code in get_user_effective_permissions(user)


def has_any_permission(user: Any, permissions: Iterable[Union[str, Permission]], obj: Any = None) -> bool:
    """
    Returns True if the user has at least one of the specified permissions.
    Empty collections return False (never grant access for empty input).
    """
    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    if not permissions:
        return False

    if getattr(user, "is_superuser", False):
        return True

    normalized_perms = set()
    for p in permissions:
        try:
            normalized_perms.add(_normalize_permission_code(p))
        except (TypeError, ValueError):
            continue

    if not normalized_perms:
        return False

    effective = get_user_effective_permissions(user)
    return bool(effective & normalized_perms)


def has_all_permissions(user: Any, permissions: Iterable[Union[str, Permission]], obj: Any = None) -> bool:
    """
    Returns True if the user possesses ALL of the specified permissions.
    Empty collections return False (never grant access for empty input).
    """
    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    if not permissions:
        return False

    if getattr(user, "is_superuser", False):
        return True

    normalized_perms = set()
    for p in permissions:
        try:
            normalized_perms.add(_normalize_permission_code(p))
        except (TypeError, ValueError):
            return False

    if not normalized_perms:
        return False

    effective = get_user_effective_permissions(user)
    return normalized_perms.issubset(effective)


# =========================================================================
# Role & Permission Assignment Services (with Cache Invalidation)
# =========================================================================

def assign_role(user: Any, role: Union[str, Role]) -> UserRole:
    """
    Assigns a role to a user and clears relevant permission caches.
    Safely handles re-assignment of soft-deleted roles without IntegrityError.
    """
    if isinstance(role, str):
        role_obj = Role.objects.get(code=role.strip().upper(), deleted_at__isnull=True)
    else:
        role_obj = role

    user_role = UserRole.all_objects.filter(user=user, role=role_obj).first()
    if user_role:
        if user_role.deleted_at is not None:
            user_role.restore()
    else:
        user_role = UserRole.objects.create(user=user, role=role_obj)

    clear_permission_cache(user)
    return user_role


def remove_role(user: Any, role: Union[str, Role]) -> bool:
    """
    Removes a role from a user and clears relevant permission caches.
    """
    if isinstance(role, str):
        role_filter = {"role__code": role.strip().upper()}
    else:
        role_filter = {"role": role}

    deleted_count, _ = UserRole.objects.filter(user=user, **role_filter).delete()
    clear_permission_cache(user)
    return deleted_count > 0


def assign_permission_to_role(role: Role, permission: Union[str, Permission]) -> Permission:
    """
    Adds a permission to a role.
    """
    if isinstance(permission, str):
        clean_perm = _normalize_permission_code(permission)
        app_label, codename = clean_perm.split(".", 1)
        perm_obj = Permission.objects.get(
            content_type__app_label=app_label, codename=codename
        )
    else:
        perm_obj = permission

    role.permissions.add(perm_obj)
    return perm_obj


def remove_permission_from_role(role: Role, permission: Union[str, Permission]) -> bool:
    """
    Removes a permission from a role.
    """
    if isinstance(permission, str):
        clean_perm = _normalize_permission_code(permission)
        app_label, codename = clean_perm.split(".", 1)
        perm_obj = Permission.objects.get(
            content_type__app_label=app_label, codename=codename
        )
    else:
        perm_obj = permission

    role.permissions.remove(perm_obj)
    return True


def assign_group_to_role(role: Role, group: Group) -> None:
    """
    Assigns a permission group to a role.
    """
    role.groups.add(group)


def remove_group_from_role(role: Role, group: Group) -> None:
    """
    Removes a permission group from a role.
    """
    role.groups.remove(group)

