import redis
from django.conf import settings

# Create a Redis client from a single connection URL
redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
)
