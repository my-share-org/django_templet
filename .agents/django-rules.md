# Django Backend AGENTS.md — Local Rules

> Works together with the global AGENTS.md. Place this file in the root of any Django project. It defines the rules an AI agent follows when building or modifying that project — app organization, versioning, security, rate limiting, error handling, and the domain patterns that recur across most real backends. **This is a rulebook, not a description of one running app.** `apps/authentication/` and `apps/payments/` below are worked examples showing the required file-level shape, not a fixed list of apps every project must have. Replace `<project_name>/` with your actual project config folder name when this file is dropped into a new repo.

## Reference Project Structure

Two apps are expanded in full purely to make the file-level shape unambiguous: `apps/authentication/`, because nearly every backend needs one, and `apps/payments/`, as a worked example of a webhook-driven domain. Neither is mandatory — build whatever domains your project actually needs, in this same shape.

```
├── apps/                          # Every Django app lives here, not at the repository root
│   ├── __init__.py
│   ├── authentication/            # Custom user model, JWT auth, password flows, admin user management
│   │   ├── docs/                    # Module reference
│   │   ├── managers/
│   │   │   ├── __init__.py
│   │   │   └── user.py                # UserManager — named after the model it manages, not managers.py
│   │   ├── migrations/
│   │   │   ├── __init__.py
│   │   │   └── 0001_initial.py, 0002_..., ...   # one file per schema change, in order
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── admin.py                 # admin-triggered business logic (NOT the same as root admin.py — see §1)
│   │   │   ├── password.py
│   │   │   └── permissions.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── urls.py
│   │   │   └── views.py
│   │   ├── __init__.py
│   │   ├── admin.py                    # Django admin site registration (ModelAdmin classes)
│   │   ├── apps.py                       # AppConfig — also where signals.py gets registered, in ready()
│   │   ├── models.py
│   │   ├── signals.py                     # post_save/pre_delete hooks — used sparingly, see §1
│   │   ├── tests.py                        # or a tests/ package once it outgrows one file
│   │   └── throttles.py
│   ├── payments/                    # Example: a payment-provider webhook domain (see §10A for the pattern)
│   │   ├── docs/
│   │   ├── migrations/
│   │   ├── services/                    # e.g. checkout.py, webhook.py
│   │   ├── v1/                           # serializers.py, urls.py, views.py
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   └── tests.py                        # no signals.py or throttles.py here — only add files a domain actually needs
│   ├── <domain>/, <domain>/, ...       # every other app YOUR project needs — otp, emails, notifications,
│   │                                      # a billing/ledger domain, an external-dispatch domain, a read-only
│   │                                      # reporting domain, dev-only debug routes — whatever applies (see §10)
│   │   # Every domain app follows the identical shape shown above:
│   │   # docs/, migrations/, services/ (split by concern), v1/ (__init__.py, serializers.py, urls.py, views.py),
│   │   # plus root __init__.py, admin.py, apps.py, models.py, tests.py — with signals.py / throttles.py / tasks.py
│   │   # added only where that specific domain needs them.
│   └── core/                          # Shared foundation, no domain logic
│       ├── health/                      # Per-service health checks (database, email, celery, etc.)
│       ├── services/                     # health_check aggregator
│       ├── middleware/                    # admin_throttle
│       ├── cache/                          # redis_client
│       ├── utils/                           # response, exception_handler, pagination, permissions,
│       │                                      # filtering, validators, generators, decorators, query, image
│       ├── templates/                        # health_report.html
│       ├── models.py                          # BaseModel (abstract, soft delete)
│       └── docs/
├── <project_name>/                 # Django project config
│   ├── configs/                      # celery_schedules.py
│   ├── settings.py
│   ├── env_config.py
│   ├── urls.py                       # Root: health dashboard, admin, /v1/
│   ├── urls_v1.py                     # v1 route table
│   └── celery.py
├── bruno-collection/                # Bruno API collection (Admin / User / Public, then app name) — if used
│   ├── environments/                  # local_env.bru (gitignored), production_env.bru
│   ├── bruno.json
│   └── collection.bru
├── developer_guide/                 # Response, Services, Utilities reference docs
├── docs/                             # Full project documentation
├── developers_files/                 # Test results, evaluations, security audits
├── project_script/                   # cross-platform CLI automation toolkit, if you have one
├── docker/                           # Dockerfile, entrypoint.sh, CI env
├── .github/workflows/                # CI and CD pipelines
├── local-db.docker-compose.yml
├── local-api.docker-compose.yml
├── production-db.docker-compose.yml
├── production-api.docker-compose.yml
└── requirements.txt
```

