# app/services/execution_service.py

from typing import Dict, Any, Optional

from app.services.parser_service import apply_learning_boost
from app.services.decision_service import apply_decision
from app.services.action_engine import apply_action
from app.services.order_service import create_order_from_parsed
from app.services.response_formatter import format_order_for_frontend
from app.services.usage_service import log_event


# =====================================
# 🚀 EXECUTION PIPELINE (SINGLE ENTRY)
# =====================================


async def execute_pipeline(
    parsed: Dict[str, Any],
    trace_id: Optional[str] = None,
    existing_order: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Full deterministic pipeline:
    parsed → decision → action → persistence → formatting
    """

    try:
        # =====================================
        # 🧠 LEARNING BOOST (SAFE)
        # =====================================
        raw_message = parsed.get("raw_message", "")
        parsed = apply_learning_boost(raw_message, parsed)

        # =====================================
        # 🧠 DECISION ENGINE
        # =====================================
        decision_result = apply_decision(parsed, trace_id=trace_id)

        # =====================================
        # ⚙️ ACTION ENGINE
        # =====================================
        action_result = apply_action(
            decision_result=decision_result,
            parsed=parsed,
            existing_order=existing_order,
            trace_id=trace_id,
        )

        # =====================================
        # 💾 PERSISTENCE LAYER
        # =====================================
        final_order = None

        status = action_result.get("status")
        is_executable = status in {"success", "updated", "merged"}

        if is_executable:
            created = create_order_from_parsed(
                data=parsed,
                decision_data=decision_result,
                trace_id=trace_id,
            )

            if isinstance(created, dict):
                final_order = created.get("order", created)
            else:
                final_order = created

        # =====================================
        # 🎨 RESPONSE FORMATTER
        # =====================================
        formatted_order = (
            format_order_for_frontend(final_order) if final_order else None
        )

        # =====================================
        # 📊 FINAL RESPONSE
        # =====================================
        response = {
            "success": True,
            "decision": decision_result,
            "action": action_result,
            "order": formatted_order,
        }

        log_event(
            event="execution_pipeline_success",
            trace_id=trace_id,
            status="ok",
            meta={
                "action": decision_result.get("action"),
                "confidence": decision_result.get("meta", {}).get("confidence"),
                "action_status": status,
            },
        )

        return response

    except Exception as e:
        log_event(
            event="execution_pipeline_error",
            trace_id=trace_id,
            status="error",
            meta={"error": str(e)},
        )

        return {
            "success": False,
            "error": str(e),
            "decision": None,
            "action": None,
            "order": None,
        }
