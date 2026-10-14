import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from authentication.models import Role, UserRole
from authentication.roles import SystemRole
from authentication.services.permissions import (
    assign_group_to_role,
    assign_permission_to_role,
    assign_role,
    clear_permission_cache,
    get_user_effective_permissions,
    get_user_roles,
    has_all_permissions,
    has_all_roles,
    has_any_permission,
    has_any_role,
    has_permission,
    has_role,
    remove_group_from_role,
    remove_permission_from_role,
    remove_role,
)
from core.utils.permissions import check_object_permission

User = get_user_model()


@pytest.fixture
def sample_permission():
    ct = ContentType.objects.get_for_model(User)
    perm, _ = Permission.objects.get_or_create(
        codename="view_custom_project",
        content_type=ct,
        defaults={"name": "Can view custom project"},
    )
    return perm


@pytest.fixture
def sample_permission_two():
    ct = ContentType.objects.get_for_model(User)
    perm, _ = Permission.objects.get_or_create(
        codename="change_custom_project",
        content_type=ct,
        defaults={"name": "Can change custom project"},
    )
    return perm


@pytest.fixture
def sample_permission_three():
    ct = ContentType.objects.get_for_model(User)
    perm, _ = Permission.objects.get_or_create(
        codename="delete_custom_project",
        content_type=ct,
        defaults={"name": "Can delete custom project"},
    )
    return perm


@pytest.mark.unit
@pytest.mark.django_db
class TestRoleAndUserRoleModels:
    def test_role_creation_and_normalization(self):
        role = Role(code="qa_engineer", name="QA Engineer")
        role.full_clean()
        role.save()

        assert role.id is not None
        assert role.code == "QA_ENGINEER"
        assert role.name == "QA Engineer"
        assert "QA Engineer (QA_ENGINEER)" in str(role)

    def test_role_code_invalid_characters_raises_validation_error(self):
        role = Role(code="INVALID-CODE!", name="Invalid")
        with pytest.raises(ValidationError):
            role.full_clean()

    def test_system_role_cannot_be_deleted(self):
        system_role = Role.objects.get(code=SystemRole.SUPER_ADMIN)
        assert system_role.is_system is True

        with pytest.raises(ValidationError, match="System-defined roles cannot be deleted"):
            system_role.delete()

    def test_system_role_code_cannot_be_mutated(self):
        system_role = Role.objects.get(code=SystemRole.SUPER_ADMIN)
        system_role.code = "CHANGED_CODE"
        with pytest.raises(ValidationError, match="System role code cannot be modified"):
            system_role.clean()

    def test_user_role_through_model_and_uniqueness(self, test_user):
        role = Role.objects.get(code=SystemRole.PROJECT_MANAGER)
        ur = UserRole.objects.create(user=test_user, role=role)

        assert ur.pk is not None
        assert str(test_user) in str(ur)

        with pytest.raises((IntegrityError, ValidationError)):
            UserRole.objects.create(user=test_user, role=role)

    def test_system_role_cannot_be_soft_deleted(self):
        system_role = Role.objects.get(code=SystemRole.SUPER_ADMIN)
        with pytest.raises(ValidationError, match="System-defined roles cannot be soft-deleted"):
            system_role.soft_delete()

    def test_role_save_normalizes_code_without_clean(self):
        role = Role.objects.create(code="analyst_code", name="Analyst")
        assert role.code == "ANALYST_CODE"

    def test_role_save_blocks_system_role_code_mutation(self):
        system_role = Role.objects.get(code=SystemRole.SUPER_ADMIN)
        system_role.code = "CHANGED_CODE"
        with pytest.raises(ValidationError, match="System role code cannot be modified"):
            system_role.save()

    def test_soft_deleted_user_role_reassignment_restores_cleanly(self, test_user):
        role = Role.objects.get(code=SystemRole.DEVELOPER)
        ur = assign_role(test_user, role)
        assert ur.deleted_at is None

        # Soft delete the assignment
        ur.soft_delete()
        assert ur.deleted_at is not None
        assert UserRole.objects.filter(user=test_user, role=role).count() == 0

        # Re-assigning should restore the soft-deleted row without IntegrityError
        ur_reassigned = assign_role(test_user, role)
        assert ur_reassigned.pk == ur.pk
        assert ur_reassigned.deleted_at is None
        assert UserRole.objects.filter(user=test_user, role=role).count() == 1

    def test_soft_delete_and_restore_role(self, test_user):
        role = Role.objects.create(code="TEMP_ROLE", name="Temporary Role")
        assign_role(test_user, role)

        assert has_role(test_user, "TEMP_ROLE") is True

        # Soft delete the role
        role.soft_delete()
        clear_permission_cache(test_user)

        assert has_role(test_user, "TEMP_ROLE") is False

        # Restore role
        role.restore()
        clear_permission_cache(test_user)

        assert has_role(test_user, "TEMP_ROLE") is True



