"""SSE endpoint for real-time job progress events."""

import asyncio
import json
import logging

from fastapi import APIRouter, Query, Request
from starlette.responses import StreamingResponse

from app.core.config import settings
from app.core.events import CHANNEL
from app.core.security import decode_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


async def _event_generator(request: Request, user_id: str | None, is_admin: bool):
    """Async generator that subscribes to Redis pub/sub and yields SSE events.

    Filters events so users only receive events for their own documents.
    Admins receive all events.
    """
    import redis.asyncio as aioredis

    client = aioredis.Redis.from_url(settings.REDIS_URL)
    pubsub = client.pubsub()
    await pubsub.subscribe(CHANNEL)

    # Send initial connected event
    yield "event: connected\ndata: {}\n\n"

    try:
        while True:
            if await request.is_disconnected():
                break

            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=0.0
            )
            if message and message["type"] == "message":
                raw = message["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    parsed = json.loads(raw)
                    data = parsed.get("data", {})

                    # Filter by user ownership (admin gets all)
                    if not is_admin and user_id:
                        event_user_id = data.get("user_id")
                        if event_user_id and event_user_id != user_id:
                            continue

                    event_type = parsed.get("event", "message")
                    yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                except (json.JSONDecodeError, KeyError):
                    logger.warning("Malformed event message: %s", raw)
            else:
                await asyncio.sleep(0.1)
    finally:
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.close()
        await client.close()


@router.get("/api/events")
async def sse_events(request: Request, token: str = Query(None)):
    """Server-Sent Events endpoint for real-time job progress.

    Accepts JWT token as query parameter since EventSource doesn't support
    custom headers.
    """
    user_id = None
    is_admin = False

    if token:
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")
            is_admin = payload.get("role") == "admin"

    return StreamingResponse(
        _event_generator(request, user_id, is_admin),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
