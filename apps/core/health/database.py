from apps.core.utils.health_response import health_ok_response, health_error_response
from django.db import connection
from django.conf import settings
import traceback

def check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()

        return health_ok_response(
            name="Database",
            message="Health OK",
        )

    except Exception as e:
        return health_error_response(
            name="Database",
            message="Health Error",
            errors=e,
        )


def check_redis():
    try:
        import redis

        client = redis.Redis.from_url(settings.REDIS_URL)
        client.ping()

        return health_ok_response(
            name="Redis",
            message="Health OK"
        )

    except Exception as e:
        return health_error_response(
            name="Redis",
            message="Health Error",
            errors=e,
        )

