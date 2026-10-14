from django.conf import settings
from core.health import (
    check_email_service,
    check_database,
    check_redis,
    check_celery_worker,
    check_celery_beat,
)

def health_report():
    health = [
        check_email_service(),
        check_database(),
        check_redis(),
        check_celery_worker(),
        check_celery_beat(),
    ]

    # print(f"Health Check Report>>>>>: {health}")

    success_count = 0
    fail_count = 0
    for service in health:
        if service["success"]:
            success_count += 1
        else:
            fail_count += 1

    return {
        "debug_status": settings.DEBUG,
        "success_count": success_count,
        "fail_count": fail_count,
        "services": health,
    }
