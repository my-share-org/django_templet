# Repository audit — Django project template

**Date:** 3 November 2026  
**Scope:** Application code, settings, tests, Bruno collection, Docker, and the CI/CD files in this repository.  
**Method:** Static review of the source. The documented pytest suite was not executed. `pytest` is not listed in `requirements.txt`, and it is not installed in the project virtualenv.

This is a judgment of the tree as it exists today, measured against the claim that it is a production-grade base for new Django projects.

## Verdict

Use this as a **local starter for an API with email OTP and JWT**, after you fix the items in the critical list. Do not treat it as a production base, and do not copy the Docker or CI setup onto a server without rewriting both.

The application layout is ahead of the operational setup. Authentication, OTP policy, throttles, and the role model show real design work. The runtime that is supposed to run that code does not match the code: the production process is not installed, the worker does not listen to the queue the code publishes to, GitHub will not see the workflow files, and the test command in CI does not run the suite the README describes.

Calling the current tree production-grade is not accurate.

**Overall: 5 / 10.** A capable personal starter with several defects that will show up on the first real deploy.

## Scorecard

| Criterion | Score | Judgment |
|---|---|---|
| Security | 5 / 10 | OTP hashing, scoped throttles, and JWT rotation are real. Account enumeration, spoofable client IP, exception text in API responses, and unsafe production defaults are also real. |
| Feature correctness | 5.5 / 10 | Register, login, and password reset can work. Session tracking does not do what the name says. Activity writes will not land. One enabled OTP purpose cannot be emailed. |
| Reliability | 4.5 / 10 | Silent `except: pass` on token revocation, no wait for Postgres, and a Celery queue nobody consumes. |
| Reusability | 6 / 10 | Apps are separable. The project name, container prefix, timezone, and a leftover `business` profile are baked in. |
| Modular coding | 7 / 10 | Strongest area. Services, `v1` routers, and the OTP policy table are the right shape. Settings are still one file, and OTP email has two implementations. |
| Documentation and comments | 5 / 10 | There is a lot of documentation. Some of it describes endpoints and files that do not exist, and some docstrings are placeholders. |
| Testing | 5 / 10 | The pytest layout is serious. It is not installable from the declared dependencies, CI does not run it, and a few tests pass without proving the behavior they describe. |
| Docker | 5 / 10 | Multi-stage image, non-root user, and a split database compose file are sound. The production command will fail, and the worker command ignores the queues defined in settings. |
| CI/CD | 2.5 / 10 | The workflows are in the wrong directory, the env file they copy does not exist, and the deploy script can destroy the running image before the new one is known to work. |
| Production-grade | 4 / 10 | Not yet. The gaps are operational, not cosmetic. |
| Best practices | 5.5 / 10 | Many local patterns are right. The shipping configuration contradicts several of them. |

## What is actually solid

These parts are worth keeping when a new project is cut from this repo.

- App boundaries are real: `authentication`, `otp`, `emails`, `notifications`, `activity`, `logs`, `core`. Business rules sit in services more often than in views.
- The user model uses email as the username. Registration runs Django’s password validators. Login and OTP have a second throttle keyed by the target account, not only by IP. That is the correct defense against credential stuffing from many addresses.
- OTP values are stored as HMAC-SHA256, compared with `hmac.compare_digest`, and a new code deletes the previous one. The email log is given a masked body (`******`), not the live code. Failed attempts are counted.
- JWT refresh tokens rotate and the blacklist app is installed. Password change *attempts* to revoke outstanding refresh tokens and close activity rows.
- Notifications are queried with `user=request.user`. Mark-read cannot update another user’s row.
- The role model, system-role sync command, and admin protection against deleting system roles are implemented and covered by tests. Nothing in the shipped API uses those roles yet, but the machinery is not a stub.
- The Docker image is multi-stage, drops to `appuser`, and does not copy `.env`. Production Postgres is not published to the host. Production pgAdmin is behind a Compose profile and bound to `127.0.0.1`.
- The response envelope and the friendly exception handler are a coherent API style, when views do not bypass them by stuffing raw exceptions into `errors`.

## Critical

### 1. The production container command is not installed

`production-api.docker-compose.yml` starts Gunicorn. `requirements.txt` does not contain `gunicorn`. A clean image build will crash on boot with “gunicorn: not found”.

The same file is a pip freeze of a developer machine (`prompt_toolkit`, `colorama`, `wcwidth`) rather than a runtime manifest. Production and test dependencies are not split. `pytest` and `pytest-django` are absent, which is why this audit could not run the suite.

