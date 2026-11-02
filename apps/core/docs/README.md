# Core Module

## Table of Contents

1. [Overview](#1-overview)
2. [Health Check System](#2-health-check-system)
3. [Response Helpers](#3-response-helpers)
4. [Utility Functions](#4-utility-functions)
5. [Redis Client](#5-redis-client)
6. [Validators & Generators](#6-validators--generators)
7. [Background Tasks](#7-background-tasks)
8. [Usage Examples](#8-usage-examples)

---

## 1. Overview

The `core` app is the shared foundation of the application. It does not represent a business domain — instead it houses the building blocks that every other module relies on: standardized response formatting, reusable query helpers, validation utilities, a singleton Redis client, and system health monitoring.

No other app should duplicate logic that belongs here. When writing code that is generic and could be useful across more than one module, it belongs in `core`.

### File Structure

```
apps/core/
├── migrations/
├── docs/
│   └── README.md           # This file
├── admin.py
├── apps.py
├── decorators.py           # Custom decorators
├── general.py              # General-purpose helpers
├── generators.py           # Random string / token generation
├── query.py                # Query shorthand utilities
├── redis_client.py         # Singleton Redis connection
├── response.py             # Standardized API response builders
├── services.py             # Health check service
├── tasks.py                # Celery tasks (heartbeat)
├── validators.py            # Phone number validators
├── validators.py           # DataSerializer for type coercion
├── views.py                # HealthReportView
└── urls.py                 # URL patterns
```

---

## 2. Health Check System

### Endpoint

`GET /`

No authentication required. Returns the real-time operational status of all critical infrastructure components.

**Success Response — `200 OK`:**

```json
{
  "success": true,
  "message": "Health report",
  "data": {
    "database": { "status": "healthy" },
    "redis": { "status": "healthy" },
    "email_service": { "status": "healthy" },
    "celery_worker": { "status": "healthy" },
    "celery_beat": { "status": "healthy" }
  }
}
```

Each component returns either `{ "status": "healthy" }` or `{ "status": "unhealthy", "error": "<reason>" }`.

### Checked Components

| Component         | Method                  | What It Tests                                        |
| ----------------- | ----------------------- | ---------------------------------------------------- |
| **Database**      | `check_database()`      | Executes a simple query against the default DB       |
| **Redis**         | `check_redis()`         | Pings the Redis server via the singleton client      |
| **Email Service** | `check_email_service()` | Opens and closes an SMTP connection                  |
| **Celery Worker** | `check_celery_worker()` | Inspects active Celery workers                       |
| **Celery Beat**   | `check_celery_beat()`   | Reads the heartbeat key set by `beat_heartbeat` task |

### Implementation

All checks are aggregated by `health_report()` in `apps/core/services.py`. The view calls this service and returns the result as a standardized response.

```python
# apps/core/services.py
def health_report() -> dict:
    return {
        "database": check_database(),
        "redis": check_redis(),
        "email_service": check_email_service(),
        "celery_worker": check_celery_worker(),
        "celery_beat": check_celery_beat(),
    }
```

---

## 3. Response Helpers

**Module:** `apps.core.response`

All API views use these two functions to produce consistent response envelopes.

### `success_response(message, data=None, status=200)`

Returns a DRF `Response` object with `success: true`.

```python
from apps.core.response import success_response

return success_response("User created", data={"id": 1})
```

**Output:**

```json
{
  "success": true,
  "message": "User created",
  "data": { "id": 1 }
}
```

### `error_response(message, data=None, status=400)`

Returns a DRF `Response` object with `success: false`.

```python
from apps.core.response import error_response

return error_response("Invalid OTP", status=400)
```

**Output:**

```json
{
  "success": false,
  "message": "Invalid OTP",
  "data": null
}
```

> **Note:** In `DEBUG` mode, error responses may include additional diagnostic information in the `data` field.

---

## 4. Utility Functions

**Module:** `apps.core.utils.general`

### `get_or_400(data, keys, required=None, required_together=None)`

Extracts and validates request data. `keys` is a dict mapping each field name to its expected type — a type, a tuple of types, or `None` to skip type checking. Returns `(True, values_dict)` on success or `(False, Response)` where the Response is a ready-to-return 400 error listing missing required fields and/or wrong data types.

```python
from apps.core.utils.general import get_or_400

ok, result = get_or_400(
    data=request.data,
    keys={"email": str, "otp": str},
    required=["email", "otp"],
)
if not ok:
    return result
```

### `availability_check(data)`

Takes a dict of key-value pairs. Returns `(True, None)` if every value is non-None, or `(False, Response)` with a ready-to-return 400 error naming the missing keys. Useful after resolving values from the DB or request to confirm nothing is missing before proceeding.

```python
from apps.core.utils.general import availability_check

ok, error = availability_check({"user": user, "profile": profile})
if not ok:
    return error
```

### `str_replace_from_dict(text, replacements)`

Performs multiple string substitutions in a single pass using a dictionary mapping.

```python
from apps.core.general import str_replace_from_dict

result = str_replace_from_dict("Hello {name}!", {"{name}": "World"})
# "Hello World!"
```

### `update_record(instance, data)`

Updates a model instance's fields from a dictionary and calls `.save()`. Only updates fields that are present as attributes on the model.

```python
from apps.core.general import update_record

update_record(user, {"first_name": "Jane", "last_name": "Doe"})
```

### `is_exists(model, **kwargs)` — `apps.core.query`

Returns `True` if any record matching the given kwargs exists.

```python
from apps.core.query import is_exists

exists = is_exists(User, email='user@example.com')
```

---

## 5. Redis Client

**Module:** `apps.core.redis_client`

A singleton Redis client with connection pooling. Use this instead of creating raw Redis connections in other modules.

```python
from apps.core.redis_client import get_redis_client

redis = get_redis_client()
redis.set("my_key", "value", ex=300)   # TTL of 300 seconds
value = redis.get("my_key")
```

### Design

- Uses a connection pool internally for efficiency under concurrent load.
- Returns `None` gracefully if Redis is unavailable (connection failures are caught and logged).
- Configured with sensible socket timeouts to prevent hung connections.

---

## 6. Validators & Generators

### Phone Number Validation — `apps.core.validators`

**`validate_phone(phone_number, region=None)`**

Validates international phone numbers using the `phonenumbers` library.

```python
from apps.core.validators import validate_phone

try:
    validate_phone("+8801712345678")
except ValidationError as e:
    # Handle invalid number
```

Returns `True` if valid; raises `django.core.exceptions.ValidationError` if not.

### Data Type Coercion — `apps.core.validators.DataSerializer`

A lightweight utility class for converting raw strings (typically from `.env` or request data) into typed Python values.

```python
from apps.core.validators import DataSerializer

ds = DataSerializer("42")
number = ds.to_int()          # → 42
flag = DataSerializer("true").to_bool()  # → True
```

### Cryptographic Random Strings — `apps.core.generators`

**`random_string(length=32)`**

Generates a cryptographically secure random alphanumeric string using `secrets.token_hex`. Suitable for tokens, nonces, and temporary keys.

```python
from apps.core.generators import random_string

token = random_string(64)
```

### Model Introspection — `apps.core.app_model_relate.ModelInspector`

A utility class that reflects on the Django app registry to programmatically list apps, models, and their fields. Useful for admin tooling and dynamic report generation.

---

## 7. Background Tasks

**Module:** `apps.core.tasks`

### `beat_heartbeat`

A lightweight Celery task scheduled to run **every 1 minute** via Celery Beat. It writes a timestamp to Redis under a known key.

The `check_celery_beat()` health check reads this key to confirm that Beat is alive and scheduling tasks.

```python
# Defined in my_django/configs/celery_schedules.py
CELERY_BEAT_SCHEDULE = {
    "beat-heartbeat": {
        "task": "apps.core.tasks.beat_heartbeat",
        "schedule": 60.0,  # seconds
    }
}
```

---

## 8. Usage Examples

### Using the response helpers in a view

```python
from rest_framework.views import APIView
from apps.core.response import success_response, error_response

class MyView(APIView):
    def get(self, request):
        try:
            data = {"key": "value"}
            return success_response("Data retrieved", data=data)
        except Exception as e:
            return error_response("Something went wrong", status=500)
```

### Checking Redis health manually

```python
from apps.core.redis_client import get_redis_client

client = get_redis_client()
if client and client.ping():
    print("Redis is reachable")
```

### Validating request data in a view

```python
from apps.core.utils.general import get_or_400

def post(self, request):
    ok, result = get_or_400(
        data=request.data,
        keys={"email": str, "user_id": int},
        required=["email"],
    )
    if not ok:
        return result
    email = result["email"]
```
