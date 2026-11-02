# Activity Module

## Table of Contents

1. [Overview](#1-overview)
2. [UserSession Model](#2-usersession-model)
3. [UserActivity Model](#3-useractivity-model)
4. [Choices](#4-choices)
5. [Service & Action Routing](#5-service--action-routing)
6. [Services API](#6-services-api)
7. [Celery Tasks](#7-celery-tasks)
8. [ActivityTrackingMiddleware](#8-activitytrackingmiddleware)
9. [Login / Logout Signals](#9-login--logout-signals)
10. [Admin Interface](#10-admin-interface)
11. [Configuration](#11-configuration)
12. [Correlation with the Logs Module](#12-correlation-with-the-logs-module)

---

## 1. Overview

The `activity` app is the product-analytics system — it tracks which users visit which parts of
the API, how often, from what device, and for how long a session lasts. It is **not** a
replacement for [`logs`](../../logs/docs/README.md) (engineering observability / error tracking);
the two are deliberately independent systems that never share a table.

Key features:

- **Non-blocking writes** — every `UserActivity` row is written asynchronously via Celery on an
  isolated `"activity"` queue, so analytics never adds latency to the HTTP response.
- **Session tracking** — one `UserSession` row per login, started on `user_logged_in` and closed
  asynchronously on `user_logged_out`.
- **Correlation with `SystemLog`** — every `UserActivity` row carries the same `request_id` the
  `logs` module stamped onto the same HTTP request, so the two can be joined at query time without
  a foreign key.

### File Structure

```
apps/activity/
├── migrations/
├── docs/
│   └── README.md          # This file
├── admin.py                # UserSessionAdmin + UserActivityAdmin (read-only)
├── apps.py                 # ActivityConfig; wires user_logged_in / user_logged_out signals
├── choices.py               # DeviceType and ActivityAction enums
├── constants.py              # SERVICE_ROUTES, resolve_service(), resolve_action()
├── middleware.py              # ActivityTrackingMiddleware
├── models.py                   # UserSession + UserActivity
├── services.py                  # start_session(), end_session(), record_activity()
└── tasks.py                      # record_activity_task, end_session_task (Celery)
```

---

## 2. UserSession Model

**Module:** `apps.activity.models.UserSession`
**Table:** `activity_user_session`

One row per login session.

| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `created_at` / `updated_at` / `deleted_at` | DateTimeField | From `apps.core.models.BaseModel` |
| `user` | FK → `AUTH_USER_MODEL` | `on_delete=PROTECT` |
| `session_key` | CharField(100) | UUID4 string; unique + indexed |
| `started_at` | DateTimeField | `auto_now_add=True` |
| `ended_at` | DateTimeField | `null=True`; set asynchronously on logout |
| `ip_address` | GenericIPAddressField | `null=True` |
| `user_agent` | CharField(255) | Raw User-Agent header, truncated |
| `device_type` | CharField(20) | `desktop` / `mobile` / `tablet` / `unknown` |
| `is_active` | BooleanField | Indexed; `True` while the session is open |

**Indexes:** `(user, is_active)`, `(user, started_at)`, `(started_at)`.

**Property:** `duration_seconds` — `None` while `ended_at` is unset, otherwise the elapsed seconds.

---

## 3. UserActivity Model

**Module:** `apps.activity.models.UserActivity`
**Table:** `activity_user_activity`

One row per tracked HTTP request. Every field describing the request lives directly on this
model — there is no shared "request context" table.

| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `created_at` / `updated_at` / `deleted_at` | DateTimeField | From `apps.core.models.BaseModel` |
| `user` | FK → `AUTH_USER_MODEL` | `null=True` (anonymous requests allowed) |
| `session` | FK → `UserSession` | `null=True`, `on_delete=SET_NULL` |
| `request_id` | CharField(100) | `null=True`, indexed. **Soft correlation key to `logs.SystemLog.request_id` — never a FK.** |
| `service` | CharField(50) | Indexed; resolved from `SERVICE_ROUTES` |
| `action` | CharField(50) | Indexed; `ActivityAction` choices |
| `path` | CharField(500) | `request.path`, truncated |
| `method` | CharField(10) | GET / POST / PATCH / PUT / DELETE |
| `status_code` | PositiveSmallIntegerField | HTTP response status — required, always known when the task fires |
| `duration_ms` | PositiveIntegerField | `null=True`; request–response time |
| `ip_address` | GenericIPAddressField | `null=True` |
| `device_type` | CharField(20) | |
| `referrer` | CharField(500) | `HTTP_REFERER` header, truncated |
| `occurred_at` | DateTimeField | `auto_now_add=True` |

**Indexes:** `(user, service, occurred_at)`, `(service, action)`, `(occurred_at)`,
`(user, action, occurred_at)`, `(status_code, occurred_at)`. `request_id` has its own
single-column index via `db_index=True` — sufficient for `WHERE request_id = ?` lookups.

---

## 4. Choices

**`DeviceType`** — `desktop`, `mobile`, `tablet`, `unknown`. Detected in `_detect_device_type()`
via regex against the User-Agent header (mobile: `mobi|android|iphone`; tablet: `ipad|tablet`).

**`ActivityAction`** — `page_view`, `resource_created`, `resource_updated`, `resource_deleted`,
`search`, `export`, `login`, `logout`, `token_refresh`, `password_change`, `password_reset`,
`otp_requested`, `file_upload`, `unknown`.

---

## 5. Service & Action Routing

`apps/activity/constants.py` maps URL prefixes to logical service names, longest-prefix-first:

```python
SERVICE_ROUTES = {
    "/v1/auth/":          "auth",
    "/v1/otp/":            "otp",
    "/v1/notifications/":  "notifications",
    "/":                   "core",   # catch-all — always last
}
```

**When adding a new app**, add its URL prefix here so requests to it get attributed correctly.

`resolve_action(method, path)` picks the `ActivityAction`:
1. Check `PATH_ACTION_OVERRIDES` (substring match, e.g. `/v1/auth/login/` → `login`)
2. `GET` with `?q=` in the path → `search`
3. Fall back to `HTTP_METHOD_TO_ACTION` keyed on the HTTP verb
4. Fall back to `unknown`

---

## 6. Services API

### `start_session(user, request) -> UserSession`

Creates a session **synchronously** — this happens once per login, not per request, so there's no
need to push it through Celery. Called by the login signal handler and by the middleware's
`_get_or_create_session()` fallback.

### `end_session(session_key: str) -> None`

Dispatches `end_session_task.delay(session_key)` — returns immediately, never blocks the logout
response.

### `record_activity(request, response, session, duration_ms, request_id=None) -> None`

Builds the `UserActivity` payload (via `_build_activity_payload()`) and dispatches
`record_activity_task.apply_async(kwargs={"payload": payload}, queue="activity")`. The whole
function is wrapped in `try/except` — a dispatch failure is logged as a WARNING but never raises.

Called by `ActivityTrackingMiddleware._process_response()`.

---

## 7. Celery Tasks

Both use `bind=True`, `autoretry_for=(OperationalError,)`, `retry_kwargs={"max_retries": 3}`,
`retry_backoff=True`, `queue="activity"`.

| Task | Does |
|---|---|
| `record_activity_task(self, payload: dict)` | `UserActivity.objects.create(**payload)`. `IntegrityError` is logged and the row dropped (not retried — it's not transient). |
| `end_session_task(self, session_key)` | Sets `ended_at`/`is_active=False` on the matching `UserSession`. `DoesNotExist` is logged and not retried. |

**Worker command:**
```bash
celery -A my_django worker -Q activity,default -c 4
```

The `"activity"` queue is declared in `settings.py`:

```python
from kombu import Queue
CELERY_TASK_QUEUES = (
    Queue("default"),
    Queue("activity"),
)
```

Isolated from `"default"` so high-volume analytics writes never delay time-sensitive tasks
(emails, OTP dispatch).

---

## 8. `ActivityTrackingMiddleware`

**Position in `MIDDLEWARE`:** immediately after `apps.logs.middleware.LoggingContextMiddleware`.

```python
MIDDLEWARE = [
    ...
    'apps.logs.middleware.LoggingContextMiddleware',
    'apps.activity.middleware.ActivityTrackingMiddleware',  # AFTER logs middleware
]
```

This order is load-bearing — the middleware reads `request.request_id`, which
`LoggingContextMiddleware` sets unconditionally at the very start of its own `process_request()`.
No fallback (e.g. a ContextVar) is needed for the request path since the ordering guarantees it.

**`_process_request`** — records `_activity_start_time`; resolves (or creates) the caller's
`UserSession` via a Redis-cached lookup (`activity:session:{user.pk}`, 1 hour TTL) with a DB
fallback, and finally `start_session()` if no active session exists. Never raises — a failure
just leaves `request.activity_session = None`.

**`_process_response`** — skips paths in `ACTIVITY_SKIP_PATHS`, computes `duration_ms`, and calls
`record_activity(request, response, session, duration_ms, request_id=request.request_id)`. The
entire body is wrapped in `try/except` — activity tracking can never break the HTTP response.

---

## 9. Login / Logout Signals

Wired in `ActivityConfig.ready()`:

```python
user_logged_in.connect(_on_user_logged_in)
user_logged_out.connect(_on_user_logged_out)
```

- **Login:** reuse the active session if one exists (cache-first, then DB), otherwise
  `start_session()`. Writes the session key back to the Redis cache.
- **Logout:** reads the session key from cache (falling back to a DB query), dispatches
  `end_session()`, and clears the cache key.

Both handlers guard on `request is None` and wrap their body in `try/except` — a broken signal
handler must never break login/logout.

---

## 10. Admin Interface

Both `UserSessionAdmin` and `UserActivityAdmin` are fully read-only (no add/change/delete
permissions) — these are immutable audit records.

- **`UserSessionAdmin`** — list: user, session key (first 8 chars), device, IP, start/end,
  active, duration. Filterable by device type, active state, start date.
- **`UserActivityAdmin`** — list: user, service, action, method, status code, duration, device,
  timestamp. Searchable by user email, path, IP, and `request_id` — so an incident traced from a
  `SystemLog.request_id` can be looked up directly here.

---

## 11. Configuration

**`settings.ACTIVITY_SKIP_PATHS`** (optional override, default shown):

```python
ACTIVITY_SKIP_PATHS = ("/admin/", "/static/", "/media/", "/favicon.ico")
```

**Cache key:** `activity:session:{user.pk}` — TTL 3600s. Cache misses fall back to a DB query and
repopulate the cache; cache unavailability degrades gracefully (the middleware catches exceptions
and continues without a session reference).

---

## 12. Correlation with the Logs Module

`logs.SystemLog.request_id` and `activity.UserActivity.request_id` carry the same UUID for the
same HTTP request. This is a soft correlation key (the industry-standard correlation-ID pattern
used by OpenTelemetry, Segment, Snowplow, etc.) — a plain indexed string, **never a foreign key**.
The two apps write independently and asynchronously; correlation happens at query time only:

```sql
SELECT sl.event_name, sl.log_level, sl.message, ua.service, ua.action, ua.duration_ms
FROM logs_systemlog sl
JOIN activity_user_activity ua ON ua.request_id = sl.request_id
WHERE sl.request_id = '<uuid>';
```

**Why no FK:** a FK would force a synchronous shared write on the request path and couple
observability availability to the business workload. Keeping the two apps structurally
independent means either one can be modified, scaled, or even extracted without touching the
other. A small amount of field duplication (`ip_address`, user reference, timestamps) between the
two is accepted as the cost of that independence — it is not something to "clean up".

`request.request_id` is set unconditionally by `apps.logs.middleware.LoggingContextMiddleware` before
any other middleware runs, and `apps.activity.middleware.ActivityTrackingMiddleware` simply reads it
off the request object — no import of `logs` models is needed or allowed.