---

## 1. App Organization

- One app per business domain, and every domain app lives under `apps/` — not the repository root. `AppConfig.name` is the full Python path (`apps.authentication`). The app label stays the short name (`authentication`), so `AUTH_USER_MODEL`, foreign keys, and migration dependencies keep using that label.
- Inside each app, keep the same internal shape: `models.py`, `services/` (split into focused files, not one giant `services.py`), a `migrations/` folder, a version folder (`v1/`, later `v2/`), and a `docs/` folder for that app's own reference notes.
- `services/` is a folder, not a single file, once an app has more than one clear concern — e.g. `apps/authentication/services/` splits into `admin.py`, `password.py`, `permissions.py` instead of one 400-line file.
- **Two files can both be named `admin.py` in the same app — they are not the same thing.** The root-level `admin.py` is Django's admin *site* registration (`ModelAdmin` classes, list displays, filters — what staff see in `/admin/`). `services/admin.py` is business logic triggered *by* an admin action (e.g. suspending a user). Never put business logic in the root `admin.py`, and never put `ModelAdmin` registration in `services/`.
- `managers/` holds custom Django model managers. Name the file after the model it manages (`managers/user.py` for `UserManager` on the `User` model), not a generic `managers.py`.
- `migrations/` is standard Django — one file per schema change, applied in order. Every schema change goes through a migration; the generated file gets read before it's applied (see §3).
- `apps.py` defines the app's `AppConfig`. If an app uses `signals.py`, the signal handlers get connected inside `AppConfig.ready()` — never at import time in a random module, which causes signals to register more than once or not at all depending on import order.
- `signals.py` is for reacting to a model event (`post_save`, `pre_delete`) from *outside* the code that triggered it — genuinely decoupled cases only. If the reacting code could just as easily be a direct function call from the service that triggers the event, prefer the direct call. Signals hide control flow — a developer reading `services/checkout.py` has no way to know a signal elsewhere also runs on save unless they go looking for it. Use them sparingly, not as the default way to chain behavior.
- `tests.py` is fine for a small app. Convert it to a `tests/` package (`__init__.py` + one file per concern) once a single file gets hard to navigate — there's no fixed threshold, just "can a new developer find the relevant test in under 10 seconds."
- `throttles.py` at the app level holds custom DRF throttle classes specific to that app (e.g. a stricter login-attempt throttle) — only apps that actually need a custom scope have this file; don't add it by default.
- `docs/` per app is a short module reference for that domain specifically — distinct from `developer_guide/` (shared conventions) and `docs/` at project root (full project documentation).

## 2. API Versioning — Per-App `v1/` Folders

- Each app owns its own version folder — containing that version's `urls.py`, `views.py`, and `serializers.py`.
- `models.py` and `services/` live **outside** the version folder, at the app root. They're shared across versions — a future `v2/` endpoint should reuse the same service function as `v1/` unless the underlying business logic itself changed.
- `<project_name>/urls_v1.py` is only an aggregator: it includes each app's `v1/urls.py` under the right prefix. It never defines a route directly.
- The root `urls.py` includes the health dashboard, Django admin, and `urls_v1.py` — nothing else.
- **Versioning is per-app, not global.** When one app needs a breaking change, add `app_name/v2/` next to its `v1/` and register it through a new `urls_v2.py`. Apps that haven't changed stay on `v1/` — you never have to bump every app at once just because one changed.
- Never delete a `v1/` folder while any client still depends on it. Deprecate first (note it in `docs/`, log its usage), then remove once usage hits zero.

## 3. Models

- Every model inherits from `apps.core.models.BaseModel` (abstract, soft delete) — consistent `created_at`, `updated_at`, and a soft-delete flag across the whole codebase.
- Default querysets should exclude soft-deleted rows unless a query explicitly asks for deleted records.
- Keep models focused on data shape. Business logic belongs in `services/`, not model methods.
- Index every foreign key and any column used often in filters or ordering.
- Every schema change goes through a migration, and the generated migration file gets read before it's applied.

## 4. Serializers (DRF)

- One serializer per use case, scoped to its version folder — never one shared serializer reused for both input and output.
- Validate at the serializer level: field-level `validate_<field>()` for single-field rules, object-level `validate()` for rules spanning multiple fields.
- Never include sensitive fields (password hashes, internal-only flags, raw webhook payloads) in a response serializer.

