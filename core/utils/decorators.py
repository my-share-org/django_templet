import asyncio
from functools import wraps
from typing import Any, Callable, Iterable, Optional, Sequence, Union

from rest_framework import status
from rest_framework.permissions import BasePermission

from authentication.services.permissions import (
    has_all_permissions,
    has_all_roles,
    has_any_permission,
    has_any_role,
    has_permission,
    has_role,
)
from core.utils.response import error_response


def is_admin(user: Any) -> bool:
    """Checks whether the user is active, authenticated, and has staff privileges."""
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_staff", False)
    )


class IsAdminUser(BasePermission):
    """
    DRF permission class. Use this on class-based views:
        permission_classes = [IsAdminUser]
    """
    message = "Admin access required."

    def has_permission(self, request, view):
        return is_admin(request.user)


def admin_required(view_func: Callable):
    """
    Decorator for function-based views.
    Blocks non-staff users with 403.

    Usage:
        @admin_required
        def my_view(request): ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return error_response(
                message="Authentication required.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        if not request.user.is_staff:
            return error_response(
                message="Admin access required.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return view_func(request, *args, **kwargs)

    return wrapper


def _extract_request(args: tuple, kwargs: dict) -> Any:
    """Finds the HttpRequest/Request instance across FBVs, CBV methods, or kwargs."""
    if args:
        if hasattr(args[0], "user"):
            return args[0]
        if len(args) > 1 and hasattr(args[1], "user"):
            return args[1]
    if "request" in kwargs and hasattr(kwargs["request"], "user"):
        return kwargs["request"]
    return None


def authorize(
    *,
    strict: Union[str, Sequence[str], None] = None,
    role: Union[str, Sequence[str], None] = None,
    roles: Union[str, Sequence[str], None] = None,
    permission: Union[str, Sequence[str], None] = None,
    permissions: Union[str, Sequence[str], None] = None,
    operator: str = "AND",
    role_operator: str = "ALL",
    permission_operator: str = "ALL",
    object_getter: Optional[Callable[..., Any]] = None,
):
    """
    Production-ready decorator for views (function-based or class-based methods).
    Enforces role and/or permission authorization policies with AND/OR composition.

    Usage:
        @authorize(strict="SUPER_ADMIN")
        def delete_user(request, user_id):
            ...

        @authorize(permission="projects.view_project")
        def project_list(request):
            ...

        @authorize(
            strict="PROJECT_MANAGER",
            permission="projects.change_project",
            operator="AND",
        )
        def update_project(request, project_id):
            ...

        @authorize(
            strict="PROJECT_MANAGER",
            permission="projects.change_project",
            operator="OR",
        )
        def alternative_update_project(request, project_id):
            ...
    """
    if not isinstance(operator, str):
        raise ValueError(f"Invalid operator '{operator}'. Operator must be a string ('AND' or 'OR').")

    op = operator.strip().upper()
    if op not in ("AND", "OR"):
        raise ValueError(f"Invalid operator '{operator}'. Operator must be 'AND' or 'OR'.")

    # Normalize roles into a list
    role_specs: list[str] = []
    for candidate in (strict, role, roles):
        if candidate is not None:
            if isinstance(candidate, str):
                role_specs.append(candidate)
            elif isinstance(candidate, (list, tuple, set)):
                role_specs.extend(list(candidate))
            else:
                raise TypeError(f"Invalid role specification type: {type(candidate).__name__}")

    # Normalize permissions into a list
    perm_specs: list[str] = []
    for candidate in (permission, permissions):
        if candidate is not None:
            if isinstance(candidate, str):
                perm_specs.append(candidate)
            elif isinstance(candidate, (list, tuple, set)):
                perm_specs.extend(list(candidate))
            else:
                raise TypeError(f"Invalid permission specification type: {type(candidate).__name__}")

    if not role_specs and not perm_specs:
        raise ValueError("At least one role or permission must be specified for @authorize.")

    clean_role_op = role_operator.strip().upper() if isinstance(role_operator, str) else "ALL"
    clean_perm_op = permission_operator.strip().upper() if isinstance(permission_operator, str) else "ALL"

    def decorator(view_func: Callable):
        def _check_auth(request, *view_args, **view_kwargs):
            if not request or not getattr(request, "user", None):
                return False, error_response(
                    message="Authentication required.",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )

            user = request.user
            if not user.is_authenticated or not getattr(user, "is_active", True):
                return False, error_response(
                    message="Authentication required.",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )

            # Evaluate roles
            role_passed = None
            if role_specs:
                if len(role_specs) == 1 and clean_role_op != "ANY":
                    role_passed = has_role(user, role_specs[0])
                elif clean_role_op == "ANY":
                    role_passed = has_any_role(user, role_specs)
                else:
                    role_passed = has_all_roles(user, role_specs)

            # Evaluate permissions
            perm_passed = None
            if perm_specs:
                target_obj = None
                if object_getter is not None:
                    try:
                        target_obj = object_getter(request, *view_args, **view_kwargs)
                    except Exception:
                        return False, error_response(
                            message="You do not have permission to perform this action.",
                            status_code=status.HTTP_403_FORBIDDEN,
                        )

                from core.utils.permissions import check_object_permission

                if len(perm_specs) == 1 and clean_perm_op != "ANY":
                    if target_obj is not None:
                        perm_passed = check_object_permission(user, perm_specs[0], target_obj)
                    else:
                        perm_passed = has_permission(user, perm_specs[0])
                elif clean_perm_op == "ANY":
                    perm_passed = has_any_permission(user, perm_specs, obj=target_obj)
                else:
                    perm_passed = has_all_permissions(user, perm_specs, obj=target_obj)

            # Combine policies with operator
            if role_passed is not None and perm_passed is not None:
                if op == "OR":
                    authorized = role_passed or perm_passed
                else:
                    authorized = role_passed and perm_passed
            elif role_passed is not None:
                authorized = role_passed
            elif perm_passed is not None:
                authorized = perm_passed
            else:
                authorized = False

            if not authorized:
                return False, error_response(
                    message="You do not have permission to perform this action.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            return True, None

        if asyncio.iscoroutinefunction(view_func):
            from asgiref.sync import sync_to_async

            @wraps(view_func)
            async def async_wrapper(*args, **kwargs):
                request = _extract_request(args, kwargs)
                passed, error_resp = await sync_to_async(_check_auth, thread_sensitive=True)(
                    request, *args, **kwargs
                )
                if not passed:
                    return error_resp
                return await view_func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(view_func)
            def sync_wrapper(*args, **kwargs):
                request = _extract_request(args, kwargs)
                passed, error_resp = _check_auth(request, *args, **kwargs)
                if not passed:
                    return error_resp
                return view_func(*args, **kwargs)
            return sync_wrapper

    return decorator