@pytest.mark.unit
@pytest.mark.django_db
class TestRoleAuthorizationFunctions:
    def test_single_role_check_positive_and_negative(self, test_user):
        role = Role.objects.get(code=SystemRole.DEVELOPER)
        assign_role(test_user, role)

        assert has_role(test_user, "DEVELOPER") is True
        assert has_role(test_user, "developer") is True  # case-insensitive
        assert has_role(test_user, role) is True  # instance support
        assert has_role(test_user, "SUPER_ADMIN") is False

    def test_has_any_role(self, test_user):
        assign_role(test_user, SystemRole.DEVELOPER)

        assert has_any_role(test_user, ["DEVELOPER", "SUPER_ADMIN"]) is True
        assert has_any_role(test_user, ["SUPER_ADMIN", "ADMIN"]) is False

    def test_has_all_roles(self, test_user):
        assign_role(test_user, SystemRole.DEVELOPER)
        assign_role(test_user, SystemRole.PROJECT_MANAGER)

        assert has_all_roles(test_user, ["DEVELOPER", "PROJECT_MANAGER"]) is True
        assert has_all_roles(test_user, ["DEVELOPER", "PROJECT_MANAGER", "SUPER_ADMIN"]) is False

    def test_empty_role_collection_returns_false(self, test_user):
        assign_role(test_user, SystemRole.DEVELOPER)

        assert has_any_role(test_user, []) is False
        assert has_all_roles(test_user, []) is False
        assert has_any_role(test_user, None) is False
        assert has_all_roles(test_user, None) is False

    def test_unauthenticated_or_inactive_user_never_has_role(self, test_user):
        assign_role(test_user, SystemRole.DEVELOPER)

        assert has_role(None, "DEVELOPER") is False
        assert has_role(AnonymousUser(), "DEVELOPER") is False

        test_user.is_active = False
        test_user.save()
        clear_permission_cache(test_user)

        assert has_role(test_user, "DEVELOPER") is False
        assert has_any_role(test_user, ["DEVELOPER"]) is False
        assert has_all_roles(test_user, ["DEVELOPER"]) is False

    def test_user_without_roles_returns_false(self, test_user):
        assert has_role(test_user, "DEVELOPER") is False
        assert has_any_role(test_user, ["DEVELOPER"]) is False
        assert has_all_roles(test_user, ["DEVELOPER"]) is False

    def test_unknown_role_code_handled_safely(self, test_user):
        assign_role(test_user, SystemRole.DEVELOPER)

        assert has_role(test_user, "NON_EXISTENT_ROLE") is False
        assert has_role(test_user, "") is False
        assert has_role(test_user, 12345) is False