### 2. Activity tasks are published to a queue the worker does not consume

`record_activity_task` and `end_session_task` are routed to the `activity` queue. Settings even comment the worker command that would drain it:

`celery -A my_django worker -Q activity,default`

Both Compose files start:

`python -m celery -A my_django.celery worker -l info`

Celery’s default queue is named `celery`, not `default`. Unrouted work (email, the beat heartbeat) goes to `celery`. The worker, started with no `-Q`, consumes `celery` only. Activity messages sit in Redis until something else deletes them. The feature writes a success path in the HTTP response and then drops the data.

There is no retention job for `UserActivity` even if a worker were pointed at the right queue. Every request, including anonymous ones, enqueues a row.

### 3. CI/CD will not run, and the script is unsafe if it is moved into place

Workflows live in `github/workflows/`, not `.github/workflows/`. GitHub Actions does not load that path. “Inactive on GitHub” is not only a switch that was left off. The files are in the wrong directory.

If they are moved as-is, they still fail:

- `cp .env.ci.example .env` — that file does not exist. The only sibling is an empty `docker/.env.ci.dummy`.
- The job runs `python manage.py test`. Django’s runner collects `apps/*/tests.py`. It does not collect the pytest suite under `tests/`, which is the suite the README tells people to trust.
- `.dockerignore` excludes `tests/`, so the in-image test step cannot see that suite either.
- The image is pushed, including the `:latest` tag, **before** the test step. A failing test still publishes the image. The deploy job waits for CI, but the registry is already updated.
- Lint is commented out. There is no coverage gate, `pip-audit`, or `bandit`.
- CI installs Python 3.13. The image is `python:3.12-slim`.
- Deploy SSHes in, force-deletes every local tag of the image, then pulls. If the pull fails, the previous image may already be gone. There is no rollback, no post-deploy health gate, and no concurrency lock.
- Compose variables are interpolated into the remote shell script. A variable that contains shell metacharacters becomes a command.

### 4. Production defaults fight the Compose stack

`EnvConfig.ALLOWED_HOSTS` defaults to `*`, including when `DEBUG` is false. `settings.py` only forces `*` in debug; production still accepts the env default. Host-header attacks stay open unless every deploy remembers to override it. `.env.example` ships `ALLOWED_HOSTS=*`.

`SECURE_SSL_REDIRECT` defaults to true outside debug and tests. The API compose file publishes plain HTTP on port 8000 and has no TLS proxy. Clients are redirected to HTTPS that this stack does not terminate. `SECURE_PROXY_SSL_HEADER` is never set, so putting Nginx in front later still will not convince Django the request was HTTPS.

The healthcheck uses `curl -fsS http://localhost:8000/health/` without `-L`. A 301 is not a curl failure, so the container can look healthy while every real client is redirected away.

`EMAIL_USE_SSL` is read from the environment and never assigned in `settings.py`. Port 465 is handled only inside the diagnostic SMTP probe, not by the mail backend that actually sends OTP.

### 5. Account existence is part of the API contract

`verify_otp_rules` returns **404 “User not found”** for password reset and **400 “User already exists”** for registration. `apps/otp/tests.py` locks both behaviors in. A public template that does this lets anyone map which emails have accounts. Password reset should return the same response whether or not the user exists, and still send mail only when it should.

### 6. Client IP is not trustworthy, but throttles and audit logs treat it as if it were

`get_client_ip` returns `CF-Connecting-IP` as soon as the header parses as an IP. Nothing checks that the TCP peer is Cloudflare. On any deploy that is not behind Cloudflare, with that header stripped at the edge, a client sets the header and chooses the address used for IP throttles and for `UserActivity` / `SystemLog`.

The target-account throttle still helps. The IP throttle and the audit trail do not.

`LoggingContextMiddleware` also copies `X-Request-ID` from the client with no format check. Callers can forge correlation ids and put arbitrary text into logs.

### 7. Password reset burns the OTP before it accepts the new password

`ResetPasswordView` calls `otp_serializer.verify()`, which deletes the code on success, and only then calls `reset_password()`. `validate_password` runs inside `change_password`. A weak new password returns 400 and the code is already gone. The user must request another OTP.

`RegisterSerializer` has the same side effect inside `validate()`: a later `create_user` failure (duplicate email race, database error) consumes a valid code. Verification does not belong in serializer validation.

The verify path itself is read-compare-delete, not a single Redis operation. Two concurrent requests with the same code can both pass `compare_digest` before either delete runs.

