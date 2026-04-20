# app/services/decision_service.py

from typing import Dict, Any, List, Optional
from app.services.usage_service import log_event

# =====================================
# 🔥 SOFT MODE (Production Toggle)
# =====================================
SOFT_MODE = True


# =====================================
# 🚀 DECISION ENGINE (ULTRA PRO - REDDIAMOND)
# =====================================
def apply_decision(parsed: Dict[str, Any], trace_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        meta: Dict = parsed.get("meta") or {}

        decision: str = meta.get("decision") or "manual"
        decision = decision.lower() if isinstance(decision, str) else "manual"

        confidence: float = meta.get("confidence") or 0.0
        warnings: List[str] = meta.get("warnings") or []
        if not isinstance(warnings, list):
            warnings = []

        conversation_id = parsed.get("conversation_id")
        customer = parsed.get("customer")
        items = parsed.get("items") or []

        # =====================================
        # 🧱 BASE RESULT
        # =====================================
        result: Dict[str, Any] = {
            "action": None,
            "needs_review": False,
            "reason": None,
            "risk_level": "low",
            "explain": ["decision_engine_v3"],
            "meta": {}
        }

        # =====================================
        # 🚨 BLOCKING (CRITICAL)
        # =====================================
        blocking_warnings = {
            "no_items",
            "missing_phone",
        }

        if any(w in blocking_warnings for w in warnings):
            result.update({
                "action": "hold",
                "needs_review": True,
                "reason": "critical_missing_data",
                "risk_level": "high",
            })
            result["explain"].append("Blocked: missing critical fields")

            return _finalize(result, decision, confidence, warnings)

        # =====================================
        # ⚠️ HIGH RISK WARNINGS
        # =====================================
        high_risk_warnings = {
            "invalid_phone",
            "invalid_quantity",
            "duplicate_item",
        }

        if any(w in high_risk_warnings for w in warnings):
            decision = "review"
            result["risk_level"] = "high"
            result["explain"].append("High risk detected → forced review")

        # =====================================
        # 📉 MEDIUM RISK
        # =====================================
        if warnings and result["risk_level"] != "high":
            result["risk_level"] = "medium"

        # =====================================
        # 🎯 MAIN DECISION LOGIC
        # =====================================

        if decision == "auto":
            result["action"] = "create"

            if warnings:
                if SOFT_MODE:
                    result["needs_review"] = False
                    result["reason"] = "soft_ignore_warnings"
                else:
                    result["needs_review"] = True
                    result["reason"] = "warnings_present"
            else:
                result["needs_review"] = False
                result["reason"] = "auto_clean"

        elif decision == "review":
            result["action"] = "create"

            if SOFT_MODE:
                result["needs_review"] = False
                result["reason"] = "soft_review_override"
            else:
                result["needs_review"] = True
                result["reason"] = "review_required"

        elif decision == "manual":
            result["action"] = "hold"
            result["needs_review"] = True
            result["reason"] = "insufficient_data"

        else:
            result.update({
                "action": "hold",
                "needs_review": True,
                "reason": "unknown_decision",
                "risk_level": "high",
            })
            result["explain"].append("Unknown decision type")

        # =====================================
        # 📊 CONFIDENCE ENGINE (CRITICAL)
        # =====================================

        if SOFT_MODE:
            if confidence < 0.2:
                result.update({
                    "action": "hold",
                    "needs_review": True,
                    "reason": "extremely_low_confidence",
                    "risk_level": "high",
                })
                result["explain"].append("Blocked: extremely low confidence")

            elif result["action"] == "create":
                result["needs_review"] = False
                result["reason"] = "soft_auto_success"
                result["risk_level"] = "low"

        else:
            if confidence < 0.4:
                result.update({
                    "action": "hold",
                    "needs_review": True,
                    "reason": "very_low_confidence",
                    "risk_level": "high",
                })
            elif confidence < 0.7:
                result["risk_level"] = "medium"

        # =====================================
        # 🧠 FUTURE READY LOGIC
        # =====================================
        if conversation_id and customer and items:
            result["explain"].append("future_ready: merge/update possible")

        # =====================================
        # 🧾 TRACE LOGGING (NEW - PRODUCTION)
        # =====================================
        log_event(
            event="decision_made",
            trace_id=trace_id,
            status=result.get("action"),
            meta={
                "decision": decision,
                "confidence": confidence,
                "warnings_count": len(warnings),
                "risk_level": result.get("risk_level")
            }
        )

        # =====================================
        # 🔍 DEBUG MODE
        # =====================================
        if SOFT_MODE:
            result["explain"].append("SOFT_MODE_ACTIVE")

        return _finalize(result, decision, confidence, warnings)

    except Exception as e:
        log_event(
            event="decision_error",
            trace_id=trace_id,
            status="error",
            meta={"error": str(e)}
        )

        print(f"❌ DECISION CRASH: {e}")

        return {
            "action": "hold",
            "needs_review": True,
            "reason": "decision_error",
            "risk_level": "high",
            "explain": [f"Decision engine failed: {str(e)}"],
            "meta": {
                "decision": "error",
                "confidence": 0,
                "warnings": []
            }
        }


# =====================================
# 🧠 FINALIZER
# =====================================
def _finalize(
    result: Dict[str, Any],
    decision: str,
    confidence: float,
    warnings: List[str],
    field_confidence: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    existing_meta = result.get("meta", {})

    result["meta"] = {
        **existing_meta,
        "decision": decision,
        "confidence": confidence,
        "warnings_count": len(warnings),
        "warnings": warnings
    }

    return result