# Django Activity Tracking System Documentation

This document provides a step-by-step, easy-to-understand explanation of the activity tracking system implemented in this Django project. It pairs with [`apps/logs/README.md`](../logs/README.md) — read that one first if you haven't already, since this system reuses its `request_id`.

## 🌟 Overview
This activity system is designed to be **asynchronous, non-blocking, and correlated with the logs system without being coupled to it**. Every tracked HTTP request produces one `UserActivity` row — who made the request, which service/action it hit, how long it took, what device they used. It never writes synchronously and never shares a database table with `logs` — the two systems are joined only by a shared `request_id` string, at query time.

---

## 🔄 The Step-by-Step Flow

1. **HTTP Request Arrives (Middleware):** `apps.logs.middleware.LoggingContextMiddleware` runs first and sets `request.request_id`. Right after it, `apps.activity.middleware.ActivityTrackingMiddleware` runs — it resolves (or creates) the user's `UserSession` and records a start timestamp.
2. **The View Runs:** Business logic executes as normal — the activity system doesn't touch it at all.
3. **Response Comes Back (Middleware):** `ActivityTrackingMiddleware._process_response()` computes how long the request took, then calls `record_activity()` with that duration and `request.request_id`.
4. **Payload Built (Services):** `record_activity()` calls `_build_activity_payload()`, which figures out the `service` name (from the URL prefix, via `constants.py`), the `action` (from the HTTP method + path), the IP, device type, etc. — everything `UserActivity.objects.create()` needs.
5. **Sent to Celery (Tasks):** The payload is dispatched to `record_activity_task` on the isolated `"activity"` Celery queue — this returns immediately, so the HTTP response is never delayed by the DB write.
6. **Saved (Celery Worker):** A Celery worker picks up the task and creates the `UserActivity` row completely outside the request/response cycle.

Meanwhile, on login/logout, `apps.activity.apps.ActivityConfig.ready()` has wired Django's `user_logged_in`/`user_logged_out` signals to start/end a `UserSession` row — this is the thing `UserActivity.session` points to.

---

## 📂 File By File & Function By Function Explanation

### 1. `middleware.py`
**Purpose:** Wraps every request to time it and tag it with the current session, then hands off to `services.record_activity()` after the response is ready.
* `_process_request(request)`: Records a `time.monotonic()` start time and resolves the caller's active `UserSession` (Redis-cached, DB fallback, `start_session()` as a last resort).
* `_process_response(request, response)`: Computes `duration_ms`, skips admin/static/media paths, and calls `record_activity(...)`. The whole thing is wrapped in `try/except` so a bug here can never break the actual HTTP response.

### 2. `constants.py`
**Purpose:** Maps URL prefixes to service names and HTTP methods/paths to `ActivityAction` values — this is how `UserActivity.service` and `UserActivity.action` get filled in without the developer having to specify them manually.
* `resolve_service(path)`: Longest-prefix match against `SERVICE_ROUTES`.
* `resolve_action(method, path)`: Checks `PATH_ACTION_OVERRIDES` first (e.g. `/v1/auth/login/` → `login`), then falls back to a generic method→action mapping.

### 3. `services.py`
**Purpose:** The main interface the middleware uses to record activity and manage sessions.
* `start_session(user, request)`: Creates a `UserSession` row synchronously — cheap, happens once per login.
* `end_session(session_key)`: Dispatches the Celery task that closes a session — never blocks the logout response.
* `_build_activity_payload(...)`: Gathers everything needed for a `UserActivity` row into a plain dict (not a model instance — it has to survive being serialized through Celery).
* `record_activity(...)`: Builds the payload and dispatches it to Celery. Wrapped in `try/except` — a broken analytics write is logged as a WARNING via the `logs` app, never raised.

### 4. `tasks.py`
**Purpose:** The actual database writes, running on a Celery worker instead of the request thread.
* `record_activity_task(self, payload)`: `UserActivity.objects.create(**payload)`. Retries on transient DB errors; drops the row (with a warning) on integrity errors since those aren't transient.
* `end_session_task(self, session_key)`: Marks a `UserSession` as ended.

### 5. `apps.py`
**Purpose:** Wires session lifecycle into Django's built-in auth signals — this project doesn't call `start_session`/`end_session` from any view directly.
* `_on_user_logged_in(...)`: Reuses an existing active session if one's cached/found, otherwise starts a new one.
* `_on_user_logged_out(...)`: Looks up the session key (cache or DB) and dispatches `end_session()`.

### 6. `models.py`
**Purpose:** Database representations.
* `UserSession`: One row per login session — device, IP, start/end times.
* `UserActivity`: One row per tracked request — owns `service`, `path`, `method`, `status_code`, `duration_ms`, etc. directly (no FK to any shared "request" table), plus `request_id` as a plain string that happens to match the `request_id` on the `SystemLog` row from the same request.

### 7. `admin.py`
**Purpose:** Read-only Django admin views for both models — useful for spot-checking traffic and tracing an incident by searching `request_id`.

---

## 🔗 Why `request_id` and not a Foreign Key?

It's tempting to add a FK from `UserActivity` to `SystemLog` (or a shared "request" table both point to) so you can `.select_related()` your way to a joined view. This project deliberately doesn't do that:

- A FK means both systems have to succeed writing to the *same* row's context, which either forces a synchronous write on the hot path, or leaves you handling partial-write failures.
- If `logs` or `activity` ever needs to be scaled, disabled, or ripped out independently, a FK between them makes that a migration, not a config change.
- The two systems already write asynchronously and independently — `logs` via a background queue thread, `activity` via Celery. A FK would undo that independence.

Instead, both models just carry the same `request_id` string. Correlating them is one query:

```sql
SELECT sl.event_name, sl.log_level, ua.service, ua.duration_ms
FROM logs_systemlog sl
JOIN activity_user_activity ua ON ua.request_id = sl.request_id
WHERE sl.request_id = '<uuid-from-either-table>';
```