### 8. Token revocation can fail silently, and logout is not bound to the caller

`revoke_user_tokens` wraps the whole blacklist loop in `except Exception: pass`. Password change and password reset still return success. Refresh lifetime defaults to **720 hours (30 days)**. If the blacklist write fails, the old refresh token keeps working for a month. There is no scheduled cleanup of `OutstandingToken`, so that table grows for the life of the project.

Logout accepts any refresh string, blacklists that token, and then ends **all** activity sessions for `request.user`. It never checks that the token’s user id is the authenticated user. One device logout does not revoke that user’s other refresh tokens. The next request from a still-valid access token creates a new activity session, because session rows are not tied to the JWT.

Access tokens are not in SimpleJWT’s outstanding-token table. After a password change they remain valid until the access TTL (default 15 minutes), even when revocation works. That part is normal for this library. The silent failure around refresh tokens is not.

### 9. Soft-delete does not disable the account

`User.objects` is a `UserManager` that returns every row, including `deleted_at` set. `soft_delete()` does not set `is_active=False`. A soft-deleted user can still pass `ModelBackend` and receive a JWT.

### 10. “Change email” OTP is enabled and cannot be delivered

`OTPPolicy` turns `change_email` on. `OTPService.send` stores the code, then queues mail with `purpose` set to the OTP purpose (`change_email`). `EmailPurpose` has no such value. `EmailLogSerializer` will reject the log row inside the worker. The HTTP handler has already returned 200, because `delay()` does not wait. The code sits in Redis and no mail goes out.

`apps/emails/services/otp.py` is a second sender, used by a unit test and not by `OTPService`. The live path and the tested path are not the same function.

There is no endpoint that consumes a `change_email` code. The policy advertises a flow the API does not finish.

## High

### Session management is an activity log, not a session

`ActivityTrackingMiddleware` keeps one cache key per user id, `activity:session:{pk}`, and reuses the latest active `UserSession`. A second device does not get its own session. Device type is written only when a row is created. Logout and password change flip `is_active` on those rows, then a still-valid JWT creates another row on the next request.

That is request analytics with a session-shaped table. It is not server-side session control. The docs and the logout view talk about it as if it were.

### Debug diagnostics are unauthenticated and include tracebacks

`HealthReportView` is `AllowAny` and is mounted at `/` whenever `DEBUG` is true. `health_error_response` puts `traceback.format_exc()` into the payload. The SMTP probe logs in with the real mailbox password and returns the exception object on failure. `.env.example` sets `DEBUG=True`. Anyone who deploys that file, or who leaves debug on, publishes a diagnostic page.

`/` is also documented in `docs/README.md` as a normal unauthenticated route, with no mention that it exists only in debug.

### Startup has no ordering

The API compose file does not wait for Postgres or Redis. They are not in the same file, and the web service has no `depends_on`. `entrypoint.sh` runs `migrate` once and exits on failure. Restart policy will crash-loop until the database appears. Redis has no password and no `maxmemory`. Cache, OTP, and the Celery broker all default to `redis://…/0`.

Local Postgres is published on `0.0.0.0:5432`. Local pgAdmin is published on `0.0.0.0:5050`. The production file is tighter. The local file is the one people leave running.

### Static files and admin will be unstyled

`STATIC_ROOT` is set. Nothing runs `collectstatic`. WhiteNoise is not installed. Gunicorn will not serve admin CSS.

### `.dockerignore` does not match the secrets ignore

Git ignores `bruno_api/secrets/*`. The Docker ignore does not. A local `development.secrets.env` sitting next to the example file is copied into the image by `COPY . .`.

### Role permission changes do not invalidate anyone

Signals on `Role.permissions` and `Role.groups` are `pass`. The in-memory permission cache lives on the user instance, and JWT reloads the user per request, so this is not a long-lived shared cache bug. It is unfinished: the comments describe invalidation that the code does not do. No shipped endpoint calls `HasRole` or `HasPermission`. New users are created with no role. The RBAC package is a library inside the template, not part of the request path.

### Logging middleware still expects another product’s user

`LoggingContextMiddleware` reads `request.user.profile.business`. This user model has no profile and no business. The lookup is swallowed by `except Exception`. `business_id` is still a column on `SystemLog`. That is leftover structure, and it runs on every request.

The database log handler inserts a row for every `django.logs.app` record from a `QueueListener` thread. Under Gunicorn’s prefork model that listener is easy to get wrong, and the table becomes a second unbounded write path next to `UserActivity`. Log files are written inside the container under `apps/logs/logs_output` with no volume, so a recreate deletes them. The 30-day rotation does not survive the container.

