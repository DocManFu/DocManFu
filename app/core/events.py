"""Redis pub/sub event publishing for real-time SSE updates."""

import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

CHANNEL = "docmanfu:events"


def get_redis_client():
    """Create a Redis client from settings."""
    import redis

    return redis.Redis.from_url(settings.REDIS_URL)


def publish_event(event_type: str, data: dict) -> None:
    """Publish an event to the Redis pub/sub channel.

    Best-effort — exceptions are caught and logged so event publishing
    never breaks a Celery task.
    """
    try:
        client = get_redis_client()
        message = json.dumps({"event": event_type, "data": data})
        client.publish(CHANNEL, message)
        client.close()
    except Exception:
        logger.warning("Failed to publish event %s", event_type, exc_info=True)
