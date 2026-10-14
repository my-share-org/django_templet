"""
Signals for the authentication app.
Maintains permission cache integrity by invalidating user permission/role caches
whenever user permissions, groups, roles, or assignments change.
"""
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from authentication.models import Role, User, UserRole
from authentication.services.permissions import clear_permission_cache


@receiver([post_save, post_delete], sender=UserRole)
def invalidate_user_role_cache(sender, instance, **kwargs):
    """Invalidates cache when a user role assignment is created, saved, or deleted."""
    if instance and instance.user:
        clear_permission_cache(instance.user)


@receiver([post_save, post_delete], sender=Role)
def invalidate_role_cache(sender, instance, **kwargs):
    """
    Hook for role-level updates.
    Note: Multi-user role cache invalidation should rely on request-scoped lifecycles
    or a global role version key (O(1)) rather than synchronously looping millions of users.
    """
    pass


@receiver(m2m_changed, sender=User.user_permissions.through)
def invalidate_user_permissions_m2m(sender, instance, **kwargs):
    """Invalidates cache when direct user permissions change."""
    if isinstance(instance, User):
        clear_permission_cache(instance)


@receiver(m2m_changed, sender=User.groups.through)
def invalidate_user_groups_m2m(sender, instance, **kwargs):
    """Invalidates cache when user groups change."""
    if isinstance(instance, User):
        clear_permission_cache(instance)


@receiver(m2m_changed, sender=Role.permissions.through)
def invalidate_role_permissions_m2m(sender, instance, **kwargs):
    """Hook for role-permission relation changes."""
    pass


@receiver(m2m_changed, sender=Role.groups.through)
def invalidate_role_groups_m2m(sender, instance, **kwargs):
    """Hook for role-group relation changes."""
    pass

