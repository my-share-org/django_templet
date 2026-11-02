# Django Logging System Documentation

This document provides a step-by-step, easy-to-understand explanation of the custom logging system implemented in this Django project.

## 🌟 Overview
This logging system is designed to be **asynchronous, non-blocking, and highly contextual**. When an event is logged anywhere in the code, it automatically captures information like the user involved, IP address, request ID, and the exact file/function that triggered the log. It then writes the log silently in the background to three places:
1. **Console**: For local development.
2. **JSON Files**: For external log aggregators (like ELK or Datadog) with log rotation.
3. **Database**: Saved in the `SystemLog` model for admin UI access.

---

## 🔄 The Step-by-Step Flow

1. **HTTP Request Arrives (Middleware):** When a user makes a request, `LoggingContextMiddleware` catches it. It generates a unique `request_id`, finds the user's IP, browser (User-Agent), and their user ID. It saves these into "Context Variables" (`utils.py`).
2. **A Log is Triggered (Services):** Somewhere in the code, a developer calls `log_info("user_login", "User logged in successfully")` from `services.py`.
3. **Context Enrichment (Services):** The `log_info` function automatically grabs the context variables (User, IP, Request ID) and figures out exactly which file and function called it (`extract_caller_info`). It bundles all this data.
4. **Sent to Queue (Config):** The enriched log is sent to the standard Python `logger`. The `logging_config.py` intercepts this and sends it to a `QueueHandler`. This is crucial because it immediately returns control to the Django view, meaning logging takes **0 milliseconds** of the user's request time.
5. **Background Processing (QueueListener):** A background thread (`AutoQueueListener`) pulls the log from the queue and distributes it to the actual handlers.
6. **Formatting & Saving (Formatters / Handlers):** 
   - The `JSONFormatter` formats the log into a clean JSON string and saves it to a `.json` file.
   - The `DatabaseHandler` extracts the custom context and saves a new row in the `SystemLog` database table.

---

## 📂 File By File & Function By Function Explanation

### 1. `middleware.py`
**Purpose:** Intercepts web requests to gather context before the views run.
* `process_request(request)`: Extracts IP address, `HTTP_USER_AGENT`, current authenticated user, and generates an `X-Request-ID`. It saves these to global-like variables called "Context Variables", meaning we don't need to pass the `request` object down into every single function manually.
* `process_response(request, response)`: Cleans up the context variables to prevent memory leaks and attaches the `X-Request-ID` to the response headers so the frontend can track it.

### 2. `utils.py`
**Purpose:** Helper functions and context variables.
* `ContextVars`: Variables like `request_id_var` securely hold data for the lifetime of a single async/sync request thread.
* `get_current_...()` functions: Getters designed to retrieve the values stored in the context variables.
* `extract_traceback()`: Automatically grabs the Python error stack trace if an exception occurs.
* `extract_caller_info()`: Magic function that inspects the Python call stack to find out which file and function originally called the `log_info` or `log_error` function.

### 3. `services.py`
**Purpose:** The main interface developers use to log things.
* `_log(...)`: The core internal function. It calls all the `get_current_...()` helpers to gather context, merges it with developer-provided messages, and submits it down to the base Python `logger`. 
* `log_debug`, `log_info`, `log_warning`, `log_error`, `log_critical`: Convenience wrappers around `_log`. Developers use these directly (e.g., `services.log_info(...)`).
* `log_success`: A custom log level (Level 25) designed to indicate successful operations distinctly from plain info.

### 4. `logging_config.py`
**Purpose:** Tells Python how to wire all the logging pipes together.
* `get_logging_config(...)`: Returns a dictionary used inside Django's `settings.py`. It defines:
  * Loggers: Which logger grabs messages.
  * Handlers: Different destinations (Console, Rotating File, Database).
  * QueueHandler: Takes logs and puts them in a queue.
* `AutoQueueListener`: A tiny extension that ensures the background worker thread starts automatically so logs are processed asynchronously.

### 5. `handlers.py`
**Purpose:** Custom destination logic for logs.
* `DatabaseHandler.emit(record)`: This function is triggered whenever a log reaches the database destination. It grabs the enriched data (like `file_name`, `request_id`, `actor_id`) passed internally from `services.py` and uses Django's ORM (`SystemLog.objects.create(...)`) to save it completely decoupled from the main HTTP lifecycle.

### 6. `formatters.py`
**Purpose:** Defines how logs should look perfectly formatted.
* `JSONFormatter.format(record)`: Takes the raw python LogRecord object and transforms it into a strict JSON dictionary. It includes a smart fallback for any `metadata` to ensure standard types (so JSON encoding never crashes).

### 7. `models.py`
**Purpose:** Database representations.
* `SystemLog`: The Django model table that saves all the logs written by the `DatabaseHandler`. Contains indexes on `timestamp`, `log_level`, `event_name`, etc. to enable very fast querying in the Django Admin.
