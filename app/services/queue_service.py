 # app/services/queue_service.py
import json
import logging
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger("queue_service")

# 🔥 lazy init (حل مشاكل startup + reload)
_redis = None

def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=1  # 🔥 fail fast
        )
    return _redis

QUEUE_NAME = "orders_queue"

async def enqueue_bulk(messages, conversation_id):
    r = get_redis()

    pipeline = r.pipeline()  # 🔥 bulk push (أسرع ×10)

    for msg in messages:
        job = {
            "tempId": msg["tempId"],
            "content": msg["content"],
            "conversation_id": conversation_id
        }
        pipeline.rpush(QUEUE_NAME, json.dumps(job))

    try:
        await pipeline.execute()
    except Exception as e:
        logger.warning(f"Redis DOWN → fallback to sync processing: {str(e)}")

        # 🔥 fallback: processing مباشر (ما نخسر الطلبات)
        from app.routes.order_routes import run_pipeline
        from app.services.order_service import create_order_from_parsed
        import uuid

        for msg in messages:
            trace_id = str(uuid.uuid4())

            parsed = await run_pipeline(
                [msg["content"]],
                conversation_id,
                trace_id
            )

            create_order_from_parsed(
                data=parsed,
                decision_data=parsed.get("decision_data"),
                trace_id=trace_id
            )