## 5. Views / ViewSets

- Keep views thin: receive the request, call a service function, return the result through `apps/core/utils/response`. No business logic directly inside a view.
- Use DRF permission classes for access checks instead of manual `if` checks scattered through views.
- Use `ViewSet` + `Router` for standard CRUD. Use plain `APIView` for custom, non-CRUD actions (e.g. a verification endpoint, a webhook receiver, a callback receiver).

## 6. Rate Limiting & Throttling

- DRF ships throttle classes (`AnonRateThrottle`, `UserRateThrottle`, `ScopedRateThrottle`) configured centrally in `<project_name>/settings.py` via `DEFAULT_THROTTLE_CLASSES` and `DEFAULT_THROTTLE_RATES` — this is the baseline for **every** endpoint in **every** app, including ones that don't exist yet. An app's own `throttles.py` only overrides that baseline for one specific, higher-risk endpoint — it's the exception, not the mechanism itself.
- **DRF's throttle counters use Django's cache framework to track requests. In production that cache must be Redis (`apps/core/cache/redis_client`), never the default local-memory cache.** Local-memory cache is per-process — with more than one Gunicorn/Uvicorn worker or more than one server instance, each process counts independently, and the real effective limit silently becomes (configured rate × number of processes). This is the most common reason rate limiting "works in testing" and does nothing in production.
- Layer limits at two levels: per-IP (`AnonRateThrottle`, protects endpoints before a user is even authenticated — login, signup, verification-code requests) and per-user (`UserRateThrottle`/`ScopedRateThrottle`, fair use once authenticated). Per-IP alone is bypassed by rotating IPs; per-user alone doesn't protect endpoints that don't require auth yet.
- Give tighter, purpose-specific scopes to abuse-prone endpoints: login, verification codes, password reset, signup — and any webhook or callback endpoint (see §10A/§10C). Those skip normal *auth*, but they still need a throttle scope; a flood of fake calls is still a resource-exhaustion risk even if each one fails verification.
- Admin routes (`apps/core/middleware/admin_throttle`) get their own scope, separate from the public API's limit. Admin traffic is low-volume but high-privilege — sharing the public scope means a public traffic spike can starve legitimate admin usage, or abuse of an admin token hides inside normal user-level limits.
- On a throttled request, DRF returns `429` with a `Retry-After` header automatically — never intercept this and replace it with a "friendly" 200; the client needs the real status code to back off correctly.
- Default rule for any new endpoint: the global `DEFAULT_THROTTLE_RATES` applies automatically. Only touch `throttles.py` when this specific endpoint's risk profile genuinely differs from that baseline.

## 7. Database & Query Practices

- Avoid N+1 queries anywhere a queryset is looped over to reach a related object — `select_related` for foreign keys/one-to-one, `prefetch_related` for many-to-many/reverse foreign keys.
- Every list endpoint is paginated — never return an unbounded queryset. Use the shared `apps/core/utils/pagination.py` class, not a one-off per view.
- Wrap any multi-step write in `transaction.atomic()` so a partial failure can't leave the database inconsistent. This is mandatory, not optional, for any ledger domain (§10B) or external-dispatch domain (§10C), where a request touches more than one table that must succeed or fail together.
- Use `select_for_update()` inside a transaction for any read-then-write on a row that can be hit concurrently — a balance is the clearest case, but any "check a value, then update it" pattern needs the same protection.
- Connection pooling (`CONN_MAX_AGE` in `settings.py`, or a pooler like `pgbouncer` in front of Postgres) is a production requirement, not an optimization — opening a fresh DB connection per request doesn't scale past a handful of concurrent users.

## 8. Error Handling

- Every error response — validation failure, permission denial, not-found, unhandled exception — goes through `apps/core/utils/exception_handler.py` and comes out in one consistent shape: `{ "error": { "code": "...", "message": "..." } }`. A view or service never constructs its own ad-hoc error JSON.
- Map exception types to HTTP status codes the same way across the whole API: validation → 400/422, missing auth → 401, permission denied → 403, not found → 404, conflict → 409, unhandled → 500. A new app reuses this mapping — it doesn't invent its own convention.
- Never let a raw exception message, stack trace, or database error reach the client. Log the full detail internally; return only the generic, mapped message externally.
- Log every 401, 403, and 429 specifically, not just 500s — a cluster of permission-denied or throttled requests is often the first visible sign of an attack in progress.
- The `code` field (not just `message`) is what the frontend maps to a friendly, localized string. An error response missing a stable `code` breaks that contract silently.

