import logging
from django.db import close_old_connections
from django.utils import timezone

class DatabaseHandler(logging.Handler):
    """
    Custom logging handler that saves logs to the database using the SystemLog model.
    Since this runs in a separate thread via QueueListener, it does not block the main request.
    """
    def emit(self, record):
        from .models import SystemLog
        
        try:
            # Prevent infinite recursion if the DB logger itself throws a DB error
            if getattr(record, "name", "").startswith("django.db"):
                return

            # Extract exception string if trace exists standardly
            exc_str = None
            if record.exc_info:
                exc_str = self.formatException(record.exc_info)
            else:
                exc_str = getattr(record, "traceback_data", None)

            kwargs = {
                "log_level": record.levelname,
                "event_name": getattr(record, "event_name", "system_event"),
                "message": record.getMessage(),
                "timestamp": timezone.now(),
                
                "actor_type": getattr(record, "actor_type", None),
                "actor_id": getattr(record, "actor_id", None),
                "actor_email": getattr(record, "actor_email", None),
                "business_id": getattr(record, "business_id", None),
                
                "model_name": getattr(record, "model_name", None),
                "file_name": getattr(record, "file_name", record.filename),
                "function_name": getattr(record, "function_name", record.funcName),
                
                "traceback": exc_str,
                "metadata": getattr(record, "metadata", {}),
                
                "service_name": getattr(record, "service_name", None),
                "request_id": getattr(record, "request_id", None),
                "ip_address": getattr(record, "ip_address", None),
                "user_agent": getattr(record, "user_agent", None),
            }

            close_old_connections()
            try:
                SystemLog.objects.create(**kwargs)
            finally:
                close_old_connections()
            
        except Exception:
            self.handleError(record)
