from django.db import models

class LogLevel(models.TextChoices):
    DEBUG = "DEBUG", "Debug"
    INFO = "INFO", "Info"
    WARNING = "WARNING", "Warning"
    ERROR = "ERROR", "Error"
    CRITICAL = "CRITICAL", "Critical"
    SUCCESS = "SUCCESS", "Success"  # Custom level for success events

class ActorType(models.TextChoices):
    SYSTEM = "system", "System"
    USER = "user", "User"
    SERVICE = "service", "Service"
    ANONYMOUS = "anonymous", "Anonymous"