## 9. Authentication, OTP, Emails, Notifications

These four are close to universal — almost every real backend needs some form of each.

- The auth app owns the `User` model, JWT issuing/verification, password flows, and admin user management. No other app duplicates auth logic.
- JWT rules: access token short-lived (5–15 min), refresh token rotated on every use, both verified server-side on every request. Always confirm the requesting user owns the resource being accessed — never rely on "logged in" alone.
- If the project uses one-time verification codes (signup, 2FA, password reset), define **per-purpose** rules — a signup code and a password-reset code can have different expiry times and retry limits; don't force one rule set onto every purpose.
- Rate-limit verification-code generation and checking per user/phone/email, with a cooldown or lockout after repeated failures — this is one of the most commonly abused flows in any backend.
- Send all email through background tasks (Celery), never synchronously in the request cycle. Email content lives in templates, never hardcoded strings inside a service function.
- Log every email attempt (success or failure) for delivery debugging.
- In-app notifications stay decoupled from the apps that trigger them — a triggering app calls a notification service function, it doesn't build the notification itself.

## 10. Common Domain Patterns (Worked Examples, Not Mandatory Apps)

Real backends keep running into the same handful of domain *shapes*, whatever the app is actually called or whatever business it serves. The patterns below are the safe default for each shape — apply whichever one matches something your project actually has. Don't create an app just because it's listed here.

