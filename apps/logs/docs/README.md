# Logs Module

## Table of Contents

1. [Overview](#1-overview)
2. [SystemLog Model](#2-systemlog-model)
3. [Logging Service API](#3-logging-service-api)
4. [Request Context Middleware](#4-request-context-middleware)
5. [Database Handler](#5-database-handler)
6. [JSON Formatter](#6-json-formatter)
7. [File Logging](#7-file-logging)
8. [Admin Interface](#8-admin-interface)
9. [Log Levels](#9-log-levels)
10. [Configuration](#10-configuration)
11. [Integration with External Platforms](#11-integration-with-external-platforms)

---

## 1. Overview

The `logs` app is the central observability and audit system for the application. It captures structured log data from every significant event — API calls, business operations, errors, and system events — and persists them in a queryable `SystemLog` model as well as to rotating log files and structured JSON output.

Key features:

- **Structured audit trail** — Every log entry captures actor identity, request metadata, source location, and business context.
- **Request context propagation** — Request-level metadata (request ID, IP address, user agent, actor info) is automatically injected into every log entry produced during a request lifecycle using Python `contextvars`.
- **Non-blocking writes** — The database handler uses a background queue (`QueueListener`) to avoid blocking the request thread on log writes.
- **JSON output** — Structured JSON logs are compatible with Datadog, ELK Stack, Grafana Loki, and Splunk.
- **Custom `SUCCESS` level** — An additional log level between `WARNING` and `ERROR` for recording successful business operations.

### File Structure

```
apps/logs/
├── migrations/
├── docs/
│   └── README.md           # This file
├── logs_output/            # Rotating log files (git-ignored)
├── admin.py                # SystemLog admin with colored levels
├── apps.py
├── choices.py              # LogLevel and ActorType enums
├── context.py              # contextvars definitions
├── handlers.py             # DatabaseHandler, QueueListener setup
├── logging_config.py       # get_logging_config() factory
├── middleware.py           # LoggingContextMiddleware
├── models.py               # SystemLog model
├── services.py             # log_debug(), log_info(), log_error(), etc.
└── utils.py                # extract_caller_info(), extract_traceback()
```

---

## 2. SystemLog Model

**Module:** `apps.logs.models.SystemLog`

The central log store. Each row represents one log event with full contextual information.

### Fields

| Field | Type | Description |
|---|---|---|
| `timestamp` | `DateTimeField` | When the event occurred (set at write time) |
| `log_level` | `CharField` | Severity level (see [Log Levels](#9-log-levels)) |
| `event_name` | `CharField` | Short identifier for the event type (e.g., `USER_LOGIN`) |
| `message` | `TextField` | Human-readable log message |
| `actor_type` | `CharField` | Who triggered this event (`USER`, `SYSTEM`, `SERVICE`, `ANONYMOUS`) |
| `actor_id` | `CharField` | ID of the actor (user ID, service name, etc.) |
| `actor_email` | `EmailField` | Email of the actor, if applicable |
| `business_id` | `CharField` | Tenant or business identifier (from `X-Business-ID` header) |
| `model_name` | `CharField` | The Django model involved (if any) |
| `file_name` | `CharField` | Source file where the log was produced |
| `function_name` | `CharField` | Function name where the log was produced |
| `traceback` | `TextField` | Full exception traceback (for error logs) |
| `metadata` | `JSONField` | Arbitrary structured data for context |
| `service_name` | `CharField` | Name of the service or component |
| `request_id` | `CharField` | Unique request identifier (from `X-Request-ID` header) |
| `ip_address` | `GenericIPAddressField` | Client IP address |
| `user_agent` | `TextField` | Client user agent string |
| `created_at` | `DateTimeField` | Database insertion timestamp |

### Indexes

The following fields are indexed for query performance:

- `event_name`
- `log_level`
- `actor_type`
- `actor_id`

---

## 3. Logging Service API

**Module:** `apps.logs.services`

Use these functions throughout the application to produce structured logs. Do not use Python's `logging` module directly for business events — these functions ensure all required context is captured.

### Functions

All functions share the same signature:

```python
log_<level>(
    event_name: str,
    message: str,
    *,
    request=None,
    actor_type: ActorType = ActorType.SYSTEM,
    actor_id: str = None,
    actor_email: str = None,
    model_name: str = None,
    metadata: dict = None,
    service_name: str = None,
)
```

| Function | Level | When to Use |
|---|---|---|
| `log_debug()` | `DEBUG` | Detailed diagnostic information during development |
| `log_info()` | `INFO` | Routine operational events (startup, config loaded) |
| `log_success()` | `SUCCESS` | Successful completion of a business operation |
| `log_warning()` | `WARNING` | Unexpected state that doesn't require immediate action |
| `log_error()` | `ERROR` | Operation failed; requires investigation |
| `log_critical()` | `CRITICAL` | System-level failure; requires immediate attention |

### Examples

```python
from apps.logs.services import log_success, log_error, log_warning
from apps.logs.choices import ActorType

# Log a successful user registration
log_success(
    event_name="USER_REGISTERED",
    message=f"New user registered: {user.email}",
    request=request,
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    actor_email=user.email,
)

# Log a failed payment
log_error(
    event_name="PAYMENT_FAILED",
    message="Payment gateway returned error code 402",
    request=request,
    metadata={"gateway_response": response_data, "order_id": order.id},
)

# Log a warning about a deprecated API call
log_warning(
    event_name="DEPRECATED_ENDPOINT_CALLED",
    message="Client called deprecated /v1/users endpoint",
    request=request,
    metadata={"path": request.path, "user_agent": request.META.get("HTTP_USER_AGENT")},
)
```

### Automatic Context Injection

When `request` is provided, the following fields are populated automatically from the request context:

- `actor_id`, `actor_email` — from `request.user` if authenticated
- `ip_address` — from `X-Forwarded-For` or `REMOTE_ADDR`
- `user_agent` — from `HTTP_USER_AGENT`
- `request_id` — from the `X-Request-ID` header or context variable
- `business_id` — from the `X-Business-ID` header or context variable

Even without `request`, these fields are populated from the active `contextvars` context set by the middleware (as long as the code runs within a request lifecycle).

---

## 4. Request Context Middleware

**Module:** `apps.logs.middleware.LoggingContextMiddleware`

This middleware runs on every request and populates Python `contextvars` with request-level metadata. Because `contextvars` are scoped to the current async task or thread, all downstream code — views, services, tasks called synchronously — can read this context without needing to pass `request` objects around.

### What It Captures

| Context Variable | Source | Description |
|---|---|---|
| `request_id_var` | `X-Request-ID` header (or auto-generated UUID) | Unique identifier for this request |
| `actor_id_var` | `request.user.id` (if authenticated) | ID of the authenticated user |
| `actor_email_var` | `request.user.email` (if authenticated) | Email of the authenticated user |
| `ip_address_var` | `X-Forwarded-For` → `REMOTE_ADDR` | Client IP address |
| `user_agent_var` | `HTTP_USER_AGENT` | Client user agent string |
| `business_id_var` | `X-Business-ID` header | Multi-tenant business identifier |

### Middleware Position

`LoggingContextMiddleware` must be **last** in the `MIDDLEWARE` list to ensure that authentication has already been processed:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # ...
    'apps.logs.middleware.LoggingContextMiddleware',  # ← Last
]
```

---

## 5. Database Handler

**Module:** `apps.logs.handlers.DatabaseHandler`

A custom Python logging `Handler` that writes log records to the `SystemLog` model. To prevent log writes from blocking the request-response cycle, all writes are handled asynchronously via a `QueueListener`:

```
logging.Logger → QueueHandler → Queue → QueueListener → DatabaseHandler → SystemLog
                                                                          (background thread)
```

This means log writes are near-instant from the perspective of the application code; the actual database insert happens in a background thread.

---

## 6. JSON Formatter

**Module:** `apps.logs.logging_config` (via `JSONFormatter`)

When logs are written to files, the `JSONFormatter` produces one JSON object per line:

```json
{
  "timestamp": "2026-05-15T10:23:45.123Z",
  "level": "ERROR",
  "event": "PAYMENT_FAILED",
  "message": "Payment gateway returned error code 402",
  "request_id": "a1b2c3d4-...",
  "actor_id": "42",
  "service": "my_backend",
  "file": "apps/payments/services.py",
  "function": "process_payment"
}
```

This format is directly ingestible by:
- **Datadog** — via the Datadog Agent file tail or Fluentd
- **ELK Stack** — via Filebeat + Logstash
- **Grafana Loki** — via Promtail
- **Splunk** — via Universal Forwarder

---

## 7. File Logging

Log files are written to `apps/logs/logs_output/` (git-ignored).

| File | Content | Rotation |
|---|---|---|
| `app.log` | All log levels | Daily, 30-day retention |
| `error.log` | `WARNING` and above only | Daily, 30-day retention |

---

## 8. Admin Interface

**Module:** `apps.logs.admin.SystemLogAdmin`

The admin provides a rich interface for reviewing log history:

- **List display:** timestamp, log\_level (colored), event\_name, actor\_type, actor\_email, ip\_address
- **Filters:** log\_level, actor\_type, timestamp
- **Search:** event\_name, message, actor\_email, request\_id
- **All fields are read-only** — Logs are immutable records
- **Log level colors** — Levels are color-coded for quick visual scanning

Access at: `/admin/logs/systemlog/`

---

## 9. Log Levels

Defined in `apps/logs/choices.py` as `LogLevel`.

| Level | Value | Use When |
|---|---|---|
| `DEBUG` | `10` | Granular diagnostic info, only useful during development |
| `INFO` | `20` | Normal operational events |
| `SUCCESS` | `25` | A business operation completed successfully (custom level) |
| `WARNING` | `30` | Something unexpected, but the system is still functioning |
| `ERROR` | `40` | An operation failed and needs investigation |
| `CRITICAL` | `50` | A system-wide failure requiring immediate action |

`SUCCESS` sits between `INFO` and `WARNING`. It is a custom level unique to this application, providing a clear way to signal positive outcomes without conflating them with routine informational messages.

---

## 10. Configuration

The logging configuration is generated by `apps.logs.logging_config.get_logging_config()`, which is called in `my_django/settings.py`:

```python
from apps.logs.logging_config import get_logging_config
LOGGING = get_logging_config(service_name="my_backend")
```

The `service_name` parameter appears in every log record as the `service_name` field, making it easy to filter logs from this service in multi-service environments.

### Log Output in Production vs Development

| Environment | Console Output | File Output | Database Output |
|---|---|---|---|
| Development (`DEBUG=True`) | Yes | Yes | Yes |
| Production (`DEBUG=False`) | No | Yes | Yes |

---

## 11. Integration with External Platforms

### Datadog

Point the Datadog Agent's log collection at `apps/logs/logs_output/app.log` using the JSON multiline processor. The `request_id` field enables trace correlation.

### ELK Stack

Use Filebeat with the `json.keys_under_root: true` option to ship log files to Elasticsearch. The structured fields map directly to Elasticsearch document fields.

### Sentry

For exception tracking in Sentry, integrate `sentry-sdk` and configure it alongside the existing logger. The `request_id` and `actor_id` fields can be set as Sentry tags for correlation.

### Custom Alerting

Query `SystemLog` directly for alerting thresholds:

```python
from apps.logs.models import SystemLog
from apps.logs.choices import LogLevel
from django.utils import timezone
from datetime import timedelta

# Count critical errors in the last hour
recent_criticals = SystemLog.objects.filter(
    log_level=LogLevel.CRITICAL,
    created_at__gte=timezone.now() - timedelta(hours=1),
).count()
```
