# Services Reference

---

## Table of Contents

- [authentication](#authentication)
  - [services/password.py](#servicespasswordpy)
  - [services/permissions.py](#servicespermissionspy)
  - [services/roles.py](#servicesrolespy)
- [otp](#otp)
  - [services/otp.py](#servicesotppy)
  - [services/rules.py](#servicesrulespy)
- [emails](#emails)
  - [services/otp.py](#emailsservicesotppy)
- [core](#core)
  - [services/health_check.py](#serviceshealthcheckpy)

---

## authentication

### `services/password.py`

#### `change_password(user, new_password)`
**Takes:** authenticated User instance, new password string  
**Returns:** updated User instance  
**Raises:** `ValidationError` if password fails Django's validators  

Call only after confirming the current password with `user.check_password()`.

---

#### `reset_password(email, new_password)`
**Takes:** email string, new password string  
**Returns:** updated User instance  
**Raises:** `ValidationError` if no account found for that email, or if the new password fails validators  

Call only after OTP verification is confirmed. Never expose directly without OTP gating.

---

### `services/permissions.py`

#### `has_role(user, role)`
**Takes:** User instance, role code string (e.g. `"SUPER_ADMIN"`) or `Role` model instance  
**Returns:** `bool` — `True` if active authenticated user has the specified role, `False` otherwise  
**Rules:** Unauthenticated or inactive users always return `False`. Case-insensitive.

---

#### `has_any_role(user, roles)`
**Takes:** User instance, iterable of role code strings or `Role` instances  
**Returns:** `bool` — `True` if user has at least one of the specified roles  
**Rules:** Empty collection returns `False`.

---

#### `has_all_roles(user, roles)`
**Takes:** User instance, iterable of role code strings or `Role` instances  
**Returns:** `bool` — `True` if user has all specified roles  
**Rules:** Empty collection returns `False`.

---

#### `has_permission(user, permission, obj=None)`
**Takes:** User instance, permission code (`"app_label.codename"`) or `Permission` instance, optional object  
**Returns:** `bool` — `True` if granted through any source (direct, user group, role, role group, or superuser)  
**Rules:** Unauthenticated or inactive users always return `False`.

---

#### `has_any_permission(user, permissions, obj=None)`
**Takes:** User instance, iterable of permission codes  
**Returns:** `bool` — `True` if at least one permission is granted. Empty collection returns `False`.

---

#### `has_all_permissions(user, permissions, obj=None)`
**Takes:** User instance, iterable of permission codes  
**Returns:** `bool` — `True` only if all specified permissions are granted. Empty collection returns `False`.

---

#### `assign_role(user, role)` / `remove_role(user, role)`
**Takes:** User instance, role code string or `Role` instance  
**Returns:** `UserRole` instance (for assign), `bool` (for remove)  
**Rules:** Automatically invalidates user permission and role cache.

---

### `services/roles.py`

#### `sync_system_roles(prune=False, dry_run=False, role_definitions=None)`
**Takes:** optional `prune` boolean, `dry_run` boolean, custom `role_definitions` list  
**Returns:** dict summary: `{"created": [...], "updated": [...], "unchanged": [...], "pruned": [...], "protected_from_prune": [...]}`  
**Rules:** Synchronizes database roles with `authentication.system_roles.SYSTEM_ROLES`. If `prune=True`, roles with active assigned users are safely soft-deleted rather than hard-deleted.


---

## otp

### `services/otp.py`

#### `OTPService.generate(user, purpose)`
**Takes:** user identifier string (email or phone), `OtpPurpose` value  
**Returns:** plaintext OTP string — only available at this moment, not retrievable later  

Stores the OTP hashed in Redis. Automatically evicts the oldest OTP if the active limit is exceeded.

---

#### `OTPService.verify(user, purpose, submitted_otp)`
**Takes:** user identifier string, `OtpPurpose` value, OTP string submitted by the user  
**Returns:** `True` if valid and consumed, `False` otherwise  

Deletes the OTP from Redis on a successful match — single use.

---

#### `OTPService.send(user, purpose, channel)`
**Takes:** user identifier string, `OtpPurpose` value, `OtpChannel` value  
**Returns:** `None`  
**Raises:** `NotImplementedError` for `OtpChannel.PHONE`, `ValueError` for unrecognised channel  

Calls `generate()` internally, then dispatches via the given channel. Email delivery is async (Celery). Returns immediately.

---

### `services/rules.py`

#### `get_otp_rules(purpose)`
**Takes:** `OtpPurpose` value  
**Returns:** frozen `OTPPolicy` dataclass  

Check these fields before processing any OTP request:

| Field | Type | Meaning |
|---|---|---|
| `enable` | `bool` | Whether OTP is active for this purpose |
| `require_auth` | `bool` | Caller must be authenticated |
| `check_user_exists` | `bool` | Verify user exists first |
| `allow_duplicate` | `bool` | Multiple active OTPs allowed |
| `require_identifier` | `bool` | `user_identifier` field is mandatory |
| `channel` | `OtpChannel` | Forced channel, or `ALL` to let caller choose |

---

## emails

### `emails/services/otp.py`

#### `send_otp_email(email, otp, otp_purpose)`
**Takes:** recipient email string, plaintext OTP string, `OtpPurpose` value  
**Returns:** `None`  

Queues an HTML OTP email via Celery. Called internally by `OTPService.send()` — prefer that over calling this directly.

---

## core

### `services/health_check.py`

#### `health_report()`
**Takes:** nothing  
**Returns:** dict with `debug_status`, `success_count`, `fail_count`, and a `services` list  

Runs live checks against the database, Redis, SMTP, Celery workers, and Celery Beat. SMTP result is cached for 60 seconds; all others run on every call. Use only in the health check view.