**A. Payment / billing domains (Stripe or similar)**
- All payment-provider interaction lives in that domain's `services/` — never call the provider's SDK directly from a view.
- **Webhook signature verification is mandatory on every webhook request**, no exceptions. Verify the provider's signature with the signing secret before trusting any part of the payload.
- A webhook endpoint skips normal user/admin auth (the provider can't send a Bearer token) — it must never skip signature verification. "No user auth" and "no security" are not the same thing.
- Payment providers resend events. Handle every webhook idempotently — check the provider's event ID against what's already been processed before applying it again.
- Never trust a client-supplied payment amount. Compute the amount to charge on the server from the actual stored price.
- Never store raw card data — use the provider's hosted checkout/Elements so card numbers never touch your server.
- Log every payment state transition for audit and dispute handling.

**B. Ledger-backed domains (credits, wallets, points — any internal balance)**
- Treat it as a **ledger, not a balance column**. Every change — purchase, spend, refund, admin adjustment — is an append-only entry. The balance is derived from the ledger or a cached value reconciled against it.
- Wrap balance-changing operations in a transaction with `select_for_update()` to prevent race conditions.
- A refund is a new ledger entry, never a retroactive edit to an old one.
- Seed/reference data (packages, tiers, prices) lives in fixtures or a management command, kept out of migrations.

**C. External dispatch & callback domains (queued work sent out, with a result received back later)**
- Treat the callback endpoint with the same suspicion as any public-facing endpoint — the caller is external, even if it's "your own" automation.
- The callback must be authenticated with a per-dispatch token, generated at dispatch time and verified on the way back in. Hitting the right URL is not proof of legitimacy.
- Callbacks must be idempotent — a retried callback must not double-refund, double-charge, or double-dispatch.
- Failed or timed-out dispatches follow a defined retry policy with a maximum attempt count.
- A dispatch that ultimately fails after retries triggers a compensating action (typically a refund through the ledger, pattern B) — it never silently drops what the user paid for.

**D. Read-only aggregation / dashboard domains**
- These endpoints never modify data.
- Cache expensive aggregation results (via the shared Redis client) with a TTL matched to how fresh the data actually needs to be.
- Watch for N+1 queries specifically here — aggregation code often loops over related objects to build a chart, exactly where N+1 problems hide.
- Require admin-level permission — never expose aggregate business metrics to a regular user token.

**E. Third-party usage / metering domains (any external API you sync spend or usage from)**
- The provider's API key comes from environment variables only, never hardcoded.
- The sync task is idempotent — re-running it for an already-synced period must not double-count usage.
- A manual backfill command shares the same underlying sync function as the scheduled task — never a separate parallel implementation that can drift out of sync.
- Handle the provider's own rate limits gracefully — back off and retry, don't let a rate-limited sync crash the task.

**F. Dev-only / debug routes**
- Routed only when the environment is explicitly non-production, enforced with a conditional include in the URL config — never rely on "we'll remove it before deploying."
- Run a pre-deploy check (`python manage.py check --deploy`) that fails loudly if debug mode or debug routes would be reachable in a production-configured build.
- Anything here that touches a real external service is sensitive even though it's dev-only — it still runs against real credentials.
- This is one of the most common real-world security leaks: a debug route that quietly ships to production. The code-level environment guard is the actual protection — "it's dev-only by convention" is not.

## 11. Logs — Structured Logging

- Use a non-blocking log handler (`QueueHandler`) — log writes go to a queue processed by a separate listener, so a slow log write never blocks the request-response cycle.
- Separate normal application logs from error-level logs, so error monitoring can watch one stream without noise from routine request logs.
- Attach request context (request ID, user, path) to every log line automatically via middleware — new code should never bypass this by logging directly with the bare `logging` module without context.
- Any API that exposes raw logs is admin-only — logs can reveal user behavior and internal system details.

## 12. Core Utilities & Shared Foundation

- `apps/core/utils/response.py` — every API response, success or error, goes through this one formatter.
- `apps/core/utils/exception_handler.py` — one central DRF exception handler catches unhandled errors, formats them, and logs them (see §8 for the policy this implements).
- `apps/core/utils/pagination.py` — one shared pagination class used by every list endpoint.
- `apps/core/utils/permissions.py` and `filtering.py` — shared permission classes and queryset filtering helpers. Check here before writing a one-off version inside an app.
- `apps/core/utils/validators.py`, `generators.py`, `decorators.py`, `query.py`, `image.py` — shared helpers, checked before writing something new.
- `apps/core/middleware/admin_throttle` — a separate throttle scope for admin routes (see §6).
- `apps/core/cache/redis_client` — the single shared Redis client for caching and rate-limit state. Don't create a second one elsewhere.
- `apps/core/health/` holds one health-check function per dependency (database, email, celery, etc.). `apps/core/services/` aggregates them, exposed both as a JSON endpoint and a human-readable dashboard template.

## 13. Background Jobs (Celery)

- `<project_name>/celery.py` is the single Celery app entry point. `<project_name>/configs/celery_schedules.py` holds all periodic (beat) schedules in one place — don't scatter schedule definitions across app files.
- Task functions live inside the app that owns them, never in an unrelated app.
- Every task is idempotent — safe to run twice if retried.
- Tasks calling external services need explicit timeout and retry settings — a hung external call with no timeout can occupy a worker slot indefinitely.

## 14. Docker & Environments

- `env_config.py` is the single place environment variables are read and validated. `settings.py` then builds Django settings from those already-validated values, instead of calling `os.environ.get()` scattered throughout `settings.py`.
- Keep `db`/`api` compose files separate, and `local`/`production` compose files separate. Never point local development at the production compose file.
- CI must run lint and tests on every pull request before merge is allowed.
- Keep the CI environment's Docker setup as close to production's as possible, so "it works in CI" actually predicts "it works in production."

## 15. Bruno API Collection Rules (if the project uses Bruno)

The Bruno collection lives in `bruno-collection/`. Its folder tree mirrors the project's app structure, so any request maps back to the Django app that owns it.

**Folder layout**
1. Level 1 — audience: `Admin/`, `User/`, or `Public/`. Pick by who calls the endpoint, not by who wrote it.
2. Level 2 — the Django app that owns the route. Use the app's folder name, or a short established abbreviation (e.g. `authentication` → `auth`). Reuse whatever your project already established for a folder — never create a duplicate.
3. Level 3 — optional, only to group a large app's related routes.
4. Every folder needs a `folder.bru` with a `meta { name: ... }` block.

**Request files**
- One `.bru` file per endpoint, named after the view action in kebab-case.
- Source of truth is `<app>/v1/urls.py`, its views, and its serializers. Read them first. Never invent an endpoint, field, or status code.
- URLs always use `{{BASE_URL}}/v1/...`. Never hardcode a host.

**Auth**
- `Public/` requests: `auth: none`.
- `User/` requests: `auth: inherit` (collection default sends `{{USER_ACCESS_TOKEN}}`).
- `Admin/` requests: explicit `auth:bearer { token: {{ADMIN_ACCESS_TOKEN}} }` on the request itself. `inherit` sends the user token and will 403.
- Tokens are saved with `bru.setVar()` only. Never `bru.setEnvVar()` — it writes live JWTs into the tracked `environments/*.bru` files.
- Never put a real secret in a `.bru` file. Declare the name under `vars:secret`.

**Docs block**
Every request needs a `docs { }` block with: title, Method, Auth, Permission (if any), Body or Query params with types and limits, Response shape, Errors by status code, and a Note for any non-obvious behaviour.

**After changes**
Update the folder tree and variables table in `bruno-collection/README.md` whenever a folder or environment variable is added or renamed.

## 16. Developer Guide & Project Docs

- `developer_guide/` — shared response/service/utility conventions. The source of truth for how a new feature should be built.
- `docs/` — full project documentation (architecture, setup, onboarding).
- `developers_files/` — test results, evaluations, and security audit records, if you keep them.
- A cross-platform CLI toolkit, if the project has one — a new repetitive manual step should become a CLI command, not a README instruction that gets forgotten.

## 17. Testing

- Each app tests itself — a single `tests.py` while it's small, or a `tests/` package once it outgrows one file.
- Confirm the shared response format is used correctly in each new endpoint's tests.
- Explicitly test authorization boundaries — attempt to access or modify another user's resource and confirm rejection.
- Explicitly test rate-limit enforcement (request past the limit, confirm a real 429), and, for any domain following the ledger (§10B) or external-callback (§10C) patterns, webhook/callback idempotency and balance correctness under concurrent requests — these are the places where a missed edge case becomes a real financial or security bug.

## 18. Security (Django-Specific)

- `DEBUG = False` in production, with `ALLOWED_HOSTS` explicitly set.
- Keep `SECRET_KEY`, any third-party API keys, and DB credentials out of code — always pulled from environment variables.
- Run `python manage.py check --deploy` before every deploy.
- Verify webhook/callback signatures on every external request (§10A/§10C) — treat any endpoint that skips normal auth as needing a *different* form of verification, never *no* verification.
- Confirm dev-only routes (§10F) are unreachable outside a debug/dev environment before every release.
- Give admin routes their own throttle scope instead of sharing the public rate limit.

## 19. Implementation Discipline — Precautions Before Writing Code

Before generating or modifying any endpoint, model, or service in this project, work through this checklist. It exists so the rules in §1–§18 actually get applied while code is being written, not discovered missing afterward in review.

**Modularity & coupling**
- Does this change belong in `services/`, not directly in a view? If the same logic is needed in two places, is it one function called twice, not copy-pasted?
- Does this new code reach into another app's internals (importing another app's models directly instead of calling its service function)? That's tight coupling — go through the owning app's `services/` layer instead.
- Is a new shared helper being written that already exists in `apps/core/utils/`? Check there first (§12) before adding a duplicate.

