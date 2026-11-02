from celery import current_app
from kombu.exceptions import OperationalError
from apps.core.utils.health_response import health_ok_response, health_error_response
from django.core.cache import cache


def check_celery_worker():
    try:
        # Check broker connection first
        with current_app.connection() as conn:
            conn.ensure_connection(max_retries=1)

        # Ping workers
        inspect = current_app.control.inspect(timeout=2)
        response = inspect.ping()

        if not response:
            return health_error_response(
                name="Celery Worker",
                message="No active workers found",
            )

        worker_count = len(response)

        # Check registered tasks
        registered = inspect.registered() or {}
        task_count = sum(len(tasks) for tasks in registered.values())

        return health_ok_response(
            name="Celery Worker",
            message=f"{worker_count} worker(s) active | {task_count} task(s) registered",
        )

    except OperationalError as e:
        return health_error_response(
            name="Celery Worker",
            message="Broker connection failed",
            errors=e,
        )

    except Exception as e:
        return health_error_response(
            name="Celery Worker",
            message="Worker health check error",
            errors=e,
        )


def check_celery_beat():
    try:
        last_seen = cache.get("beat_last_seen")

        if not last_seen:
            return health_error_response(
                name="Celery Beat",
                message="Beat not running (no heartbeat detected)",
            )

        return health_ok_response(
            name="Celery Beat",
            message=f"Last heartbeat at {last_seen}",
        )

    except Exception as e:
        return health_error_response(
            name="Celery Beat",
            message="Beat health check error",
            errors=e,
        )
