# app/services/action_engine.py

from typing import Dict, Any, Optional
from app.services.usage_service import log_event
from .action_engine_core import _build_new_order, _update_order, _merge_orders


# =====================================
# ⚙️ CONFIG
# =====================================
STRICT_MODE = False


# =====================================
# 🚀 ACTION ENGINE (DECOUPLED - PRO)
# =====================================
def apply_action(
    decision_result: Dict[str, Any],
    parsed: Dict[str, Any],
    existing_order: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    action = decision_result.get("action")
    needs_review = decision_result.get("needs_review", False)

    result: Dict[str, Any] = {
        "status": None,
        "order": None,
        "changes": [],
        "explain": ["action_engine_v3"],
        "meta": {},
    }

    try:
        # =========================
        # 🛑 HOLD
        # =========================
        if action == "hold":
            result["status"] = "hold"
            result["explain"].append("HOLD → no execution")
            _log("action_hold", trace_id, decision_result)
            return _finalize(result)

        # =========================
        # 🆕 CREATE
        # =========================
        if action == "create" and not existing_order:
            if STRICT_MODE and needs_review:
                result["status"] = "hold"
                result["explain"].append("STRICT_MODE blocked create")
                return _finalize(result)

            new_order = _build_new_order(parsed)

            result["status"] = "success"
            result["order"] = new_order
            result["explain"].append("order_created")

            if needs_review:
                result["explain"].append("needs_review=true")

            _log("action_create", trace_id, decision_result)
            return _finalize(result)

        # =========================
        # 🔄 UPDATE
        # =========================
        if action == "create" and existing_order:
            updated_order, changes = _update_order(existing_order, parsed)

            result["status"] = "updated"
            result["order"] = updated_order
            result["changes"] = changes
            result["explain"].append("order_updated")

            if not changes:
                result["explain"].append("no_changes")

            _log("action_update", trace_id, decision_result)
            return _finalize(result)

        # =========================
        # 🔀 MERGE
        # =========================
        if action == "merge":
            merged_order, changes = _merge_orders(existing_order, parsed)

            result["status"] = "merged"
            result["order"] = merged_order
            result["changes"] = changes
            result["explain"].append("orders_merged")

            _log("action_merge", trace_id, decision_result)
            return _finalize(result)

        # =========================
        # ❓ UNKNOWN
        # =========================
        result["status"] = "hold"
        result["explain"].append("unknown_action_fallback")

        _log("action_unknown", trace_id, decision_result)
        return _finalize(result)

    except Exception as e:
        _log("action_error", trace_id, {"error": str(e)})

        return {
            "status": "error",
            "order": None,
            "changes": [],
            "explain": [f"action_engine_error:{str(e)}"],
            "meta": {},
        }


# =====================================
#  LOGGER
# =====================================
def _log(event: str, trace_id: Optional[str], meta: Dict[str, Any]):
    try:
        log_event(event=event, trace_id=trace_id, status="ok", meta=meta)
    except Exception:
        pass


# =====================================
# 🧠 FINALIZER
# =====================================
def _finalize(result: Dict[str, Any]) -> Dict[str, Any]:
    if result.get("order"):
        result["meta"] = {
            "items_count": len(result["order"].get("items", [])),
            "engine": "action_engine_v3",
        }
    return result
