# app/worker/worker.py
import json
import asyncio
import uuid
import redis
import logging

from app.services.parser_service import parse_conversation
from app.services.order_service import create_order_from_parsed
from app.services.decision_service import apply_decision
from app.services.usage_service import log_event
from app.services.queue_service import get_redis

logger = logging.getLogger("worker")

r = get_redis()

QUEUE_NAME = "orders_queue"

async def worker():
    logger.info("🚀 Worker started...")

    while True:
        _, data = r.blpop(QUEUE_NAME)
        job = json.loads(data)

        trace_id = str(uuid.uuid4())

        try:
            # 🔥 نفس pipeline الحقيقي
            parser_payload = await parse_conversation(
                [job["content"]],
                conversation_id=job["conversation_id"],
                trace_id=trace_id
            )
            parsed = (
                parser_payload.get("order", {})
                if isinstance(parser_payload, dict) and parser_payload.get("multi_orders") is False
                else {}
            )

            decision = apply_decision(parsed)
            logger.debug(f"🎯 DECISION: {decision}")
            order = create_order_from_parsed(
                data=parsed,
                decision_data=decision,
                trace_id=trace_id
            )

            log_event(
                event="worker_success",
                trace_id=trace_id,
                conversation_id=job["conversation_id"],
                status="success",
                order_id=getattr(order, "id", None)
            )

        except Exception as e:
            log_event(
                event="worker_error",
                trace_id=trace_id,
                conversation_id=job["conversation_id"],
                status="failed",
                error=str(e)
            )

if __name__ == "__main__":
    asyncio.run(worker())