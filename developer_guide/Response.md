# Response Reference

Every response from this API — whether returned manually from a view or generated automatically by the framework — produces the same shape:

```json
{
  "success": true | false,
  "message": "...",
  "data": null | { ... } | [ ... ],
  "errors": null | { "field": ["msg"] } | ["msg"]
}
```

---

## Table of Contents

- [apps/core/utils/response.py](#coreutilsresponsepy)
  - [success_response](#success_response)
  - [error_response](#error_response)
- [apps/core/utils/exception_handler.py](#coreutilsexception_handlerpy)
  - [custom_exception_handler](#custom_exception_handler)
  - [handle_404](#handle_404)
  - [handle_500](#handle_500)
- [The `errors` Field](#the-errors-field)
- [Debug Mode](#debug-mode)
- [Rule](#rule)

---

## `apps/core/utils/response.py - (Manual responses)`

### `success_response`

**Takes:** message string (default `"Success"`), optional data payload, optional status code (default `200`)  
**Returns:** DRF `Response` with `success: true`  

Use for every successful response from a view.

```python
# No payload
return success_response(message="Logged out successfully")

# With payload
return success_response(
    message="User registered successfully",
    data={"email": user.email, "access": token},
    status_code=201,
)
```

---

### `error_response`

**Takes:** keyword-only — message string (default `"Something went wrong."`), optional `errors`, optional `data`, optional `status_code` (default `500`), optional `request`, optional raw `exc`  
**Returns:** DRF `Response` with `success: false`  

Use for every error you return manually from a view. All parameters are keyword-only.

```python
# No detail needed — message is enough
return error_response(message="Refresh token is required", status_code=400)

# Serializer failed — pass errors for field-level feedback
if not serializer.is_valid():
    return error_response(
        message="Invalid registration data",
        errors=serializer.errors,
        status_code=400,
    )

# Caught exception — pass exc for debug traceback
try:
    change_password(request.user, new_password)
except Exception as e:
    return error_response(message="Password change failed", exc=e, status_code=400)
```

**`errors` vs `exc`:**

| Parameter | Purpose | Shown in production |
|---|---|---|
| `errors` | User-facing field feedback. Appears in the response `errors` field. | Yes |
| `exc` | Raw exception for debug traceback only. | Never |

**`errors` is normalized automatically:**

| What you pass | What `errors` becomes |
|---|---|
| `serializer.errors` dict | `{"field": ["message"]}` |
| `Exception` | `["exception string"]` |
| `DjangoValidationError` with field dict | `{"field": ["message"]}` |
| `DjangoValidationError` with messages | `["message"]` |
| `list` | list of strings |
| `None` | `null` |

---

## `apps/core/utils/exception_handler.py - (Rise Exceptions Handling Process)`

### `custom_exception_handler`

**Wired via:** `REST_FRAMEWORK["EXCEPTION_HANDLER"]` in `settings.py`  
**Takes:** DRF exception, request context (injected by DRF — not called manually)  
**Returns:** DRF `Response` via `error_response()`  

Intercepts every DRF exception before the response is sent and reformats it using `error_response()`. You do not call this directly — raise exceptions normally and this handles the rest.

| Scenario | Response message |
|---|---|
| Serializer validation failure | `"Validation failed."` + `errors` dict |
| Missing auth token | `"Authentication credentials were not provided."` |
| Bad or expired token | `"Authentication failed."` |
| Permission check failed | `"You do not have permission to perform this action."` |
| Rate limit exceeded | `"Too many requests. Try again in N second(s)."` |
| `raise NotFound()` | `"The requested resource was not found."` |
| `raise PermissionDenied()` | `"You do not have permission to perform this action."` |
| Unhandled exception in view | `"Internal server error."` (500) |

To trigger automatic handling, raise normally — do not wrap in try/except unless you need a custom message:

```python
serializer.is_valid(raise_exception=True)
raise ValidationError({"email": ["Already taken"]})
raise PermissionDenied()
```

---

### `handle_404`

**Wired via:** `handler404` in `urls.py`  
**Takes:** Django request, optional exception (injected by Django — not called manually)  
**Returns:** `JsonResponse` built from `error_response()` with status 404  

Triggered when no URL pattern matches the request.

```json
{ "success": false, "message": "The requested endpoint does not exist.", "data": null, "errors": null }
```

---

### `handle_500`

**Wired via:** `handler500` in `urls.py`  
**Takes:** Django request (injected by Django — not called manually)  
**Returns:** `JsonResponse` built from `error_response()` with status 500  

Triggered on unrecoverable server errors outside DRF's handling.

```json
{ "success": false, "message": "Internal server error.", "data": null, "errors": null }
```

---

## The `errors` Field

- **`null`** — no field-level detail. The `message` is the full story.
- **`dict`** — field-level errors. Each key is a field name; each value is a list of strings. Use to highlight specific form inputs on the frontend.
- **`list`** — non-field errors. Use to display a general error banner.

---

## Debug Mode

When `DEBUG=True`, error responses include an extra `debug` field — never present in production:

```json
"debug": {
  "exception": "ValidationError",
  "traceback": "Traceback (most recent call last): ..."
}
```

Passing `request=request` to `error_response()` also adds path, method, and payload to the debug block.

---

## Rule

Every response that leaves a view goes through `success_response()` or `error_response()`. Never return a raw `Response({...})` directly.