@pytest.mark.unit
@pytest.mark.django_db
class TestEffectivePermissionCalculations:
    def test_direct_user_permission(self, test_user, sample_permission):
        perm_code = f"{sample_permission.content_type.app_label}.{sample_permission.codename}"
        assert has_permission(test_user, perm_code) is False

        test_user.user_permissions.add(sample_permission)
        clear_permission_cache(test_user)

        assert has_permission(test_user, perm_code) is True
        assert has_permission(test_user, sample_permission) is True

    def test_permission_inherited_from_user_groups(self, test_user, sample_permission):
        perm_code = f"{sample_permission.content_type.app_label}.{sample_permission.codename}"
        group = Group.objects.create(name="Project Contributors")
        group.permissions.add(sample_permission)

        test_user.groups.add(group)
        clear_permission_cache(test_user)

        assert has_permission(test_user, perm_code) is True

    def test_permission_inherited_from_roles(self, test_user, sample_permission):
        perm_code = f"{sample_permission.content_type.app_label}.{sample_permission.codename}"
        role = Role.objects.get(code=SystemRole.PROJECT_MANAGER)
        assign_permission_to_role(role, sample_permission)
        assign_role(test_user, role)

        assert has_permission(test_user, perm_code) is True

    def test_permission_inherited_from_role_assigned_groups(
        self, test_user, sample_permission
    ):
        perm_code = f"{sample_permission.content_type.app_label}.{sample_permission.codename}"
        group = Group.objects.create(name="Core Reviewers")
        group.permissions.add(sample_permission)

        role = Role.objects.get(code=SystemRole.DEVELOPER)
        assign_group_to_role(role, group)
        assign_role(test_user, role)

        assert has_permission(test_user, perm_code) is True

    def test_additive_combination_across_all_four_sources(
        self, test_user, sample_permission, sample_permission_two, sample_permission_three
    ):
        p1 = f"{sample_permission.content_type.app_label}.{sample_permission.codename}"
        p2 = f"{sample_permission_two.content_type.app_label}.{sample_permission_two.codename}"
        p3 = f"{sample_permission_three.content_type.app_label}.{sample_permission_three.codename}"

        # Source 1: Direct user perm
        test_user.user_permissions.add(sample_permission)

        # Source 2: Direct user group
        g1 = Group.objects.create(name="Group A")
        g1.permissions.add(sample_permission_two)
        test_user.groups.add(g1)

        # Source 3: Role direct perm
        role = Role.objects.get(code=SystemRole.PROJECT_MANAGER)
        assign_permission_to_role(role, sample_permission_three)
        assign_role(test_user, role)

        effective = get_user_effective_permissions(test_user)
        assert p1 in effective
        assert p2 in effective
        assert p3 in effective

        assert has_all_permissions(test_user, [p1, p2, p3]) is True
        assert has_any_permission(test_user, [p1, "unknown.perm"]) is True

    def test_empty_permissions_collection_returns_false(self, test_user, sample_permission):
        test_user.user_permissions.add(sample_permission)
        clear_permission_cache(test_user)

        assert has_any_permission(test_user, []) is False
        assert has_all_permissions(test_user, []) is False
        assert has_any_permission(test_user, None) is False
        assert has_all_permissions(test_user, None) is False

    def test_superuser_has_all_permissions(self, superuser):
        assert has_permission(superuser, "projects.view_project") is True
        assert has_all_permissions(superuser, ["a.b", "c.d"]) is True
        assert has_any_permission(superuser, ["x.y"]) is True

    def test_permission_revocation_invalidates_cache(self, test_user, sample_permission):
        perm_code = f"{sample_permission.content_type.app_label}.{sample_permission.codename}"
        role = Role.objects.get(code=SystemRole.PROJECT_MANAGER)
        assign_permission_to_role(role, sample_permission)
        assign_role(test_user, role)

        assert has_permission(test_user, perm_code) is True

        # Revoke role from user
        remove_role(test_user, role)

        assert has_permission(test_user, perm_code) is False

    def test_django_user_has_perm_backend_integration(self, test_user, sample_permission):
        perm_code = f"{sample_permission.content_type.app_label}.{sample_permission.codename}"
        role = Role.objects.get(code=SystemRole.PROJECT_MANAGER)
        assign_permission_to_role(role, sample_permission)
        assign_role(test_user, role)

        # Native Django user.has_perm integrates seamlessly via RolePermissionBackend
        assert test_user.has_perm(perm_code) is True
        assert perm_code in test_user.get_all_permissions()


@pytest.mark.unit
@pytest.mark.django_db
class TestObjectLevelAuthorization:
    class MockProject:
        def __init__(self, user_id):
            self.user_id = user_id

    class MockProjectWithHook:
        def __init__(self, user_id):
            self.user_id = user_id

        def has_object_permission(self, user, permission):
            return permission == "projects.custom_action" and self.user_id == user.id

    def test_check_object_permission_ownership_requires_explicit_flag(self, test_user, user_factory):
        other_user = user_factory()
        own_project = self.MockProject(user_id=test_user.id)
        other_project = self.MockProject(user_id=other_user.id)

        # Default (allow_owner=False) ensures ownership does NOT grant arbitrary permission
        assert check_object_permission(test_user, "projects.change_project", own_project, allow_owner=False) is False
        assert check_object_permission(test_user, "projects.change_project", other_project, allow_owner=False) is False

        # When allow_owner=True is explicitly passed, own object is authorized
        assert check_object_permission(test_user, "projects.change_project", own_project, allow_owner=True) is True
        assert check_object_permission(test_user, "projects.change_project", other_project, allow_owner=True) is False

    def test_check_object_permission_custom_model_hook(self, test_user, user_factory):
        other_user = user_factory()
        project = self.MockProjectWithHook(user_id=test_user.id)

        assert check_object_permission(test_user, "projects.custom_action", project) is True
        assert check_object_permission(other_user, "projects.custom_action", project) is False
        assert check_object_permission(test_user, "projects.disallowed_action", project) is False



