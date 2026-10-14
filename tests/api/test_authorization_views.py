import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from authentication.models import Role
from authentication.roles import SystemRole
from authentication.services.permissions import (
    assign_permission_to_role,
    assign_role,
)
from core.utils.decorators import authorize
from core.utils.permissions import AuthorizePermission, HasPermission, HasRole
from core.utils.response import success_response

User = get_user_model()


@pytest.fixture
def auth_perm():
    ct = ContentType.objects.get_for_model(User)
    perm, _ = Permission.objects.get_or_create(
        codename="view_project",
        content_type=ct,
        defaults={"name": "Can view project"},
    )
    return perm


@pytest.fixture
def auth_perm_change():
    ct = ContentType.objects.get_for_model(User)
    perm, _ = Permission.objects.get_or_create(
        codename="change_project",
        content_type=ct,
        defaults={"name": "Can change project"},
    )
    return perm


@pytest.mark.api
@pytest.mark.django_db
class TestAuthorizeDecoratorFBV:
    def setup_method(self):
        self.factory = APIRequestFactory()

    def test_strict_role_only_decorator_allowed(self, test_user):
        @authorize(strict="SUPER_ADMIN")
        def delete_user(request, user_id):
            return success_response(data={"deleted": user_id})

        assign_role(test_user, SystemRole.SUPER_ADMIN)
        request = self.factory.post("/users/1/delete/")
        request.user = test_user

        response = delete_user(request, user_id=1)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["deleted"] == 1

    def test_strict_role_only_decorator_denied_returns_403(self, test_user):
        @authorize(strict="SUPER_ADMIN")
        def delete_user(request, user_id):
            return success_response(data={"deleted": user_id})

        assign_role(test_user, SystemRole.DEVELOPER)
        request = self.factory.post("/users/1/delete/")
        request.user = test_user

        response = delete_user(request, user_id=1)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["message"] == "You do not have permission to perform this action."

    def test_permission_only_decorator(self, test_user, auth_perm):
        perm_code = f"{auth_perm.content_type.app_label}.{auth_perm.codename}"

        @authorize(permission=perm_code)
        def project_list(request):
            return success_response(data={"projects": ["Alpha", "Beta"]})

        request = self.factory.get("/projects/")
        request.user = test_user

        # Denied initially
        res_denied = project_list(request)
        assert res_denied.status_code == status.HTTP_403_FORBIDDEN

        # Grant permission
        test_user.user_permissions.add(auth_perm)
        res_allowed = project_list(request)
        assert res_allowed.status_code == status.HTTP_200_OK
        assert res_allowed.data["data"]["projects"] == ["Alpha", "Beta"]

    def test_role_and_permission_operator_and(self, test_user, auth_perm_change):
        perm_code = f"{auth_perm_change.content_type.app_label}.{auth_perm_change.codename}"

        @authorize(
            strict="PROJECT_MANAGER",
            permission=perm_code,
            operator="AND",
        )
        def update_project(request, project_id):
            return success_response(data={"updated": project_id})

        request = self.factory.put("/projects/1/")
        request.user = test_user

        # Has neither -> 403
        assert update_project(request, project_id=1).status_code == status.HTTP_403_FORBIDDEN

        # Has role only -> 403
        assign_role(test_user, SystemRole.PROJECT_MANAGER)
        assert update_project(request, project_id=1).status_code == status.HTTP_403_FORBIDDEN

        # Has both -> 200
        test_user.user_permissions.add(auth_perm_change)
        res = update_project(request, project_id=1)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["data"]["updated"] == 1

    def test_role_and_permission_operator_or(self, test_user, auth_perm_change):
        perm_code = f"{auth_perm_change.content_type.app_label}.{auth_perm_change.codename}"

        @authorize(
            strict="PROJECT_MANAGER",
            permission=perm_code,
            operator="OR",
        )
        def alternative_update_project(request, project_id):
            return success_response(data={"updated": project_id})

        request = self.factory.put("/projects/1/")
        request.user = test_user

        # Has neither -> 403
        assert alternative_update_project(request, project_id=1).status_code == status.HTTP_403_FORBIDDEN

        # Grant only role -> 200
        assign_role(test_user, SystemRole.PROJECT_MANAGER)
        assert alternative_update_project(request, project_id=1).status_code == status.HTTP_200_OK

    def test_unauthenticated_request_returns_401(self):
        @authorize(strict="SUPER_ADMIN")
        def protected_view(request):
            return success_response()

        request = self.factory.get("/test/")
        request.user = AnonymousUser()

        response = protected_view(request)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["message"] == "Authentication required."

    def test_invalid_operator_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid operator"):
            @authorize(strict="ADMIN", operator="XOR")
            def invalid_view(request):
                pass

    def test_empty_criteria_raises_value_error(self):
        with pytest.raises(ValueError, match="At least one role or permission must be specified"):
            @authorize()
            def invalid_view(request):
                pass


