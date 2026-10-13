"""
Authentication and authorization backends.
Extends Django's ModelBackend to include Role-based and Role-Group-based permissions in user.has_perm().
"""
from typing import Set
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission


class RolePermissionBackend(ModelBackend):
    """
    Custom authorization backend that calculates effective permissions across:
    1. Direct user permissions (User.user_permissions)
    2. User group permissions (User.groups.permissions)
    3. Role direct permissions (User.roles.permissions)
    4. Role group permissions (User.roles.groups.permissions)
    """

    def get_role_permissions(self, user_obj, obj=None) -> Set[str]:
        """
        Return permissions granted directly to roles assigned to the user.
        Excludes soft-deleted roles and soft-deleted assignments.
        """
        if not user_obj.is_authenticated or not user_obj.is_active:
            return set()

        perms = (
            Permission.objects.filter(
                roles__user_roles__user=user_obj,
                roles__user_roles__deleted_at__isnull=True,
                roles__deleted_at__isnull=True,
            )
            .values_list("content_type__app_label", "codename")
            .distinct()
        )
        return {f"{app_label}.{codename}" for app_label, codename in perms}

    def get_role_group_permissions(self, user_obj, obj=None) -> Set[str]:
        """
        Return permissions granted to groups associated with the user's active roles.
        Excludes soft-deleted roles and soft-deleted assignments.
        """
        if not user_obj.is_authenticated or not user_obj.is_active:
            return set()

        perms = (
            Permission.objects.filter(
                group__roles__user_roles__user=user_obj,
                group__roles__user_roles__deleted_at__isnull=True,
                group__roles__deleted_at__isnull=True,
            )
            .values_list("content_type__app_label", "codename")
            .distinct()
        )
        return {f"{app_label}.{codename}" for app_label, codename in perms}

    def get_all_permissions(self, user_obj, obj=None) -> Set[str]:
        """
        Calculates all effective permissions additively from all four supported sources:
        1. Direct user permissions
        2. Direct user groups
        3. Role direct permissions
        4. Role group permissions
        """
        if not user_obj.is_authenticated or not user_obj.is_active:
            return set()

        if not hasattr(user_obj, "_role_perm_cache"):
            user_perms = self.get_user_permissions(user_obj, obj)
            group_perms = self.get_group_permissions(user_obj, obj)
            role_perms = self.get_role_permissions(user_obj, obj)
            role_group_perms = self.get_role_group_permissions(user_obj, obj)

            user_obj._role_perm_cache = (
                user_perms | group_perms | role_perms | role_group_perms
            )

        return user_obj._role_perm_cache

    def has_perm(self, user_obj, perm, obj=None) -> bool:
        if not user_obj.is_authenticated or not user_obj.is_active:
            return False
        if user_obj.is_superuser:
            return True
        return perm in self.get_all_permissions(user_obj, obj)
