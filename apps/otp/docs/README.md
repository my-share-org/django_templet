# OTP Module

## Table of Contents

1. [Overview](#1-overview)
2. [How It Works](#2-how-it-works)
3. [API Endpoints](#3-api-endpoints)
4. [OTP Purposes](#4-otp-purposes)
5. [OTP Policies](#5-otp-policies)
6. [OTPService Reference](#6-otpservice-reference)
7. [Configuration](#7-configuration)
8. [Security Design](#8-security-design)
9. [Integration Guide](#9-integration-guide)

---

## 1. Overview

The `otp` app provides a complete one-time password (OTP) system for any scenario that requires secondary verification. It is used across the application for registration email verification, password reset flows, and other sensitive operations.

Key characteristics:

- **Redis-backed** — OTPs are stored in Redis with automatic TTL-based expiry. No database table is required.
- **Purpose-driven** — Each OTP is tied to a specific purpose (e.g., `REGISTRATION`, `PASSWORD_RESET`), ensuring that an OTP issued for one flow cannot be used in another.
- **Hashed storage** — OTP values are hashed with SHA-256 before storage; raw values are never persisted.
- **Constant-time comparison** — Verification uses HMAC comparison to prevent timing attacks.
- **Per-purpose policies** — Authentication requirements, user existence checks, and delivery channels are configurable per purpose.

### File Structure

```
apps/otp/
├── migrations/
├── docs/
│   └── README.md           # This file
├── services/
│   ├── __init__.py         # Exposes OTPService
│   ├── apps.otp.py              # OTPService class
│   └── rules.py            # OTPPolicy, _OTP_POLICY_TABLE, verify_otp_rules
├── v1/
│   ├── serializers.py      # OtpVerifySerializer
│   ├── urls.py
│   └── views.py            # GetOtpView
├── apps.py
├── choices.py              # Enums for purpose and channel
└── throttles.py            # GetOtpRateThrottle
```

---

## 2. How It Works

### Generation Flow

```
Client → POST /v1/otp/get-apps/otp/  →  verify_otp_rules(request)
                                    │
                                    ├─ Extract & type-check fields (get_or_400)
                                    ├─ Validate purpose against the policy table
                                    ├─ Enforce auth / identifier / channel rules
                                    └─ Check user existence or duplication (per policy)
                                    │
                                OTPService.send()
                                    │
                                    ├─ Generate random OTP (length/charset from config)
                                    ├─ Hash the OTP (SHA-256) and store in Redis with TTL
                                    ├─ Enforce max active OTP limit
                                    └─ Dispatch email via send_email_task (Celery)
```

### Verification Flow

```
Client sends OTP in another endpoint (e.g., /v1/auth/password/reset/)
                                    │
                            OtpVerifySerializer.is_valid()
                                    │
                            OtpVerifySerializer.verify() → OTPService.verify()
                                    │
                                    ├─ Reject if MAX_VERIFY_ATTEMPTS exceeded (lockout)
                                    ├─ Look up stored hashes for (identifier, purpose)
                                    ├─ Hash the provided OTP
                                    ├─ HMAC compare against stored hashes
                                    ├─ If match → delete from Redis (one-time use)
                                    └─ Return True / False
```

---

## 3. API Endpoints

Base path: `/v1/otp/`

---

### POST `/v1/otp/get-apps/otp/`

Request an OTP for a given purpose and delivery channel.

**Authentication:** Conditional — depends on the policy of the requested `purpose` (see [OTP Policies](#5-otp-policies)).

**Request Body:**

```json
{
  "purpose": "registration",
  "user_identifier": "user@example.com",
  "otp_channel": "email"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `purpose` | string | Yes | The reason for the OTP, lowercase (see [OTP Purposes](#4-otp-purposes)) |
| `user_identifier` | string | Policy-dependent | Email address or phone number. Required when the policy sets `require_identifier`; otherwise derived from the authenticated user |
| `otp_channel` | string | Policy-dependent | `email` or `phone`. Only honored when the policy channel is `all`; otherwise the policy channel is forced |
| `region` | string | Phone only | Phone region code, required when the resolved channel is `phone` |

**Success Response — `200 OK`:**

```json
{
  "success": true,
  "message": "OTP sent successfully. Please check your email. Valid for 5 minutes.",
  "data": null
}
```

**Error Responses:**

| Status | Scenario |
|---|---|
| `400 Bad Request` | Missing/wrong-type field, invalid or disabled purpose, invalid identifier or channel, or user already exists (when the policy forbids duplicates) |
| `401 Unauthorized` | Authentication required for this purpose but token not provided |
| `404 Not Found` | Policy requires an existing user and none matched the identifier |
| `429 Too Many Requests` | Daily OTP throttle limit exceeded |

---

## 4. OTP Purposes

Defined in `apps/otp/choices.py` as `OtpPurpose`.

| Value | Description |
|---|---|
| `REGISTRATION` | Verify email address during new account registration |
| `LOGIN` | Two-factor login verification |
| `PASSWORD_CHANGE` | Verify identity before changing a known password |
| `PASSWORD_RESET` | Recover access when the password is forgotten |
| `VERIFICATION` | General-purpose identity verification |
| `CHANGE_EMAIL` | Verify ownership of a new email address |
| `CHANGE_PHONE` | Verify ownership of a new phone number |
| `CHANGE_USERNAME` | Confirm username change |
| `OTHER` | Custom or miscellaneous use cases |

### OTP Channels

Defined in `apps/otp/choices.py` as `OtpChannel`.

| Value | Description |
|---|---|
| `EMAIL` | Deliver OTP via email (fully implemented) |
| `PHONE` | Deliver OTP via SMS (not yet implemented) |
| `ALL` | Deliver via all available channels |

---

## 5. OTP Policies

Each purpose has a policy registered in the `_OTP_POLICY_TABLE` inside `apps/otp/services/rules.py` via the frozen `OTPPolicy` dataclass. `verify_otp_rules(request)` enforces every policy rule for an incoming OTP request and is what `GetOtpView` calls.

### `OTPPolicy` Fields

| Field | Type | Description |
|---|---|---|
| `enable` | `bool` | Whether this purpose is active |
| `require_auth` | `bool` | Whether the requester must be authenticated |
| `require_identifier` | `bool` | Client must supply `user_identifier`; when `False` it is derived from the authenticated user |
| `check_user_exists` | `bool` | A matching user must already exist (404 otherwise) |
| `allow_duplicate` | `bool` | A matching user may already exist; `False` rejects with 400 |
| `channel` | `OtpChannel` | Forced channel (defaults to `OTP_CHANNEL` config), or `ALL` to let the caller choose |

### Registered Policies

| Purpose | `enable` | `require_auth` | `require_identifier` | `check_user_exists` | `allow_duplicate` |
|---|---|---|---|---|---|
| `LOGIN` | No | No | Yes | Yes | Yes |
| `REGISTRATION` | Yes | No | Yes | No | No |
| `PASSWORD_CHANGE` | No | Yes | No | Yes | Yes |
| `PASSWORD_RESET` | Yes | No | Yes | No | Yes |
| `CHANGE_EMAIL` | Yes | Yes | No | Yes | Yes |
| `CHANGE_PHONE` | No | Yes | No | Yes | Yes |
| `CHANGE_USERNAME` | No | Yes | No | Yes | Yes |
| `VERIFICATION` | No | Yes | No | Yes | Yes |

> Policies can be modified in `apps/otp/services/rules.py` to match project-specific requirements without changing the underlying service logic.

---

## 6. OTPService Reference

**Module:** `apps.otp.services.OTPService`

### Class Methods

#### `OTPService.generate(user, purpose)`

Generates and stores a new OTP, enforcing the max active OTP limit. Oldest OTPs are evicted when the limit is exceeded.

| Parameter | Type | Description |
|---|---|---|
| `user` | `str` | Unique identifier (email address or phone number) |
| `purpose` | `OtpPurpose` | The use case for this OTP |

**Returns:** the raw OTP string (for delivery).

#### `OTPService.send(user, purpose, channel)`

Generates an OTP via `generate()` and dispatches it through the given channel. Email delivery goes through the `send_email_task` Celery task using the `otp_body.html` template; the `phone` channel is not yet implemented.

| Parameter | Type | Description |
|---|---|---|
| `user` | `str` | Unique identifier (email address or phone number) |
| `purpose` | `OtpPurpose` | The use case for this OTP |
| `channel` | `OtpChannel` | Delivery channel (`email` implemented, `phone` raises `NotImplementedError`) |

#### `OTPService.verify(user, purpose, submitted_otp)`

Verifies a submitted OTP.

| Parameter | Type | Description |
|---|---|---|
| `user` | `str` | The identifier the OTP was issued for |
| `purpose` | `OtpPurpose` | The purpose to verify against |
| `submitted_otp` | `str` | The raw OTP submitted by the user |

**Returns:** `True` on success, `False` if the OTP is invalid, expired, or the attempt lockout is active.

**Side effects:** The verified OTP is deleted from Redis immediately (one-time use). Each failed call increments a per-user/purpose attempt counter; once `MAX_VERIFY_ATTEMPTS` is exceeded within the TTL window, further attempts are rejected without checking. A successful verify clears the counter.

### Redis Key Structure

OTPs are stored under namespaced key patterns (the identifier is stored as its SHA-256 hash):

```
otp:{purpose}:{sha256(identifier)}:{uuid}          # one key per active OTP
otp:index:{purpose}:{sha256(identifier)}           # list of active OTP ids
otp:attempts:{purpose}:{sha256(identifier)}        # failed verify counter (lockout)
```

Multiple OTPs can exist concurrently for the same identifier/purpose pair (up to `MAX_ACTIVE_OTPS`). Each has an independent TTL.

---

## 7. Configuration

All OTP settings are loaded from environment variables.

| Environment Variable | Description | Default |
|---|---|---|
| `OTP_CHANNEL` | Default delivery channel used by policies | `email` |
| `OTP_LENGTH` | Number of characters in the generated OTP | `6` |
| `OTP_EXPIRY_MINUTES` | Time-to-live for each OTP in minutes | `5` |
| `OTP_ALLOW_NUMBER` | Include numeric digits in the OTP charset | `True` |
| `OTP_ALLOW_CAPITAL` | Include uppercase letters in the OTP charset | `False` |
| `OTP_ALLOW_SMALL` | Include lowercase letters in the OTP charset | `False` |
| `OTP_ALLOW_SPECIAL` | Include special characters in the OTP charset | `False` |
| `MAX_ACTIVE_OTPS` | Maximum number of active OTPs per identifier per purpose | `5` |
| `MAX_VERIFY_ATTEMPTS` | Failed verify attempts allowed before lockout (per identifier per purpose, within the TTL window) | `5` |
| `GET_OTP_THROTTLE_RATE_PER_DAY` | Maximum OTP requests per day per client | `25` |

---

## 8. Security Design

### Hashed Storage

The raw OTP value is **never stored**. Before persisting to Redis, the OTP is hashed using SHA-256:

```
stored_value = SHA256(raw_otp)
```

If Redis is compromised, attackers cannot recover OTP values from the hashes.

### Constant-Time Comparison

Verification uses `hmac.compare_digest()` to compare the hash of the submitted OTP against the stored hash. This eliminates timing-based side-channel attacks that could be used to enumerate valid OTPs.

### One-Time Use

Upon successful verification, the matching Redis key is deleted immediately. The OTP cannot be reused even within its TTL window.

### Rate Limiting

The `GetOtpRateThrottle` (a `UserRateThrottle`) applies a daily cap (default: 25 requests per day) on OTP generation requests — keyed by user id for authenticated callers and by IP for anonymous ones. This prevents automated OTP flooding, including for auth-required purposes.

### Brute-Force Lockout

`OTPService.verify()` tracks failed attempts per identifier/purpose in Redis. After `MAX_VERIFY_ATTEMPTS` failures within the OTP TTL window, all further attempts are rejected — so a valid OTP cannot be brute-forced by guessing (a 6-digit numeric OTP has only ~1M possibilities). A successful verification resets the counter.

### Purpose Isolation

An OTP generated for `REGISTRATION` cannot be used to verify a `PASSWORD_RESET` flow. The purpose is embedded in the Redis key, and verification always checks the stored purpose.

---

## 9. Integration Guide

### Using OTP in a Custom Flow

**Step 1 — Request OTP:**

```
POST /v1/otp/get-apps/otp/
{
  "purpose": "password_reset",
  "user_identifier": "user@example.com"
}
```

**Step 2 — Accept OTP in your endpoint and verify:**

```python
from apps.otp.v1.serializers import OtpVerifySerializer
from apps.otp.choices import OtpPurpose

# In your view:
otp_serializer = OtpVerifySerializer(data={
    "identifier": request.data["email"],
    "otp":        request.data["otp"],
    "purpose":    OtpPurpose.PASSWORD_RESET,
})
otp_serializer.is_valid(raise_exception=True)   # format checks only
if not otp_serializer.verify():                  # actual OTP check
    ...  # return a 400 — invalid or expired OTP
# Verification passed — proceed with the business logic
```

### Adding a New Purpose

1. Add the new value to `OtpPurpose` in `apps/otp/choices.py`.
2. Add a corresponding row to `_OTP_POLICY_TABLE` inside `apps/otp/services/rules.py`.
3. (Optional) Add a dedicated email template or delivery handler in the `emails` app.
