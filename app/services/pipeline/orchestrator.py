# app/services/pipeline/orchestrator.py

from typing import List, Dict, Any, Optional

from app.routes.order_routes import _build_history, _enrich_parsed_order

from app.services.parser_service import parse_conversation
from app.services.confidence_service import compute_confidence
from app.services.warning_service import generate_warnings
from app.services.decision_service import apply_decision
from app.services.identity_service import resolve_identity


# =====================================
# 🚀 PIPELINE ORCHESTRATOR (CORE ENGINE)
# =====================================
async def run_pipeline(
    messages: List[str],
    conversation_id: str,
    trace_id: str,
    temp_id: Optional[str] = None,
) -> Dict[str, Any]:

    # 1️⃣ Build History (READ ONLY)
    history = _build_history(messages, conversation_id, persist=True)

    # 2️⃣ PARSER
    parser_payload = await parse_conversation(
        messages=history, conversation_id=conversation_id, trace_id=trace_id
    )

    # fallback safety
    if not isinstance(parser_payload, dict):
        parser_payload = {"multi_orders": False, "order": {}}

    # 3️⃣ Extract single order
    if parser_payload.get("multi_orders") is True:
        parser_order = (parser_payload.get("orders") or [{}])[0]
    else:
        parser_order = parser_payload.get("order") or {}

    # 4️⃣ ENRICH (still shared logic for now)
    parsed = _enrich_parsed_order(
        parser_order,
        messages=messages,
        conversation_id=conversation_id,
        trace_id=trace_id,
        temp_id=temp_id,
        history=history,
    )

    # 5️⃣ CONFIDENCE
    confidence_data = compute_confidence(parsed) or {}
    warnings = generate_warnings(parsed) or []

    parsed["meta"] = {
        "confidence": confidence_data.get("confidence", 0),
        "decision": confidence_data.get("decision", "review"),
        "field_confidence": confidence_data.get("field_confidence", {}),
        "warnings": warnings,
        "trace_id": trace_id,
    }

    # 6️⃣ IDENTITY
    parsed["identity"] = resolve_identity(parsed)

    # 7️⃣ DECISION (ONLY HERE)
    decision_data = apply_decision(parsed)

    parsed["decision_data"] = decision_data

    # 8️⃣ FINAL FLAGS
    parsed["needs_review"] = decision_data.get("needs_review", False)

    return parsed
