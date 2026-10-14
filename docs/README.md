# Backend API — Project Documentation

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [Architecture Overview](#3-architecture-overview)
4. [Application Modules](#4-application-modules)
5. [Getting Started](#5-getting-started)
6. [Environment Configuration](#6-environment-configuration)
7. [Running the Project](#7-running-the-project)
8. [API Reference](#8-api-reference)
9. [Authentication & Authorization](#9-authentication--authorization)
10. [Background Tasks](#10-background-tasks)
11. [Logging & Observability](#11-logging--observability)
12. [Deployment](#12-deployment)
13. [Project Structure](#13-project-structure)

---

## 1. Project Overview

This is a production-grade Django REST API backend designed for scalability, maintainability, and security. The system provides a complete foundation for modern web applications, including user authentication with JWT tokens, OTP-based verification, transactional email delivery, comprehensive structured logging, and background task processing.

The backend follows a modular application architecture, where each concern is isolated into its own Django app with clearly defined responsibilities. This ensures that the codebase remains maintainable as the project grows.

### Core Capabilities

- **User Authentication** — Email-based registration and login with JWT access/refresh tokens, password management, and token blacklisting on logout.
- **OTP System** — A Redis-backed, purpose-driven one-time password system supporting multiple delivery channels with configurable policies per use case.
- **Email Service** — Asynchronous, Celery-powered email delivery with retry logic, HTML/text support, and a full audit trail.
- **Structured Logging** — A comprehensive logging framework that captures request context, actor identity, tracebacks, and business metadata into a queryable `SystemLog` model and structured JSON output for log aggregation platforms.
- **System Health Monitoring** — A built-in health check endpoint that reports the status of all critical infrastructure components: database, Redis, SMTP, Celery workers, and Celery Beat.

---

## 2. Technology Stack

| Layer | Technology | Version |
|---|---|---|
| **Language** | Python | 3.12 |
| **Framework** | Django | 5.2 |
| **API** | Django REST Framework | 3.16.1 |
| **Authentication** | SimpleJWT | 5.5.1 |
| **Database** | PostgreSQL | — |
| **Cache / Message Broker** | Redis | 7.x |
| **Task Queue** | Celery | 5.6.2 |
| **CORS** | django-cors-headers | 4.9.0 |
| **Phone Validation** | phonenumbers | 9.0.25 |
| **Configuration** | python-decouple | 3.8 |
| **Containerization** | Docker | — |

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                        Clients                          │
│                 (Web / Mobile / Third-party)            │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS
┌────────────────────────▼────────────────────────────────┐
│                     Reverse Proxy                       │
│                    (Nginx / Caddy)                      │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   Django Application                    │
│  ┌─────────────┐  ┌──────────┐  ┌────────────────────┐  │
│  │    Auth     │  │   OTP    │  │      Emails        │  │
│  │    Core     │  │   Logs   │  │   (+ Celery Tasks) │  │
│  │  Activity   │  │          │  │                    │  │
│  └─────────────┘  └──────────┘  └────────────────────┘  │
└───────────┬──────────────┬──────────────────────────────┘
            │              │
┌───────────▼──┐    ┌──────▼───────────────────────────┐
│  PostgreSQL  │    │           Redis                   │
│  (Primary    │    │  (Cache · OTP Storage ·           │
│   Database)  │    │   Celery Broker · Result Backend) │
└──────────────┘    └──────────────────────────────────┘
```

### Request Lifecycle

1. A request arrives and passes through Django middleware in order: Security → Session → Common → CORS → CSRF → Auth → Messages → XFrameOptions → **LoggingContextMiddleware** → **ActivityTrackingMiddleware**.
2. `LoggingContextMiddleware` injects request metadata (request ID, actor info, IP address, user agent) into Python `contextvars` for the duration of the request.
3. `ActivityTrackingMiddleware` reads `request.request_id` (set by the step above) and resolves the caller's session, ready to record a `UserActivity` row once the response is known.
4. The router dispatches to the appropriate view, which applies authentication, permissions, and throttling.
5. Business logic executes, potentially enqueuing Celery tasks (e.g., sending emails).
6. The view returns a standardized response object.
7. All significant events are written to `SystemLog` asynchronously via a non-blocking queue handler; a `UserActivity` row for the request is dispatched to Celery on the isolated `"activity"` queue. Both rows carry the same `request_id`, letting them be correlated later without any FK between the two systems.

---

## 4. Application Modules

| App | Responsibility |
|---|---|
| [`authentication`](../authentication/docs/README.md) | Custom user model, registration, login, logout, password management |
| [`core`](../core/docs/README.md) | Shared utilities, response helpers, health checks, Redis client |
| [`otp`](../otp/docs/README.md) | OTP generation, storage, verification, and per-purpose policies |
| [`emails`](../emails/docs/README.md) | Transactional email delivery, async tasks, email audit log |
| [`logs`](../logs/docs/README.md) | Structured logging, request context middleware, `SystemLog` model |
| [`activity`](../activity/docs/README.md) | Product analytics — `UserSession`/`UserActivity`, correlated with `logs` via a shared `request_id` |

Each app contains its own `docs/` folder with detailed documentation specific to that module.

---

## 5. Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose (recommended)

### Local Setup (Without Docker)

**1. Clone the repository and create a virtual environment:**

```bash
git clone <repository-url>
cd <project-directory>
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

**2. Install dependencies:**

```bash
pip install -r requirements.txt
```

**3. Configure environment variables:**

```bash
cp .env.example .env
# Edit .env with your local settings
```

**4. Run database migrations:**

```bash
python manage.py migrate
```

**5. Create a superuser:**

```bash
python manage.py createsuperuser
```

**6. Start the development server:**

```bash
python manage.py runserver
```

**7. Start Celery worker (in a separate terminal):**

```bash
celery -A my_django worker -l info
```

**8. Start Celery Beat scheduler (in a separate terminal):**

```bash
celery -A my_django beat -l info
```

### Local Setup (With Docker)

```bash
cp .env.example .env
# Edit .env with your settings

docker compose up --build
```

---

## 6. Environment Configuration

All configuration is managed via environment variables, loaded through `my_django/env_config.py`. A `.env.example` file is provided as a reference.

### Security

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Django secret key — must be long, random, and kept secret | *(required)* |
| `DEBUG` | Enable debug mode. Must be `False` in production | `False` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed host/domain names | `*` |

### CORS

| Variable | Description | Default |
|---|---|---|
| `CORS_ALLOW_CREDENTIALS` | Allow credentials in cross-origin requests | `True` |
| `CORS_ALLOW_ALL_ORIGINS` | Allow all origins (disable in production) | `False` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of allowed origins | — |
| `CORS_ALLOWED_ORIGIN_REGEXES` | Comma-separated list of origin regexes | — |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins for CSRF | — |

### Database

| Variable | Description | Default |
|---|---|---|
| `DB_ENGINE` | Database backend (`django.db.backends.postgresql` or `sqlite3`) | `postgresql` |
| `DB_NAME` | Database name | — |
| `DB_USER` | Database user | — |
| `DB_PASSWORD` | Database password | — |
| `DB_HOST` | Database host | — |
| `DB_PORT` | Database port | `5432` |

### Redis

| Variable | Description | Default |
|---|---|---|
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |

### Celery

| Variable | Description | Default |
|---|---|---|
| `CELERY_BROKER_URL` | Celery broker URL (Redis) | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result backend URL | `redis://redis:6379/0` |

### Email

| Variable | Description | Default |
|---|---|---|
| `EMAIL_HOST` | SMTP server hostname | `smtp.gmail.com` |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_HOST_USER` | SMTP login username / sender address | — |
| `EMAIL_HOST_PASSWORD` | SMTP password or app password | — |
| `EMAIL_USE_TLS` | Enable TLS | `True` |

### JWT

| Variable | Description | Default |
|---|---|---|
| `ACCESS_TOKEN_LIFETIME_MINUTES` | Access token TTL in minutes | `15` |
| `REFRESH_TOKEN_LIFETIME_HOURS` | Refresh token TTL in hours | `30` |

### OTP

| Variable | Description | Default |
|---|---|---|
| `OTP_LENGTH` | Number of digits in OTP | `6` |
| `OTP_EXPIRY_MINUTES` | OTP validity period in minutes | `5` |
| `OTP_ALLOW_NUMBER` | Allow numeric-only OTPs | `True` |
| `MAX_ACTIVE_OTPS` | Maximum concurrent OTPs per user per purpose | `5` |

### Throttling

| Variable | Description | Default |
|---|---|---|
| `LOGIN_THROTTLE_RATE_PER_MINUTE` | Login attempts per minute | — |
| `REGISTER_THROTTLE_RATE_PER_MINUTE` | Registration attempts per minute | — |
| `CHANGE_PASSWORD_THROTTLE_RATE_PER_MINUTE` | Password change attempts per minute | — |
| `GET_OTP_THROTTLE_RATE_PER_DAY` | OTP requests per day | `25` |

---

## 7. Running the Project

### Development

```bash
# API server
python manage.py runserver

# Celery worker
celery -A my_django worker -l info

# Celery Beat (periodic tasks)
celery -A my_django beat -l info
```

### Production

In production, use a process manager (Supervisor, systemd) or Docker Compose to run:

- **Gunicorn** — WSGI server for the Django application
- **Celery worker** — Background task processor
- **Celery Beat** — Periodic task scheduler
- **Nginx** — Reverse proxy and static file server

---

## 8. API Reference

All API responses follow a consistent envelope format:

**Success:**
```json
{
  "success": true,
  "message": "Human-readable description",
  "data": { ... }
}
```

**Error:**
```json
{
  "success": false,
  "message": "Human-readable error description",
  "data": null
}
```

### Endpoints Summary

| Method | Path | Description | Auth Required |
|---|---|---|---|
| `GET` | `/` | System health report | No |
| `POST` | `/v1/auth/register/` | Register a new user | No |
| `POST` | `/v1/auth/login/` | Login and receive JWT tokens | No |
| `POST` | `/v1/auth/logout/` | Logout and blacklist refresh token | Yes |
| `POST` | `/v1/auth/token/refresh/` | Obtain a new access token | No |
| `GET` | `/v1/auth/verify/` | Verify the current session | Yes |
| `POST` | `/v1/auth/password/change/` | Change authenticated user's password | Yes |
| `POST` | `/v1/otp/get-otp/` | Request a one-time password | Conditional |

For detailed request/response schemas, refer to the individual app documentation.

---

## 9. Authentication & Authorization

The API uses **JWT Bearer token authentication**.

### Obtaining Tokens

Tokens are issued on successful login at `POST /auth/login/`. The response includes:

```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access": "<access_token>",
    "refresh": "<refresh_token>",
    "user": { ... }
  }
}
```

### Using Tokens

Include the access token in the `Authorization` header for all protected endpoints:

```
Authorization: Bearer <access_token>
```

### Token Rotation

- Access tokens expire after **15 minutes** (configurable).
- Refresh tokens expire after **30 hours** (configurable).
- Upon refreshing, the old refresh token is **blacklisted** and a new pair is issued (`ROTATE_REFRESH_TOKENS = True`).

### Throttling

Sensitive endpoints are rate-limited to prevent abuse. Throttle limits are configurable via environment variables. Exceeding a limit returns HTTP `429 Too Many Requests`.

---

### Role & Permission Authorization System

The project implements a production-ready, additive role- and permission-based authorization architecture.

#### 1. Models & Relationships
- **`Role`** — Represents a system or custom role. Contains:
  - `code`: Unique, uppercase programmatic code (e.g., `SUPER_ADMIN`, `ADMIN`, `PROJECT_MANAGER`, `DEVELOPER`, `USER`).
  - `name`: Human-readable display name.
  - `description`: Optional text.
  - `is_system`: Boolean flag protecting core roles from deletion or code modification.
  - `permissions`: Many-to-many relationship with `django.contrib.auth.models.Permission`.
  - `groups`: Many-to-many relationship with `django.contrib.auth.models.Group`.
- **`UserRole`** — Explicit intermediary through-model linking `User` and `Role` with audit timestamps and soft-delete support (`unique_user_role` constraint).
- **`User.roles`** — Many-to-many relationship connecting users to roles via `UserRole`.

#### 2. Effective Permission Calculation (4 Additive Tiers)
Effective permissions are evaluated additively without explicit deny rules:
1. **Tier 1:** Direct user permissions (`User.user_permissions`)
2. **Tier 2:** Permissions from groups assigned directly to the user (`User.groups.permissions`)
3. **Tier 3:** Permissions assigned directly to the user's active roles (`Role.permissions`)
4. **Tier 4:** Permissions inherited from groups assigned to the user's active roles (`Role.groups.permissions`)
*Superusers automatically have all permissions.*
*Unauthenticated or inactive users always fail with `False`.*

Django's native backend integration is provided via `RolePermissionBackend` in `AUTHENTICATION_BACKENDS`, ensuring standard calls like `request.user.has_perm('app.action')` and `request.user.get_all_permissions()` include all role and role-group permissions.

#### 3. Single Source of Truth (`authentication/system_roles.py`)
All canonical system roles, descriptions, and default permissions are defined in code in [`authentication/system_roles.py`](../authentication/system_roles.py).

To synchronize roles with the database:
```bash
# Preview changes without modifying database
python manage.py sync_roles --dry-run

# Apply additions and updates
python manage.py sync_roles

# Safely prune obsolete roles (roles with active user assignments are soft-deleted to protect users)
python manage.py sync_roles --prune

# Generate a data migration for automated CI/CD deployment
python manage.py sync_roles --create-migration add_new_roles
```

#### 4. View Integration (`@authorize` Decorator)
The `@authorize` decorator supports function-based views, class-based view methods, and async view functions with `AND` / `OR` composition:

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

# Role AND Permission check (default operator is AND)
@authorize(
    strict="PROJECT_MANAGER",
    permission="projects.change_project",
    operator="AND",
)
def update_project(request, project_id):
    ...

# Role OR Permission check
@authorize(
    strict="PROJECT_MANAGER",
    permission="projects.change_project",
    operator="OR",
)
def alternative_update_project(request, project_id):
    ...
```

#### 5. DRF Permission Classes
For standard class-based `APIView` and `ViewSet` classes:

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

#### 6. Object-Level Authorization
Use `check_object_permission(user, permission, obj)` or provide `object_getter` to `@authorize` for record-level authorization.

#### 7. Automatic Cache Invalidation
Whenever a user's permissions, groups, roles, or role permissions change, Django signal handlers in `authentication/signals.py` automatically clear all in-memory permission and role caches.


## 10. Background Tasks

Celery handles all asynchronous work. The broker and result backend are both Redis.

### Registered Tasks

| Task | Module | Trigger |
|---|---|---|
| `send_email_task` | `emails.tasks` | Called when an email needs to be sent |
| `beat_heartbeat` | `core.tasks` | Periodic — every 1 minute |

### Periodic Schedule

| Schedule Name | Task | Interval |
|---|---|---|
| `beat-heartbeat` | `core.tasks.beat_heartbeat` | Every 60 seconds |

All tasks are serialized as JSON and run in UTC timezone.

---

## 11. Logging & Observability

### Structured Logging

The system uses a multi-layer logging strategy:

- **File logs** — Rotated daily, retained for 30 days. Separate files for application logs and error logs.
- **Database logs** — `SystemLog` model stores logs with full request context, actor identity, and structured metadata.
- **JSON output** — A `JSONFormatter` produces machine-readable output compatible with Datadog, ELK Stack, and Splunk.
- **Console output** — Enabled in `DEBUG` mode for local development.

### Request Context

Every log entry produced during a request automatically includes:
- `request_id` — From the `X-Request-ID` header (or auto-generated)
- `actor_id`, `actor_email` — The authenticated user, if any
- `ip_address`, `user_agent` — Client metadata
- `business_id` — From the `X-Business-ID` header, for multi-tenant scenarios

### Correlation with Activity Tracking

`SystemLog.request_id` and `activity.UserActivity.request_id` (see [`activity`](../activity/docs/README.md)) carry the same UUID for the same HTTP request — a soft correlation key, never a foreign key. The two systems write independently and asynchronously (logs via a background queue thread, activity via Celery); they're joined only at query time:

```sql
SELECT sl.event_name, sl.log_level, ua.service, ua.duration_ms
FROM logs_systemlog sl
JOIN activity_user_activity ua ON ua.request_id = sl.request_id
WHERE sl.request_id = '<uuid>';
```

### Health Check

`GET /` returns a real-time health report:

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

---

## 12. Deployment

### Docker

The project ships with a multi-stage `Dockerfile` (`docker/Dockerfile`) optimized for production:

- **Builder stage** — Installs build dependencies and compiles Python packages into a virtual environment.
- **Runtime stage** — Copies only the virtual environment and application code, keeping the image lean.

An `entrypoint.sh` script handles startup logic (migrations, static files collection, server launch).

### Recommended Infrastructure

| Component | Recommendation |
|---|---|
| Web Server | Gunicorn with 2–4 workers (adjust to CPU cores) |
| Reverse Proxy | Nginx or Caddy |
| Database | PostgreSQL with connection pooling (PgBouncer) |
| Cache / Broker | Redis (consider Redis Sentinel or Cluster for HA) |
| Task Workers | Celery with auto-scaling concurrency |
| Process Manager | Docker Compose / Kubernetes / Supervisor |
| Log Aggregation | Datadog, ELK Stack, or Grafana Loki |
| Secrets | Environment variables via a secrets manager (AWS Secrets Manager, Vault) |

### Pre-deployment Checklist

- [ ] `DEBUG=False`
- [ ] `SECRET_KEY` is long, random, and stored securely
- [ ] `ALLOWED_HOSTS` is explicitly set to your domain(s)
- [ ] `CORS_ALLOW_ALL_ORIGINS=False` with explicit `CORS_ALLOWED_ORIGINS`
- [ ] Database uses a dedicated user with minimum required permissions
- [ ] `python manage.py migrate` has been run
- [ ] `python manage.py collectstatic` has been run
- [ ] Email credentials are valid and tested
- [ ] Redis is accessible from the application
- [ ] Celery worker and Beat are running

---

## 13. Project Structure

```
.
├── my_django/                  # Django project configuration package
│   ├── settings.py             # Main settings file
│   ├── urls.py                 # Root URL configuration
│   ├── wsgi.py                 # WSGI entry point
│   ├── asgi.py                 # ASGI entry point
│   ├── celery.py               # Celery application setup
│   ├── env_config.py           # Typed environment variable loader
│   └── configs/
│       └── celery_schedules.py # Celery Beat periodic task definitions
│
├── authentication/             # User authentication module
├── core/                       # Shared utilities and health monitoring
├── emails/                     # Email delivery service
├── otp/                        # One-time password service
├── logs/                       # Structured logging and audit trail
├── activity/                   # Product analytics — sessions & per-request tracking
│
├── docs/                       # Project-level documentation (this folder)
├── docker/                     # Docker build files
│   ├── Dockerfile              # Multi-stage production Dockerfile
│   └── entrypoint.sh           # Container startup script
│
├── requirements.txt            # Python package dependencies
├── .env.example                # Environment variable reference file
├── manage.py                   # Django management utility
└── .gitignore                  # Git exclusion rules
```
