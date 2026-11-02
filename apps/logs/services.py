import logging
from typing import Any, Dict, Optional

from .choices import ActorType
from .utils import (
    get_current_request_id,
    get_current_actor_id,
    get_current_actor_type,
    get_current_ip_address,
    get_current_user_agent,
    get_current_business_id,
    get_current_actor_email,
    extract_caller_info,
    extract_traceback,
    get_current_request,
)

logger = logging.getLogger("django.logs.app")

def _log(
    level: int,
    event: str,
    message: str,
    model_name: Optional[str] = None,
    actor_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    service_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    traceback: bool = False,
    **kwargs
):
    """
    Internal base logging function that injects all the necessary context
    into the log record's `extra` dictionary.
    """
    
    # Auto-extract context from middleware (if available)
    auto_request_id = get_current_request_id()
    auto_actor_id = get_current_actor_id()
    auto_actor_type = get_current_actor_type()
    auto_ip_address = get_current_ip_address()
    auto_user_agent = get_current_user_agent()
    auto_business_id = get_current_business_id()
    auto_actor_email = get_current_actor_email()
    
    # Try dynamic fetch from DRF authenticated request (lazy)
    # DRF auth runs after middleware, so re-fetch from the live request for accuracy
    req = get_current_request()
    if req and hasattr(req, 'user') and req.user.is_authenticated:
        auto_actor_id = str(req.user.id)
        auto_actor_type = ActorType.USER
        auto_actor_email = str(req.user.email) if req.user.email else None
        # Re-fetch business_id lazily (same pattern as actor_id)
        try:
            if req.user.profile and req.user.profile.business:
                auto_business_id = str(req.user.profile.business.id)
        except Exception:
            pass  # keep whatever middleware set
    
    # Auto-extract caller file/function
    caller_info = extract_caller_info()
    
    # Auto-extract traceback if requested and an exception is currently active
    tb_data = None
    if traceback:
        tb_data = extract_traceback()
        
    extra = {
        "event_name": event,
        "model_name": model_name,
        "actor_type": actor_type or auto_actor_type or ActorType.SYSTEM,
        "actor_id": actor_id or auto_actor_id,
        "actor_email": auto_actor_email,
        "business_id": auto_business_id,
        "service_name": service_name,
        "metadata": metadata or {},
        "request_id": auto_request_id,
        "ip_address": auto_ip_address,
        "user_agent": auto_user_agent,
        "file_name": caller_info.get("file_name"),
        "function_name": caller_info.get("function_name"),
        "traceback_data": tb_data,
    }
    
    # Include any extra kwargs strictly into metadata
    if kwargs:
        extra["metadata"].update(kwargs)

    logger.log(level, message, extra=extra)

def log_debug(event: str, message: str, **kwargs):
    _log(logging.DEBUG, event, message, **kwargs)

def log_info(event: str, message: str, **kwargs):
    _log(logging.INFO, event, message, **kwargs)

def log_success(event: str, message: str, **kwargs):
    # Custom level for SUCCESS (value 25 is between INFO/20 and WARNING/30)
    logging.addLevelName(25, "SUCCESS")
    _log(25, event, message, **kwargs)

def log_warning(event: str, message: str, **kwargs):
    _log(logging.WARNING, event, message, **kwargs)

def log_error(event: str, message: str, traceback: bool = True, **kwargs):
    _log(logging.ERROR, event, message, traceback=traceback, **kwargs)

def log_critical(event: str, message: str, traceback: bool = True, **kwargs):
    _log(logging.CRITICAL, event, message, traceback=traceback, **kwargs)