@pytest.mark.unit
@pytest.mark.django_db
class TestSystemRolesSync:
    def test_sync_system_roles_creates_new_roles(self):
        from authentication.services.roles import sync_system_roles
        from authentication.system_roles import RoleDefinition

        custom_def = [
            RoleDefinition(code="AUDITOR", name="Compliance Auditor", description="Audit logs access.")
        ]
        summary = sync_system_roles(role_definitions=custom_def)
        assert "AUDITOR" in summary["created"]

        role = Role.objects.get(code="AUDITOR")
        assert role.name == "Compliance Auditor"
        assert role.is_system is True

    def test_sync_system_roles_updates_existing_role(self):
        from authentication.services.roles import sync_system_roles
        from authentication.system_roles import RoleDefinition

        Role.objects.create(code="ANALYST", name="Old Name", description="Old Desc", is_system=True)

        updated_def = [
            RoleDefinition(code="ANALYST", name="New Analyst", description="Updated description.")
        ]
        summary = sync_system_roles(role_definitions=updated_def)
        assert "ANALYST" in summary["updated"]

        role = Role.objects.get(code="ANALYST")
        assert role.name == "New Analyst"
        assert role.description == "Updated description."

    def test_sync_system_roles_dry_run_leaves_db_unchanged(self):
        from authentication.services.roles import sync_system_roles
        from authentication.system_roles import RoleDefinition

        custom_def = [
            RoleDefinition(code="GHOST_ROLE", name="Ghost", description="Should not be created.")
        ]
        summary = sync_system_roles(role_definitions=custom_def, dry_run=True)
        assert "GHOST_ROLE" in summary["created"]
        assert not Role.objects.filter(code="GHOST_ROLE").exists()

    def test_sync_system_roles_prune_safety_with_active_user(self, test_user):
        from authentication.services.roles import sync_system_roles
        from authentication.system_roles import RoleDefinition

        # Role exists in DB with an assigned user, but is omitted from definitions
        obsolete_role = Role.objects.create(
            code="LEGACY_OPERATOR", name="Legacy", description="Legacy role.", is_system=True
        )
        assign_role(test_user, obsolete_role)

        definitions = [
            RoleDefinition(code=SystemRole.USER, name="Standard User", description="Standard user.")
        ]

        # Prune run
        summary = sync_system_roles(prune=True, role_definitions=definitions)
        # Should be protected from hard-delete because of active user assignment
        assert any("LEGACY_OPERATOR" in item for item in summary["protected_from_prune"])
        obsolete_role.refresh_from_db()
        assert obsolete_role.is_deleted is True  # soft-deleted safely

    def test_management_command_sync_roles_executes_cleanly(self):
        import io
        from django.core.management import call_command

        out = io.StringIO()
        call_command("sync_roles", stdout=out)
        output = out.getvalue()
        assert "synchronization" in output.lower() or "up to date" in output.lower()


@pytest.mark.unit
@pytest.mark.django_db
class TestRoleAdminProtection:
    def test_admin_has_delete_permission_blocks_system_roles(self, superuser):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        from authentication.admin import RoleAdmin
        from authentication.models import Role

        admin_site = AdminSite()
        role_admin = RoleAdmin(Role, admin_site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = superuser

        system_role = Role.objects.get(code=SystemRole.SUPER_ADMIN)
        custom_role = Role.objects.create(code="CUSTOM_ROLE", name="Custom")

        assert role_admin.has_delete_permission(request, obj=system_role) is False
        assert role_admin.has_delete_permission(request, obj=custom_role) is True


    def test_admin_delete_queryset_skips_system_roles(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        from authentication.admin import RoleAdmin
        from authentication.models import Role

        admin_site = AdminSite()
        role_admin = RoleAdmin(Role, admin_site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, "session", {})
        setattr(request, "_messages", FallbackStorage(request))

        custom_role = Role.objects.create(code="TO_DELETE", name="To Delete")
        system_role = Role.objects.get(code=SystemRole.SUPER_ADMIN)

        qs = Role.objects.filter(pk__in=[custom_role.pk, system_role.pk])
        role_admin.delete_queryset(request, qs)

        assert not Role.objects.filter(pk=custom_role.pk).exists()
        assert Role.objects.filter(pk=system_role.pk).exists()


