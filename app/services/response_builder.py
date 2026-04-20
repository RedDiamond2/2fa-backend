# app/services/response_builder.py
def build_order_response(order, parsed: dict):
    """
    🔥 Single Source of Truth for API Contract
    """

    order_data = order.model_dump() if hasattr(order, "model_dump") else order

    decision = parsed.get("decision_data", {}) or {}

    identity_raw = parsed.get("identity", {}) or {}

    # 🔥 Normalize identity
    strength = "weak"
    conf = identity_raw.get("confidence", 0)

    if conf > 0.8:
        strength = "strong"
    elif conf > 0.5:
        strength = "medium"

    identity = {
        "status": identity_raw.get("status", "unknown"),
        "strength": strength
    }

    return {
        "order": order_data,

        "decision_data": {
            "confidence_score": decision.get("confidence_score", 0),
            "missing_fields": decision.get("missing_fields", []),
            "action": decision.get("action", "review")
        },

        "meta": parsed.get("meta", {}),

        "warnings": parsed.get("warnings", []),

        "needs_review": parsed.get("needs_review", False),

        "identity": identity
    }