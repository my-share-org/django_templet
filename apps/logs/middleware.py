import uuid
from django.utils.deprecation import MiddlewareMixin
from apps.core.utils.general import get_client_ip
from .utils import (
    request_id_var, 
    actor_id_var, 
    actor_type_var, 
    actor_email_var,
    ip_address_var, 
    user_agent_var,
    request_var,
    business_id_var,
)
from .choices import ActorType

class LoggingContextMiddleware(MiddlewareMixin):
    """
    Middleware to inject request-scoped data into contextvars.
    This enables anywhere in the application to log the request_id
    and user transparently.
    """

    def process_request(self, request):
        # Generate and store request ID
        req_id = request.META.get('HTTP_X_REQUEST_ID', str(uuid.uuid4()))
        request.request_id = req_id # Attach to request object for convenience
        
        # Set into context variable
        request_id_var.set(req_id)
        request_var.set(request)
        
        # Determine actor
        if hasattr(request, 'user') and request.user.is_authenticated:
            actor_id_var.set(str(request.user.id))
            actor_type_var.set(ActorType.USER)
            actor_email_var.set(str(request.user.email) if request.user.email else None)
            # Set business_id from the authenticated user's profile
            try:
                if request.user.profile.business:
                    business_id_var.set(str(request.user.profile.business.id))
                else:
                    business_id_var.set(None)
            except Exception:
                business_id_var.set(None)
        else:
            actor_id_var.set(None)
            actor_type_var.set(ActorType.ANONYMOUS)
            actor_email_var.set(None)
            business_id_var.set(None)
            
        # Determine IP Address safely without trusting spoofed X-Forwarded-For
        ip = get_client_ip(request)
        ip_address_var.set(ip)
        
        # Determine User Agent
        user_agent_var.set(request.META.get('HTTP_USER_AGENT')[:255] if request.META.get('HTTP_USER_AGENT') else None)

    def process_response(self, request, response):
        # We can append the request_id to the response headers for client tracking
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
            
        # Clear context vars memory
        request_id_var.set(None)
        actor_id_var.set(None)
        actor_type_var.set(None)
        actor_email_var.set(None)
        ip_address_var.set(None)
        user_agent_var.set(None)
        request_var.set(None)
        business_id_var.set(None)
            
        return response
