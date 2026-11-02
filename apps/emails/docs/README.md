# Emails Module

## Table of Contents

1. [Overview](#1-overview)
2. [EmailLog Model](#2-emaillog-model)
3. [Sending Emails](#3-sending-emails)
4. [Async Task & Retry Logic](#4-async-task--retry-logic)
5. [Email Purposes](#5-email-purposes)
6. [Admin Interface](#7-admin-interface)
7. [Configuration](#8-configuration)
8. [Adding New Email Types](#9-adding-new-email-types)

---

## 1. Overview

The `emails` app provides a centralized, auditable, and fault-tolerant email delivery system. All outbound emails in the application are routed through this module.

Key features:

- **Asynchronous delivery** — Emails are dispatched via Celery tasks, keeping API response times fast.
- **Automatic retry** — Failed deliveries are retried up to 3 times with a delay between attempts.
- **Full audit trail** — Every email attempt is recorded in the `EmailLog` model with status, attempt count, and timestamps.
- **HTML and plain text** — Supports both body types.
- **Purpose tagging** — Emails are categorized by purpose (e.g., OTP, Welcome, Password Reset) for reporting and filtering.

### File Structure

```
apps/emails/
├── migrations/
├── docs/
│   └── README.md           # This file
├── admin.py
├── apps.py
├── choices.py              # Enums for body type, status, and purpose
├── models.py               # EmailLog model
├── serializers.py          # EmailLogSerializer
├── services.py             # Core email sending logic
├── tasks.py                # Celery tasks
├── urls.py
└── views.py
```

---

## 2. EmailLog Model

**Module:** `apps.emails.models.EmailLog`

Every email dispatched by the system creates or updates an `EmailLog` record, providing a complete history of email activity.

### Fields

| Field | Type | Description |
|---|---|---|
| `to_emails` | `JSONField` | List of recipient email addresses |
| `bcc` | `JSONField` | List of BCC recipient addresses |
| `from_email` | `EmailField` | Sender address |
| `subject` | `CharField` | Email subject line |
| `body` | `TextField` | Email body content (HTML or plain text) |
| `body_type` | `CharField` | Body format: `HTML` or `TEXT` |
| `status` | `CharField` | Current status: `SENT`, `FAILED`, or `SCHEDULED` |
| `try_count` | `IntegerField` | Number of delivery attempts made |
| `schedule_at` | `DateTimeField` | Scheduled send time (nullable) |
| `sent_at` | `DateTimeField` | Timestamp of successful delivery (nullable) |
| `created_at` | `DateTimeField` | Record creation timestamp (auto-set) |

### Statuses

| Status | Meaning |
|---|---|
| `SCHEDULED` | Email is queued but not yet sent |
| `SENT` | Email was successfully delivered |
| `FAILED` | All retry attempts were exhausted without success |

---

## 3. Sending Emails

### High-Level API — `send_otp_email()`

**Module:** `apps.emails.services.send_otp_email`

The recommended way to send OTP emails. Wraps `send_email_core()` with OTP-specific defaults.

```python
from apps.emails.services import send_otp_email

send_otp_email(
    to_emails=["user@example.com"],
    otp_code="482910",
)
```

### Low-Level API — `send_email_core()`

**Module:** `apps.emails.services.send_email_core`

Use this for all other email types. It creates an `EmailLog` entry and enqueues the Celery delivery task.

```python
from apps.emails.services import send_email_core
from apps.emails.choices import EmailBodyType, EmailPurpose

send_email_core(
    to_emails=["user@example.com"],
    subject="Welcome to the platform",
    body="<h1>Hello!</h1><p>Thanks for joining.</p>",
    body_type=EmailBodyType.HTML,
    purpose=EmailPurpose.WELCOME,
)
```

#### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `to_emails` | `list[str]` | Yes | List of recipient addresses |
| `subject` | `str` | Yes | Email subject |
| `body` | `str` | Yes | Email body content |
| `body_type` | `EmailBodyType` | No | `HTML` or `TEXT`. Defaults to `HTML`. |
| `purpose` | `EmailPurpose` | No | Purpose tag for audit filtering |
| `bcc` | `list[str]` | No | BCC recipients |
| `from_email` | `str` | No | Override sender address. Defaults to `EMAIL_HOST_USER`. |
| `schedule_at` | `datetime` | No | Future send time (deferred delivery) |

---

## 4. Async Task & Retry Logic

**Module:** `apps.emails.tasks.send_email_task`

`send_email_core()` does not send the email directly. It creates the `EmailLog` record and then calls `send_email_task.delay()` to push the work onto the Celery queue.

### Task Behavior

```
send_email_task(log_id)
    │
    ├─ Fetch EmailLog by log_id
    ├─ Build Django EmailMessage object
    ├─ Attempt SMTP delivery
    │
    ├─ SUCCESS → Update log: status=SENT, sent_at=now()
    │
    └─ FAILURE (SMTPException)
         ├─ Increment try_count
         ├─ If retries remaining → retry after 30 seconds
         └─ If max retries exhausted → Update log: status=FAILED
```

### Retry Configuration

| Setting | Value | Description |
|---|---|---|
| Max retries | 3 | Total delivery attempts before marking as FAILED |
| Retry countdown | 30 seconds | Delay between retry attempts |
| Exception type | `SMTPException` | Only SMTP errors trigger a retry |

This means an email will be attempted up to **4 times** in total (1 initial + 3 retries) before being marked as `FAILED`.

### Monitoring Failed Emails

Failed emails can be reviewed in the Django admin under `Emails > Email Logs`, filtered by `status=FAILED`. The `try_count` field shows how many attempts were made.

---

## 5. Email Purposes

Defined in `apps/emails/choices.py` as `EmailPurpose`.

| Value | Description |
|---|---|
| `OTP` | One-time password delivery |
| `WELCOME` | New user welcome message |
| `PASSWORD_RESET` | Password reset link or code |
| `REGISTRATION` | Registration confirmation |
| `DISCOUNT_CODE` | Promotional or discount code |
| `OTHERS` | General / uncategorized emails |

---

## 6. Admin Interface

The `EmailLog` admin provides full visibility into email activity.

- **List display:** to\_emails, subject, status, purpose, try\_count, sent\_at, created\_at
- **Filters:** status, body\_type, purpose
- **Search:** subject, to\_emails
- **Read-only fields:** All fields (email logs are immutable records)

Access at: `/admin/emails/emaillog/`

---

## 7. Configuration

Email delivery is configured via environment variables loaded in `my_django/settings.py`.

| Variable | Description | Default |
|---|---|---|
| `EMAIL_HOST` | SMTP server hostname | `smtp.gmail.com` |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_HOST_USER` | SMTP username (also used as default sender) | — |
| `EMAIL_HOST_PASSWORD` | SMTP password or app-specific password | — |
| `EMAIL_USE_TLS` | Enable TLS encryption | `True` |

> **Gmail users:** Enable 2-factor authentication on the Google account and generate an **App Password** for use as `EMAIL_HOST_PASSWORD`.

---

## 8. Adding New Email Types

To add a new type of transactional email:

**Step 1 — Add the purpose to `EmailPurpose` in `apps/emails/choices.py`:**

```python
class EmailPurpose(models.TextChoices):
    # ... existing values ...
    INVOICE = 'INVOICE', 'Invoice'
```

**Step 2 — Create a service wrapper in `apps/emails/services.py`:**

```python
def send_invoice_email(to_emails: list, invoice_data: dict):
    subject = f"Your invoice #{invoice_data['number']}"
    body = render_invoice_html(invoice_data)  # your template rendering logic
    send_email_core(
        to_emails=to_emails,
        subject=subject,
        body=body,
        body_type=EmailBodyType.HTML,
        purpose=EmailPurpose.INVOICE,
    )
```

**Step 3 — Call the new function from wherever needed:**

```python
from apps.emails.services import send_invoice_email

send_invoice_email(to_emails=["customer@example.com"], invoice_data={...})
```

No changes are needed to the task or the log model — the existing infrastructure handles delivery, retries, and logging automatically.