@pytest.mark.api
@pytest.mark.django_db
class TestAuthorizeDecoratorCBVAndAsync:
    def setup_method(self):
        self.factory = APIRequestFactory()

    def test_authorize_on_cbv_method(self, test_user):
        from rest_framework.test import force_authenticate

        class ProjectDetailView(APIView):
            permission_classes = [AllowAny]

            @authorize(strict="DEVELOPER")
            def get(self, request, project_id):
                return success_response(data={"project_id": project_id})

        view = ProjectDetailView.as_view()
        request = self.factory.get("/projects/42/")
        force_authenticate(request, user=test_user)

        # Denied
        assert view(request, project_id=42).status_code == status.HTTP_403_FORBIDDEN

        # Grant role
        assign_role(test_user, SystemRole.DEVELOPER)
        request2 = self.factory.get("/projects/42/")
        force_authenticate(request2, user=test_user)
        res = view(request2, project_id=42)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["data"]["project_id"] == 42

    def test_async_view_compatibility(self, transactional_db, test_user):
        import asyncio

        @authorize(strict="DEVELOPER")
        async def async_view(request):
            return success_response(data={"async": True})

        assign_role(test_user, SystemRole.DEVELOPER)
        request = self.factory.get("/async/")
        request.user = test_user

        response = asyncio.run(async_view(request))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["async"] is True


@pytest.mark.api
@pytest.mark.django_db
class TestDRFPermissionClassesIntegration:
    def setup_method(self):
        self.factory = APIRequestFactory()

    def test_drf_has_role_permission_class(self, test_user):
        from rest_framework.test import force_authenticate

        class DeveloperAPIView(APIView):
            permission_classes = [HasRole("DEVELOPER")]

            def get(self, request):
                return success_response()

        view = DeveloperAPIView.as_view()
        request = self.factory.get("/dev/")
        force_authenticate(request, user=test_user)

        assert view(request).status_code == status.HTTP_403_FORBIDDEN

        assign_role(test_user, SystemRole.DEVELOPER)
        request2 = self.factory.get("/dev/")
        force_authenticate(request2, user=test_user)
        assert view(request2).status_code == status.HTTP_200_OK

    def test_drf_authorize_permission_class_combined(self, test_user, auth_perm):
        from rest_framework.test import force_authenticate

        perm_code = f"{auth_perm.content_type.app_label}.{auth_perm.codename}"

        class ProjectAdminAPIView(APIView):
            permission_classes = [
                AuthorizePermission(
                    roles=["ADMIN"],
                    permissions=[perm_code],
                    operator="OR",
                )
            ]

            def get(self, request):
                return success_response()

        view = ProjectAdminAPIView.as_view()
        request = self.factory.get("/admin-project/")
        force_authenticate(request, user=test_user)

        # Neither -> 403
        assert view(request).status_code == status.HTTP_403_FORBIDDEN

        # Grant role -> 200 (since operator is OR)
        assign_role(test_user, SystemRole.ADMIN)
        request2 = self.factory.get("/admin-project/")
        force_authenticate(request2, user=test_user)
        assert view(request2).status_code == status.HTTP_200_OK


@pytest.mark.api
@pytest.mark.django_db
class TestAuthorizeDecoratorObjectLevel:
    def setup_method(self):
        self.factory = APIRequestFactory()

    class MockResource:
        def __init__(self, resource_id, user_id):
            self.id = resource_id
            self.user_id = user_id

    def test_authorize_with_object_getter_and_allow_owner(self, test_user, user_factory):
        other_user = user_factory()
        own_resource = self.MockResource(1, test_user.id)
        other_resource = self.MockResource(2, other_user.id)

        resources = {1: own_resource, 2: other_resource}

        # 1. View with allow_owner=False (default) blocks non-privileged users even if they own the resource
        @authorize(
            permission="projects.change_project",
            object_getter=lambda req, resource_id: resources.get(resource_id),
            allow_owner=False,
        )
        def update_resource(request, resource_id):
            return success_response(data={"updated": resource_id})

        request_own = self.factory.post("/resources/1/")
        request_own.user = test_user
        res_denied = update_resource(request_own, resource_id=1)
        assert res_denied.status_code == status.HTTP_403_FORBIDDEN

        # 2. View with allow_owner=True allows owner access
        @authorize(
            permission="projects.change_project",
            object_getter=lambda req, resource_id: resources.get(resource_id),
            allow_owner=True,
        )
        def owner_update_resource(request, resource_id):
            return success_response(data={"updated": resource_id})

        res_owner_allowed = owner_update_resource(request_own, resource_id=1)
        assert res_owner_allowed.status_code == status.HTTP_200_OK

        request_other = self.factory.post("/resources/2/")
        request_other.user = test_user
        res_other_denied = owner_update_resource(request_other, resource_id=2)
        assert res_other_denied.status_code == status.HTTP_403_FORBIDDEN