## Medium

- `ResetPasswordView`, `ChangePasswordView`, and `LogoutView` pass `errors=e` into `error_response`. The debug traceback is gated on `DEBUG`. The `errors` field is not. `_normalize_errors` stringifies a bare exception, so production clients receive exception text.
- `_enforce_limit` is never called. `MAX_ACTIVE_OTPS` does nothing. The class docstring still says “max 5 active OTPs”. `generate()` always deletes the previous code. The config default is 1. Three stories, one behavior.
- `get_or_400` treats only `None` as missing. An empty string passes a required field.
- Password rules are Django’s defaults (minimum length 8). Fine for a starter. Not a hardened policy.
- Signing uses `SECRET_KEY` and HS256. There is no separate JWT key, so rotating the Django secret invalidates tokens, OTP HMACs, and sessions together.
- `OutstandingToken` is never pruned.
- The beat schedule is a one-minute heartbeat so the debug page can show “beat is alive”. There is no persistent scheduler and no lock. A second beat process would double-fire. The heartbeat key lives in the same cache the throttles use.
- `apps/emails/utils/general.py` imports `transaction` and does not use it. Mail is sent in the worker after the log row is saved, which is fine, but a failure before `email_log_id` is attached retries poorly.
- Placeholder docstring in `str_replace_from_dict` (`:param text: Description`). That function is not the only thin comment, but the OTP and permission modules show the author can document properly. The quality is uneven.
- `.agents/django-rules.md` describes `apps/core/middleware/admin_throttle` and a Redis requirement for every throttle. The middleware file is not in the tree. Tests and `TESTING` force LocMem cache, so throttle tests do not prove the production Redis configuration.

## Testing

The suite under `tests/` is organized the way a real project should be: unit, API, integration, workflow, and a dedicated role/permission module. Fixtures build users and fake Redis instead of skipping the OTP service. Throttle tests deliberately rotate `REMOTE_ADDR` and assert 429 on the target key. That is good work.

It does not support the claim that the API is “properly tested” as a gate on this template.

- `pytest` is not a project dependency. A fresh `pip install -r requirements.txt` cannot run `pytest`, which is the command in the root README. This audit confirmed the virtualenv has no `pytest` module.
- CI does not run that command. See the critical CI finding.
- `pytest.ini` defines a `security` marker. No test uses it.
- `FakeRedisClient.expire` returns true and ignores TTL. `set(..., ex=)` does not expire. OTP lifetime is untested. A bug that made codes live forever would still pass.
- `tests/workflows/test_password_recovery.py` requests an OTP, then calls `OTPService.generate()` again and submits that second code. `generate()` deletes the code that was emailed. The test never reads the Celery payload. It passes even if the mail contains the wrong code or no code.
- App-level `tests.py` files (`APITestCase`) and the pytest tree overlap. Two runners, two styles, one of them invisible to `manage.py test` unless invoked explicitly.
- There is no coverage config and no failing threshold.
- Bruno is a tidy collection with chained variables and a few negative cases. `Register New User.bru` asserts status **201 or 400**. A broken register still passes. Bruno is not run in CI. `Local-Docker.bru` is described in the Bruno README as port 8080; Compose publishes 8000.

I did not execute the suite. I will not invent a pass/fail count.

## Documentation

`README.md` at the repo root is the most accurate user-facing document: real paths, real env vars, an honest note that production must set `DEBUG=False`.

`docs/README.md` is not at the same standard. It calls the system production-grade in the opening paragraph, and the endpoint table lists `POST /v1/otp/get-apps/otp/`. The route is `POST /v1/otp/get-otp/`. The same wrong path appears again in that file’s OTP section. People cloning this as a base will copy the wrong URL into clients.

App READMEs exist and are useful as orientation. They drift from the code in the same way the OTP docstring drifts from `_enforce_limit`. `.agents/django-rules.md` is an internal standard the repository only partly follows. Treat it as intention, not as a description of this tree.

## Docker, in one pass

