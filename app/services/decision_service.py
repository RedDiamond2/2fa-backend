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
def apply_decision(
    parsed: Dict[str, Any], trace_id: Optional[str] = None
) -> Dict[str, Any]:
    try:
        meta: Dict = parsed.get("meta") or {}

        decision: str = meta.get("decision") or "manual"
        decision = decision.lower() if isinstance(decision, str) else "manual"

        confidence: float = meta.get("confidence") or 0.0

        warnings: List[str] = meta.get("warnings") or []
        if not isinstance(warnings, list):
            warnings = []

        conversation_id = parsed.get("conversation_id")
        customer = parsed.get("customer") or parsed.get("customer_name")
        items = parsed.get("items") or []

        # =====================================
        # 🧱 BASE RESULT
        # =====================================
        result: Dict[str, Any] = {
            "action": None,
            "needs_review": False,
            "reason": None,
            "risk_level": "low",
            "explain": ["decision_engine_v4"],
            "meta": {},
        }

        # =====================================
        # 🚨 BLOCKING (CRITICAL)
        # =====================================
        blocking_warnings = {"no_items", "missing_phone"}

        if any(w in blocking_warnings for w in warnings):
            result.update(
                {
                    "action": "hold",
                    "needs_review": True,
                    "reason": "critical_missing_data",
                    "risk_level": "high",
                }
            )
            result["explain"].append("blocked_missing_fields")
            return _finalize(result, decision, confidence, warnings, meta)

        # =====================================
        # ⚠️ HIGH RISK
        # =====================================
        high_risk_warnings = {"invalid_phone", "invalid_quantity", "duplicate_item"}

        if any(w in high_risk_warnings for w in warnings):
            decision = "review"
            result["risk_level"] = "high"
            result["explain"].append("high_risk_forced_review")

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
            result.update(
                {
                    "action": "hold",
                    "needs_review": True,
                    "reason": "unknown_decision",
                    "risk_level": "high",
                }
            )
            result["explain"].append("unknown_decision_type")

        # =====================================
        # 📊 CONFIDENCE ENGINE
        # =====================================
        if SOFT_MODE:
            if confidence < 0.2:
                result.update(
                    {
                        "action": "hold",
                        "needs_review": True,
                        "reason": "extremely_low_confidence",
                        "risk_level": "high",
                    }
                )
                result["explain"].append("blocked_low_confidence")

            elif result["action"] == "create":
                result["needs_review"] = False
                result["reason"] = "soft_auto_success"
                result["risk_level"] = "low"

        else:
            if confidence < 0.4:
                result.update(
                    {
                        "action": "hold",
                        "needs_review": True,
                        "reason": "very_low_confidence",
                        "risk_level": "high",
                    }
                )
            elif confidence < 0.7:
                result["risk_level"] = "medium"

        # =====================================
        # 🧠 FUTURE READY
        # =====================================
        if conversation_id and customer and items:
            result["explain"].append("future_ready_merge_possible")

        # =====================================
        # 🧾 LOGGING
        # =====================================
        _log(
            trace_id,
            {
                "event": "decision_made",
                "action": result.get("action"),
                "confidence": confidence,
                "risk": result.get("risk_level"),
                "warnings": len(warnings),
            },
        )

        if SOFT_MODE:
            result["explain"].append("soft_mode_active")

        return _finalize(result, decision, confidence, warnings, meta)

    except Exception as e:
        _log(trace_id, {"event": "decision_error", "error": str(e)})

        return {
            "action": "hold",
            "needs_review": True,
            "reason": "decision_error",
            "risk_level": "high",
            "explain": [f"engine_error:{str(e)}"],
            "meta": {"decision": "error", "confidence": 0, "warnings": []},
        }


# =====================================
# 🧠 FINALIZER
# =====================================
def _finalize(
    result: Dict[str, Any],
    decision: str,
    confidence: float,
    warnings: List[str],
    field_confidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    existing_meta = result.get("meta", {}) or {}

    result["meta"] = {
        **existing_meta,
        "decision": decision,
        "confidence": confidence,
        "warnings_count": len(warnings),
        "warnings": warnings,
        "field_confidence": field_confidence
        or existing_meta.get("field_confidence", {}),
    }

    return result


# =====================================
# 🧾 LOGGER
# =====================================
def _log(trace_id: Optional[str], meta: Dict[str, Any]):
    try:
        log_event(
            event=meta.get("event", "decision_log"),
            trace_id=trace_id,
            status="ok",
            meta=meta,
        )
    except Exception:
        pass
