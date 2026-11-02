import redis
from django.conf import settings


# ------------------------------------------------------------------
# Redis Client (singleton-style module instance)
# ------------------------------------------------------------------

def _create_redis_client() -> redis.Redis:
    """
    Create a Redis client using REDIS_URL.

    Uses connection pooling internally.
    Raises configuration error if REDIS_URL is missing.
    """

    redis_url = getattr(settings, "REDIS_URL", None)

    if not redis_url:
        raise ValueError("REDIS_URL is not configured in Django settings.")

    return redis.Redis.from_url(
        redis_url,
        decode_responses=True,   # Always return str instead of bytes
        socket_timeout=5,        # Prevent hanging connections
        socket_connect_timeout=5,
        retry_on_timeout=True,
    )


# Shared Redis instance
redis_client: redis.Redis = _create_redis_client()