| What | State |
|---|---|
| Image | Multi-stage, venv, non-root, `curl` present for the healthcheck. Shebang in `entrypoint.sh` is not on line 1; the image invokes it with `sh`, so this is harmless. |
| Web process | Gunicorn flags are reasonable (2 workers, 2 threads, 60s timeout, `init: true`). The binary is not installed. No `--forwarded-allow-ips`. No `max-requests`. |
| Worker / beat | Wrong queues. No healthcheck. Beat schedule file is inside the container filesystem. |
| Data | Postgres 15 and Redis 7 are current enough. No healthchecks, no Redis auth, no backup story, shared Redis DB. |
| Network | `dt_net` is `external: true`. A new clone fails until someone creates the network by hand. That step is easy to miss. |
| Secrets in the image | `.env` is ignored. Bruno secret env files are not. |
| Static / media | `./media` is mounted. Static files are not collected. |

## Criterion notes

**Security.** The OTP and throttle design is the part I would keep without a rewrite. The failures are default configuration and a few API choices that tests now freeze in place: enumeration, trusted `CF-Connecting-IP`, exception strings, and revocation that cannot fail visibly. Fix those before this template is exposed to the internet. Admin at `/admin/` has no extra throttle or IP allowlist. That is normal Django, and it should be said in the deploy docs rather than left as an implied hardening step.

**Feature correctness.** Happy-path register, login, refresh, logout-of-one-token, notification list, and health-of-database are coherent. Session, activity, change-email OTP, soft-delete, and “SSL on by default” are not coherent with the rest of the design.

**Reliability.** The code often catches exceptions so the HTTP response still returns. That is right for analytics middleware. It is wrong for `revoke_user_tokens`. Queue mismatch turns the same pattern into silent data loss.

**Reusability.** A new project can add an app beside these without fighting a monolith view file. It cannot be re-skinned by changing one setting module. Names to replace by hand: `my_django`, container prefix `dt_`, `TIME_ZONE = Asia/Dhaka`, Celery timezone, the ghost `business` fields, and docs that still say “Django Template” in the OTP email footer.

**Modular coding.** `v1` URL modules, `OTPPolicy`, service functions, and the permission helpers are the right cut. `settings.py` should be `base` / `local` / `production` / `test` before this is copied again. `TESTING = "pytest" in sys.argv` is a string search, not a settings module. Two OTP mail functions should be one.

**Production-grade.** Missing process in the image, wrong worker command, CI that cannot run, and security defaults that match `.env.example` more than a locked-down deploy. I would not put this on a VPS this week.

## Fix this before the next project starts from this repo

In this order:

1. Add `gunicorn` to the runtime requirements. Split a `requirements-dev.txt` that contains `pytest`, `pytest-django`, and a coverage plugin. Stop freezing the REPL tools into the production file.
2. Point the worker at the queues that exist: set `CELERY_TASK_DEFAULT_QUEUE` and start the worker with `-Q celery,activity` (or rename the queues so there is one story). Add a test that the email task and the activity task are consumed by that worker command.
3. Move workflows to `.github/workflows/` only after the job runs `pytest`, uses a real CI env file, and pushes the image only after tests pass. Add a rollback or at least do not delete the current image before the new pull succeeds.
4. Change production defaults: `ALLOWED_HOSTS` empty unless set, `SECURE_SSL_REDIRECT` false until a TLS proxy exists, set `SECURE_PROXY_SSL_HEADER` in the proxy setup, and make the healthcheck hit the app without treating a redirect as success.
5. Stop telling anonymous callers whether an email is registered. Return one password-reset response. Adjust the tests that currently require 404 and “already exists”.
6. Ignore `CF-Connecting-IP` unless the edge is actually Cloudflare and that header is stripped from client traffic. Generate `X-Request-ID` on the server.
7. Verify the OTP only after the new password is valid, and delete it in one Redis operation. Do not call `verify()` from `Serializer.validate()`.
8. Make `revoke_user_tokens` raise on failure. Bind logout to the token’s user id. Set `is_active=False` inside user soft-delete, or stop soft-deleting users.
9. Map OTP purposes onto `EmailPurpose` before queueing mail, or stop enabling purposes that have no completion endpoint.
10. Either bind activity sessions to the refresh token, or document them as analytics and stop calling logout “session management”.

## What this audit did not do

- Did not run pytest, Bruno, or a container build. The missing dependency is recorded above; I did not install packages into the environment to manufacture a green run.
- Did not scan git history for secrets that were committed and later removed.
- Did not review `.env`. It is present locally and gitignored. `.env.example` is enough to judge the defaults.
- Did not treat `.agents/skills/` as product code. Those files are third-party skill notes, not the template.

## Bottom line

The auth and OTP design is good enough to build on. The claim around it is ahead of the tree. Ship the application layout. Do not ship the Compose command, the worker command, the CI file, or the production defaults until the critical list is done.
