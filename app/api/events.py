"""SSE endpoint for real-time job progress events."""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import StreamingResponse

from app.core.auth import user_from_token
from app.core.config import settings
from app.core.events import CHANNEL
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


REVALIDATE_SECONDS = 60


def _authenticate(token: str) -> tuple[str, bool]:
    """Return (user_id, is_admin) for a valid access token; raises 401 otherwise."""
    with SessionLocal() as db:
        user = user_from_token(token, "access", db)
        return str(user.id), user.role == "admin"


def _token_still_valid(token: str) -> bool:
    try:
        _authenticate(token)
        return True
    except HTTPException:
        return False


async def _event_generator(request: Request, token: str, user_id: str, is_admin: bool):
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
        loop = asyncio.get_running_loop()
        next_check = loop.time() + REVALIDATE_SECONDS
        while True:
            if await request.is_disconnected():
                break

            # End the stream once the token expires or is revoked (password
            # change, deactivation); the client reconnects with a fresh token
            if loop.time() >= next_check:
                if not await asyncio.to_thread(_token_still_valid, token):
                    break
                next_check = loop.time() + REVALIDATE_SECONDS

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
                    if not is_admin and data.get("user_id") != user_id:
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
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Sync DB lookup runs off the event loop; the session is closed before
    # streaming so no connection is held for the stream's lifetime
    user_id, is_admin = await asyncio.to_thread(_authenticate, token)

    return StreamingResponse(
        _event_generator(request, token, user_id, is_admin),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
