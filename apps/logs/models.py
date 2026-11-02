from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class SystemLog(BaseModel):
    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    log_level = models.CharField(max_length=20, db_index=True)
    event_name = models.CharField(max_length=150, db_index=True)
    message = models.TextField()
    
    actor_type = models.CharField(max_length=50, blank=True, null=True)
    actor_id = models.CharField(max_length=255, blank=True, null=True)
    actor_email = models.EmailField(max_length=255, blank=True, null=True)
    business_id = models.CharField(max_length=255, blank=True, null=True)
    
    model_name = models.CharField(max_length=100, blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    function_name = models.CharField(max_length=255, blank=True, null=True)
    
    traceback = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True, null=True)
    
    service_name = models.CharField(max_length=100, blank=True, null=True)
    request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    
    ip_address = models.GenericIPAddressField(blank=True, null=True, db_index=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        db_table = 'logs_systemlog'
        ordering = ['-timestamp']
        verbose_name = 'System Log'
        verbose_name_plural = 'System Logs'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['event_name', 'log_level']),
            models.Index(fields=['actor_type', 'actor_id']),
        ]

    def __str__(self):
        return f"[{self.log_level}] {self.event_name} at {self.timestamp}"
