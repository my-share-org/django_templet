from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

@shared_task
def beat_heartbeat():
    cache.set("beat_last_seen", timezone.now().isoformat(), timeout=120)