**Security**
- Does this endpoint touch another user's data? If yes, is there an explicit object-level ownership check, not just an authentication check (§1, §9)?
- Does this endpoint accept external input (body, query params, headers, webhook payload)? Is every field validated, not just the ones that "look important"?
- Is anything here a secret (API key, signing secret, DB credential)? It comes from environment variables — never a literal string in the code, even temporarily "to test."
- Is this a webhook or callback endpoint? Signature/token verification (§10A/§10C) must be in place before the handler trusts any part of the payload — not added as a follow-up task.

**Throttling & rate limits**
- Does this endpoint fall outside the global default throttle rate — login, verification codes, password reset, signup, or any webhook/callback? If so, apply the tighter scope from §6 explicitly instead of leaving it on the default.
- If throttling is being configured for the first time on a fresh setup, is the cache backend actually Redis, not local-memory? (§6 — this is the single most common silent failure.)

**Database & scalability**
- Does this code loop over a queryset and touch a related object inside the loop? That's N+1 — use `select_related`/`prefetch_related` (§7) before it ships, not after a slow-query report.
- Does this write touch more than one table, or read-then-write a value that can be hit concurrently (a balance, a count, a status flag)? Wrap it in a transaction, and add `select_for_update()` if concurrency is possible (§7).
- Is this a new list endpoint? Paginate it before it ships — don't plan to add pagination later.

**Error handling & reliability**
- Does every failure path return through the shared response/exception formatter (§8), or does this code build its own error JSON?
- If this operation can be retried (a webhook, a background job, a callback), is it actually idempotent, or will a retry double-apply it (§10B/§10C)?

**When something doesn't fit cleanly**
If a change doesn't obviously map to one of these checks — a genuinely new kind of endpoint, an ambiguous ownership case, a performance tradeoff with no clear right answer — say so explicitly instead of silently picking an approach. Flag the tradeoff and the reasoning, same as the global AGENTS.md's agent-behavior rules already require.

---

*Status: v4 — added §19, a pre-implementation checklist tying security, modularity/coupling, throttling, database, and error-handling rules together at the moment code is actually written.*
