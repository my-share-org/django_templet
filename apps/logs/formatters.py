import json
import logging
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """
    Formats the log record as a structured JSON object.
    Ideal for Datadog, ELK, Splunk, etc.
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "event_name": getattr(record, "event_name", "system_event"),
            "logger_name": record.name,
        }
        
        # Add all contextual data
        optional_fields = [
            'actor_type', 'actor_id', 'actor_email', 'business_id', 'model_name', 'file_name', 
            'function_name', 'service_name', 'request_id', 'ip_address', 'user_agent', 'metadata'
        ]
        
        for field in optional_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                if field == 'metadata':
                    # Best-effort conversion to standard dict for JSON compatibility
                    try:
                        json.dumps(value) # Validation check
                        log_record[field] = value
                    except (TypeError, ValueError):
                        log_record[field] = str(value)
                else:
                    log_record[field] = value
                
        # Handle exceptions
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        elif hasattr(record, "traceback_data") and record.traceback_data:
             log_record['exception'] = record.traceback_data
            
        return json.dumps(log_record)
