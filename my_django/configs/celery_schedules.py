from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "beat-heartbeat": {
        "task": "apps.core.tasks.beat_heartbeat",
        "schedule": crontab(minute="*/1"),
    },
}
