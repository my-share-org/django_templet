"""
Role synchronization service.
Synchronizes database system roles with the code-defined single source of truth in system_roles.py.
"""
from typing import Any, Dict, List, Optional
from django.contrib.auth.models import Permission
from django.db import transaction

from authentication.models import Role, UserRole
from authentication.services.permissions import clear_permission_cache
from authentication.system_roles import SYSTEM_ROLES, RoleDefinition


def sync_system_roles(
    prune: bool = False,
    dry_run: bool = False,
    role_definitions: Optional[List[RoleDefinition]] = None,
) -> Dict[str, Any]:
    """
    Synchronizes Role database records with system role definitions.

    Actions:
    - Creates missing system roles.
    - Updates names, descriptions, and system flags on existing roles.
    - Attaches default permissions specified in role definitions.
    - If prune=True, safely soft-deletes obsolete system roles that are no longer defined.
      (Active user assignments are protected).
    - Invalidates caches for any affected users.

    Returns a summary dictionary of actions taken.
    """
    definitions = role_definitions or list(SYSTEM_ROLES)
    summary: Dict[str, List[str]] = {
        "created": [],
        "updated": [],
        "unchanged": [],
        "pruned": [],
        "protected_from_prune": [],
        "obsolete_unpruned": [],
    }

    defined_codes = set()

    with transaction.atomic():
        for defn in definitions:
            code = defn.code.strip().upper()
            defined_codes.add(code)

            role = Role.all_objects.filter(code=code).first()

            if not role:
                if not dry_run:
                    role = Role.objects.create(
                        code=code,
                        name=defn.name,
                        description=defn.description,
                        is_system=True,
                    )
                    _sync_role_permissions(role, defn.permissions)
                summary["created"].append(code)
            else:
                needs_save = False
                # Check for changes
                if role.name != defn.name:
                    role.name = defn.name
                    needs_save = True
                if role.description != defn.description:
                    role.description = defn.description
                    needs_save = True
                if not role.is_system:
                    role.is_system = True
                    needs_save = True
                if role.deleted_at is not None:
                    role.deleted_at = None
                    needs_save = True

                perms_changed = False
                if not dry_run:
                    perms_changed = _sync_role_permissions(role, defn.permissions)

                if needs_save or perms_changed:
                    if not dry_run:
                        role.save()
                        # Invalidate cache for users holding this role
                        for u in role.users.all():
                            clear_permission_cache(u)
                    summary["updated"].append(code)
                else:
                    summary["unchanged"].append(code)

        # Handle roles in DB with is_system=True that are no longer defined
        db_system_roles = Role.objects.filter(is_system=True).exclude(code__in=defined_codes)

        for obsolete_role in db_system_roles:
            active_assignments = UserRole.objects.filter(
                role=obsolete_role, deleted_at__isnull=True
            ).count()

            if prune:
                if active_assignments > 0:
                    # Protect role with active users — soft delete instead of hard delete
                    if not dry_run:
                        obsolete_role.soft_delete()
                        for u in obsolete_role.users.all():
                            clear_permission_cache(u)
                    summary["protected_from_prune"].append(
                        f"{obsolete_role.code} (soft-deleted, {active_assignments} active user assignment(s))"
                    )
                else:
                    if not dry_run:
                        obsolete_role.is_system = False
                        obsolete_role.save(update_fields=["is_system"])
                        obsolete_role.delete()
                    summary["pruned"].append(obsolete_role.code)
            else:
                summary["obsolete_unpruned"].append(
                    f"{obsolete_role.code} ({active_assignments} active user assignment(s))"
                )

        if dry_run:
            transaction.set_rollback(True)

    return summary


def _sync_role_permissions(role: Role, permission_codes: tuple) -> bool:
    """Attaches default permissions to a role if not already present."""
    if not permission_codes:
        return False

    changed = False
    for perm_str in permission_codes:
        if "." in perm_str:
            app_label, codename = perm_str.split(".", 1)
            perm_obj = Permission.objects.filter(
                content_type__app_label=app_label, codename=codename
            ).first()
            if perm_obj and not role.permissions.filter(pk=perm_obj.pk).exists():
                role.permissions.add(perm_obj)
                changed = True
    return changed
