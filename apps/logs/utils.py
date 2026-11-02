import inspect
import traceback
import sys
import contextvars

# Context variables for thread-local-like storage scoped to async/sync requests
request_id_var = contextvars.ContextVar("request_id", default=None)
actor_id_var = contextvars.ContextVar("actor_id", default=None)
actor_type_var = contextvars.ContextVar("actor_type", default=None)
actor_email_var = contextvars.ContextVar("actor_email", default=None)
ip_address_var = contextvars.ContextVar("ip_address", default=None)
user_agent_var = contextvars.ContextVar("user_agent", default=None)
request_var = contextvars.ContextVar("request", default=None)
business_id_var = contextvars.ContextVar("business_id", default=None)

def get_current_request_id() -> str | None:
    return request_id_var.get()

def get_current_actor_id() -> str | None:
    return actor_id_var.get()

def get_current_actor_type() -> str | None:
    return actor_type_var.get()

def get_current_ip_address() -> str | None:
    return ip_address_var.get()

def get_current_user_agent() -> str | None:
    return user_agent_var.get()

def get_current_request():
    return request_var.get()

def get_current_business_id():
    return business_id_var.get()

def get_current_actor_email() -> str | None:
    return actor_email_var.get()

def extract_traceback() -> str | None:
    """Extracts the traceback of the current exception, if any."""
    exc_type, exc_value, exc_traceback = sys.exc_info()
    if exc_type is not None:
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        return "".join(tb_lines)
    return None

def extract_caller_info() -> dict:
    """
    Extracts file_name and function_name of the code that called the logger.
    Skips the logging internal stack frames.
    """
    frame = inspect.currentframe()
    if not frame:
        return {"file_name": "unknown", "function_name": "unknown"}

    # Go back through frames until we escape the logs app namespace (or reach a reasonable limit)
    # 0 = extract_caller_info
    # 1 = services.log_xxx (wrapper)
    # 2 = user code calling log_xxx
    
    caller_frame = None
    try:
        # Step back frames
        f = frame.f_back
        while f:
            if "apps.logs.services" not in f.f_globals.get("__name__", ""):
                # We found the frame outside our logging service wrappers
                caller_frame = f
                break
            f = f.f_back
            
        if not caller_frame:
            # Fallback if somehow we couldn't escape
            caller_frame = frame.f_back.f_back if frame.f_back else frame
            
        return {
            "file_name": caller_frame.f_code.co_filename,
            "function_name": caller_frame.f_code.co_name,
        }
    finally:
        del frame
        del caller_frame # Prevent reference cycles
