# Utilities Reference

---

## Table of Contents

- [core](#core)
  - [utils/general.py](#utilsgeneralpy)
  - [utils/generators.py](#utilsgeneratorspy)
  - [utils/validators.py](#utilsvalidatorspy)
  - [utils/query.py](#utilsquerypy)
  - [utils/decorators.py](#utilsdecoratorspy)
  - [utils/health_response.py](#utilshealth_responsepy)
  - [utils/app_model_relate.py](#utilsapp_model_relatepy)
  - [tasks.py](#coretaskspy)
- [authentication](#authentication)
  - [throttles.py](#authenticationthrottlespy)
  - [managers/user.py](#authenticationmanagersusерpy)
- [otp](#otp)
  - [throttles.py](#otpthrottlespy)
- [emails](#emails)
  - [tasks.py](#emailstaskspy)

---

## core

### `utils/general.py`

#### `get_or_400(data, keys, required, required_together)`
**Takes:** request data dict, dict mapping each field name to its expected type — a type, a tuple of types, or `None` to skip type checking — optional list of individually required fields, optional list of groups where at least one field per group must be present  
**Returns:** `(True, dict)` on success — dict contains extracted values; `(False, Response)` on failure — Response is a ready-to-return 400 error listing missing fields and/or wrong data types  

Type checks apply only to present (non-None) values. Always check the first element before using the second:
```python
ok, result = get_or_400(
    data=request.data,
    keys={"email": str, "otp": str, "age": (int, float), "extra": None},
    required=["email", "otp"],
)
if not ok:
    return result
```

---

#### `availability_check(data)`
**Takes:** dict of key-value pairs  
**Returns:** `(True, None)` if all values are non-None; `(False, Response)` if any value is None — Response is a ready-to-return 400 error  

Use after resolving values from DB or request to confirm nothing is missing before proceeding.

---

#### `str_replace_from_dict(text, replacements)`
**Takes:** string with placeholders, dict mapping placeholder strings to replacement values  
**Returns:** string with all substitutions applied  

```python
str_replace_from_dict("Hello {{name}}, code: {{code}}", {"{{name}}": "Sara", "{{code}}": "4821"})
# → "Hello Sara, code: 4821"
```

---

#### `update_record(qs, data)`
**Takes:** queryset, dict of field-value pairs  
**Returns:** the queryset after calling `.update(**data)`  

Calls queryset `.update()` — bypasses model `.save()` and signals. Use only when that is intentional.

---

### `utils/generators.py`

#### `random_string(length, allow_numbers, allow_capital, allow_small, allow_special)`
**Takes:** length (required, positive int), four boolean flags for character sets — numbers (default `True`), capitals, lowercase, specials (all others default `False`)  
**Returns:** cryptographically secure random string of the given length  
**Raises:** `ValueError` if no character set is enabled, or length is zero or negative  

---

### `utils/validators.py`

#### `validate_phone(phone, region)`
**Takes:** phone number string, optional ISO 3166-1 alpha-2 region code (e.g. `"BD"`, `"US"`) — required for local numbers without a country prefix  
**Returns:** E.164 formatted number string (e.g. `"+8801712345678"`)  
**Raises:** `ValidationError` if the number is invalid for the given region  

---

#### `DataSerializer(value)`
**Takes:** a raw value — string, int, or bool  
**Returns instance with:** `.to_bool()` — converts truthy strings (`"true"`, `"1"`, `"yes"`, `"on"`) and booleans to `True`/`False`  

---

### `utils/query.py`

#### `is_exists(model, **kwargs)`
**Takes:** a Django model class, plus any filter kwargs  
**Returns:** `True` if a matching record exists, `False` otherwise  

Single optimised query via `.filter().exists()`. No model instance is loaded.

---

### `utils/decorators.py`

#### `is_admin(user)`
**Takes:** user object  
**Returns:** `True` if user is authenticated and `is_staff=True`, otherwise `False`  

---

#### `IsAdminUser` (DRF permission class)
**Use on:** `permission_classes` of class-based API views  
**Behaviour:** returns 401 for unauthenticated requests, 403 for authenticated non-staff users  

---

#### `@admin_required` (decorator)
**Use on:** function-based views  
**Behaviour:** returns 401 if not authenticated, 403 if authenticated but not staff  

---

#### `@authorize` (decorator)
**Takes:**
- `strict` or `role`/`roles`: role code string or list of role codes
- `permission` or `permissions`: permission code string (`"app.codename"`) or list of permissions
- `operator`: `"AND"` (default) or `"OR"` (composition between role check and permission check)
- `role_operator`: `"ALL"` (default) or `"ANY"` (when multiple roles provided)
- `permission_operator`: `"ALL"` (default) or `"ANY"` (when multiple permissions provided)
- `object_getter`: optional callable `(request, *args, **kwargs) -> obj` for object-level check

**Use on:** function-based views, class-based view handler methods (`get`, `post`, etc.), or async view functions.  
**Behaviour:** returns standardized 401 error if unauthenticated, 403 if unauthorized. Genuinely async-safe (uses `sync_to_async`).

```python
@authorize(strict="SUPER_ADMIN")
def delete_user(request, user_id): ...

@authorize(permission="projects.view_project")
def project_list(request): ...

@authorize(strict="PROJECT_MANAGER", permission="projects.change_project", operator="AND")
def update_project(request, project_id): ...
```

---

### `utils/permissions.py`

#### `HasRole(*roles, require_all=False)` (DRF permission class)
**Use on:** `permission_classes = [HasRole("SUPER_ADMIN")]`

---

#### `HasPermission(*permissions, require_all=True)` (DRF permission class)
**Use on:** `permission_classes = [HasPermission("projects.view_project")]`

---

#### `AuthorizePermission(roles=None, permissions=None, operator="AND")` (DRF permission class)
**Use on:** `permission_classes = [AuthorizePermission(roles=["ADMIN"], permissions=["projects.view_project"], operator="OR")]`

---

#### `check_object_permission(user, permission, obj)`
**Takes:** user instance, permission string, target model instance  
**Returns:** `bool` — checks object-level ownership or custom `has_object_permission` hook.


---

### `utils/health_response.py`

#### `health_ok_response(name, message)`
**Takes:** component name string, status message string  
**Returns:** `{"name": ..., "status": "healthy", "message": ...}`  

For use only inside `core/health/` check functions.

---

#### `health_error_response(name, message, errors=None)`
**Takes:** component name string, status message string, optional exception  
**Returns:** `{"name": ..., "status": "unhealthy", "message": ..., "error": str(errors)}`  

For use only inside `core/health/` check functions.

---

### `utils/app_model_relate.py`

#### `ModelInspector`
Zero-DB-hit utility for reflecting on the Django app registry.

| Method | Takes | Returns |
|---|---|---|
| `get_all_apps(app_labels=None)` | optional list of app label strings | list of app config objects |
| `get_models(app_configs=None, model_names=None)` | optional list of app configs, optional model name filter | list of model classes |
| `get_model_fields(model, field_names=None)` | model class or instance, optional field name filter | list of non-relation field objects |

---

### `core/tasks.py`

#### `beat_heartbeat` (Celery task)
**Takes:** nothing  
**Returns:** nothing  

Writes current UTC timestamp to `"beat_last_seen"` cache key. Scheduled every 60 seconds by Celery Beat. Do not call manually.

---

## authentication

### `authentication/throttles.py`

| Class | Scope key | Applied to |
|---|---|---|
| `RegisterThrottle` | `register` | `RegisterView` |
| `LoginThrottle` | `login` | `LoginView` |
| `ChangePasswordThrottle` | `change_password` | `ChangePasswordView` |

Rates are set in `settings.py` under `DEFAULT_THROTTLE_RATES`.

---

### `authentication/managers/user.py`

#### `UserManager.create_user(email, password, **extra_fields)`
**Takes:** email string (required, non-empty), password, any additional model fields  
**Returns:** saved User instance  

---

#### `UserManager.create_superuser(email, password, **extra_fields)`
**Takes:** email string, password, any additional model fields  
**Returns:** saved User instance with `is_staff=True` and `is_superuser=True`  
**Raises:** `ValueError` if either flag is explicitly passed as `False`  

---

## otp

### `otp/throttles.py`

| Class | Scope key | Applied to |
|---|---|---|
| `GetOtpRateThrottle` | `get_otp` | `GetOtpView` |

Rate is per-day. Configured in `settings.py` under `DEFAULT_THROTTLE_RATES`. Subclasses `UserRateThrottle`, so authenticated requests are keyed by user id and anonymous requests by IP — auth-required OTP purposes stay rate-limited too.

---

## emails

### `emails/tasks.py`

#### `send_email_task` (Celery task)
**Takes:** `subject`, `to_emails` (list), `body`, `body_type` (`EmailBodyType` value)  
**Returns:** nothing  

Always call with `.delay()` or `.apply_async()`. Retries up to 3 times on `SMTPException` with 30-second backoff. Do not call synchronously.
