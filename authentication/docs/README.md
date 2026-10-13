# Authentication Module

## Table of Contents

1. [Overview](#1-overview)
2. [User Model](#2-user-model)
3. [API Endpoints](#3-api-endpoints)
4. [Serializers](#4-serializers)
5. [Throttling](#5-throttling)
6. [JWT Configuration](#6-jwt-configuration)
7. [Admin Interface](#7-admin-interface)
8. [Integration Notes](#8-integration-notes)

---

## 1. Overview

The `authentication` app manages everything related to user identity in the system. It provides:

- A **custom user model** using email as the primary identifier instead of a username.
- **Registration** with OTP verification to ensure email ownership before account creation.
- **JWT-based login** that issues both access and refresh tokens.
- **Secure logout** with refresh token blacklisting.
- **Password management** with current password verification and Django's built-in validators.
- **Session verification** to confirm authenticated identity.

All endpoints return a standardized response envelope (`success`, `message`, `data`) defined in the `core` module.

### File Structure

```
authentication/
├── migrations/             # Database migration files
├── docs/
│   └── README.md           # This file
├── admin.py                # Django admin configuration
├── apps.py                 # App configuration
├── managers.py             # Custom user manager
├── models.py               # User model
├── serializers.py          # DRF serializers
├── services.py             # Business logic (password change)
├── throttles.py            # Custom rate limiters
├── urls.py                 # URL patterns
└── views.py                # API views
```

---

## 2. User Model

**Module:** `authentication.models.User`

The system uses a fully custom user model that replaces Django's default `User`. It extends `AbstractBaseUser` and `PermissionsMixin`.

### Fields

| Field | Type | Description |
|---|---|---|
| `email` | `EmailField` | Unique identifier. Used as `USERNAME_FIELD`. |
| `first_name` | `CharField` | User's first name. |
| `last_name` | `CharField` | User's last name. |
| `is_active` | `BooleanField` | Whether the account is active. Defaults to `True`. |
| `is_staff` | `BooleanField` | Whether the user can access the Django admin. |
| `date_joined` | `DateTimeField` | Timestamp of account creation (auto-set). |

### Custom Manager — `UserManager`

The `UserManager` overrides `create_user()` and `create_superuser()` to enforce email normalization and proper flag defaults.

```python
# Create a regular user
user = User.objects.create_user(email='user@example.com', password='secret')

# Create a superuser
user = User.objects.create_superuser(email='admin@example.com', password='secret')
```

### Settings Reference

```python
AUTH_USER_MODEL = 'authentication.User'
```

---

## 3. API Endpoints

Base path: `/auth/`

---

### POST `/auth/register/`

Register a new user account. OTP verification is required as part of registration.

**Authentication:** Not required

**Request Body:**

```json
{
  "email": "user@example.com",
  "first_name": "Jane",
  "last_name": "Doe",
  "password": "StrongPassword123",
  "otp": "482910"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `email` | string | Yes | Email address (used as login identifier) |
| `first_name` | string | Yes | First name |
| `last_name` | string | Yes | Last name |
| `password` | string | Yes | Password — subject to Django's password validators |
| `otp` | string | Yes | 6-digit OTP previously sent to the email |

**Success Response — `201 Created`:**

```json
{
  "success": true,
  "message": "User registered successfully",
  "data": null
}
```

**Error Responses:**

| Status | Scenario |
|---|---|
| `400 Bad Request` | Missing fields, invalid email, weak password, invalid/expired OTP |
| `429 Too Many Requests` | Register throttle limit exceeded |

---

### POST `/auth/login/`

Authenticate a user and receive JWT access and refresh tokens.

**Authentication:** Not required

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "StrongPassword123"
}
```

**Success Response — `200 OK`:**

```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access": "<access_token>",
    "refresh": "<refresh_token>",
    "user": {
      "id": 1,
      "email": "user@example.com",
      "first_name": "Jane",
      "last_name": "Doe"
    }
  }
}
```

**Error Responses:**

| Status | Scenario |
|---|---|
| `401 Unauthorized` | Invalid credentials or inactive account |
| `429 Too Many Requests` | Login throttle limit exceeded |

---

### POST `/auth/logout/`

Logout the current user by blacklisting their refresh token. After logout, the refresh token cannot be used to obtain new access tokens.

**Authentication:** Required (`Bearer <access_token>`)

**Request Body:**

```json
{
  "refresh": "<refresh_token>"
}
```

**Success Response — `200 OK`:**

```json
{
  "success": true,
  "message": "Logout successful",
  "data": null
}
```

**Error Responses:**

| Status | Scenario |
|---|---|
| `400 Bad Request` | Missing or already-blacklisted refresh token |
| `401 Unauthorized` | Access token missing or expired |

---

### POST `/auth/token/refresh/`

Obtain a new access token using a valid refresh token. Due to `ROTATE_REFRESH_TOKENS = True`, a new refresh token is also issued and the old one is blacklisted.

**Authentication:** Not required

**Request Body:**

```json
{
  "refresh": "<refresh_token>"
}
```

**Success Response — `200 OK`:**

```json
{
  "access": "<new_access_token>",
  "refresh": "<new_refresh_token>"
}
```

**Error Responses:**

| Status | Scenario |
|---|---|
| `401 Unauthorized` | Refresh token is expired, blacklisted, or invalid |

---

### GET `/auth/verify/`

Verify that the current access token is valid and return the authenticated user's information.

**Authentication:** Required (`Bearer <access_token>`)

**Success Response — `200 OK`:**

```json
{
  "success": true,
  "message": "User verified",
  "data": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "Jane",
    "last_name": "Doe"
  }
}
```

**Error Responses:**

| Status | Scenario |
|---|---|
| `401 Unauthorized` | Access token missing or expired |

---

### POST `/auth/password/change/`

Change the authenticated user's password. Requires both the current password for verification and the new password.

**Authentication:** Required (`Bearer <access_token>`)

**Request Body:**

```json
{
  "current_password": "OldPassword123",
  "new_password": "NewStrongPassword456"
}
```

**Success Response — `200 OK`:**

```json
{
  "success": true,
  "message": "Password changed successfully",
  "data": null
}
```

**Error Responses:**

| Status | Scenario |
|---|---|
| `400 Bad Request` | Current password is incorrect, or new password fails validation |
| `401 Unauthorized` | Access token missing or expired |
| `429 Too Many Requests` | Change password throttle limit exceeded |

---

## 4. Serializers

### `RegisterSerializer`

Handles user registration input. Validates:
- OTP correctness (delegates to `OTPService`)
- Password strength (runs Django's `AUTH_PASSWORD_VALIDATORS`)
- Email uniqueness

On `.save()`, creates the `User` instance.

### `LoginSerializer`

Extends `TokenObtainPairSerializer` from SimpleJWT. Adds user details to the token response payload for convenience.

---

## 5. Throttling

Custom throttle classes defined in `authentication/throttles.py` protect sensitive endpoints.

| Throttle Class | Setting Key | Applied To |
|---|---|---|
| `RegisterThrottle` | `register` | `POST /auth/register/` |
| `LoginThrottle` | `login` | `POST /auth/login/` |
| `ChangePasswordThrottle` | `change_password` | `POST /auth/password/change/` |

Rates are configured via environment variables:
- `REGISTER_THROTTLE_RATE_PER_MINUTE`
- `LOGIN_THROTTLE_RATE_PER_MINUTE`
- `CHANGE_PASSWORD_THROTTLE_RATE_PER_MINUTE`

---

## 6. JWT Configuration

Configured in `my_django/settings.py` under `SIMPLE_JWT`:

| Setting | Value | Description |
|---|---|---|
| `AUTH_HEADER_TYPES` | `Bearer` | Token prefix in the `Authorization` header |
| `ACCESS_TOKEN_LIFETIME` | 15 minutes (configurable) | How long access tokens are valid |
| `REFRESH_TOKEN_LIFETIME` | 30 hours (configurable) | How long refresh tokens are valid |
| `ROTATE_REFRESH_TOKENS` | `True` | New refresh token issued on every refresh |
| `BLACKLIST_AFTER_ROTATION` | `True` | Old refresh tokens are invalidated |
| `UPDATE_LAST_LOGIN` | `True` | Updates `last_login` on the user on each login |
| `ALGORITHM` | `HS256` | Signing algorithm |

The `rest_framework_simplejwt.token_blacklist` app must remain in `INSTALLED_APPS` for token blacklisting to function.

---

## 7. Admin Interface

The `UserAdmin` class provides a tailored admin interface:

- **List display:** email, first name, last name, is\_active, is\_staff, date\_joined
- **Search:** by email, first name, last name
- **Filters:** is\_active, is\_staff, date\_joined
- **Fieldsets:** Organized into Personal Info, Permissions, and Important Dates sections
- **Password:** Displayed as a hashed value (read-only); use the change form to update

Access at: `/admin/authentication/user/`

---

## 8. Integration Notes

### Adding Fields to the User Model

To add custom fields (e.g., `phone`, `avatar`, `timezone`):
1. Add the field to `authentication/models.py`.
2. Run `python manage.py makemigrations authentication` and `python manage.py migrate`.
3. Update `RegisterSerializer` to include the new field.
4. Update `UserAdmin` fieldsets as appropriate.

### OTP Dependency

Registration requires a valid OTP. The OTP must be requested first via `POST /v1/otp/get-otp/` with `purpose=registration`. See the [OTP module documentation](../../otp/docs/README.md) for details.

### Extending the Login Response

To include additional data in the login response, override `LoginSerializer.validate()` and add fields to the returned dictionary.

---

## 9. Role & Permission Authorization System

### Overview

The system includes a production-ready, additive role- and permission-based authorization architecture:
1. **User**: Extends `PermissionsMixin` and connects to `Role` via `roles` M2M with through-model `UserRole`.
2. **Role**: Represents an authorization role with stable programmatic `code` (`SUPER_ADMIN`, `ADMIN`, `PROJECT_MANAGER`, `DEVELOPER`, `USER`), human-readable `name`, direct `permissions` (`auth.Permission`), and `groups` (`auth.Group`).
3. **Effective Permissions**: Automatically computed from 4 sources:
   - Direct user permissions
   - Permissions from groups assigned to user
   - Permissions assigned to user's roles
   - Permissions from groups assigned to user's roles
4. **Backend Integration**: `RolePermissionBackend` extends Django's authentication backend so that native `user.has_perm()` and `user.get_all_permissions()` include all role and role-group permissions.
5. **Automatic Cache Invalidation**: `m2m_changed` and `post_save`/`post_delete` signals automatically invalidate user permission caches whenever permissions, groups, or role assignments change.

### Public Authorization Functions

Import from `core.utils.permissions` or `authentication.services.permissions`:

```python
from core.utils.permissions import (
    has_role,
    has_any_role,
    has_all_roles,
    has_permission,
    has_any_permission,
    has_all_permissions,
)

# Role checks
has_role(user, "SUPER_ADMIN")
has_any_role(user, ["PROJECT_MANAGER", "DEVELOPER"])
has_all_roles(user, ["PROJECT_MANAGER", "DEVELOPER"])

# Permission checks (app_label.codename)
has_permission(user, "projects.view_project")
has_any_permission(user, ["projects.view_project", "projects.change_project"])
has_all_permissions(user, ["projects.view_project", "projects.change_project"])
```

### View Decorator `@authorize`

Import from `core.utils.decorators`:

```python
from core.utils.decorators import authorize

# Role-only check
@authorize(strict="SUPER_ADMIN")
def delete_user(request, user_id):
    ...

# Permission-only check
@authorize(permission="projects.view_project")
def project_list(request):
    ...

# Combined Role AND Permission check (default operator is AND)
@authorize(
    strict="PROJECT_MANAGER",
    permission="projects.change_project",
    operator="AND",
)
def update_project(request, project_id):
    ...

# Combined Role OR Permission check
@authorize(
    strict="PROJECT_MANAGER",
    permission="projects.change_project",
    operator="OR",
)
def alternative_update_project(request, project_id):
    ...
```

### DRF Permission Classes

Import from `core.utils.permissions`:

```python
from rest_framework.views import APIView
from core.utils.permissions import HasRole, HasPermission, AuthorizePermission

class ProjectManagementView(APIView):
    permission_classes = [
        AuthorizePermission(
            roles=["PROJECT_MANAGER"],
            permissions=["projects.change_project"],
            operator="AND",
        )
    ]
```
