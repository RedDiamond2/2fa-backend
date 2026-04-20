# app/services/action_engine.py

from typing import Dict, Any, List, Optional
from copy import deepcopy


# =====================================
# 🚀 ACTION ENGINE (PRO VERSION - REDDIAMOND)
# =====================================

def apply_action(
    decision_result: Dict[str, Any],
    parsed: Dict[str, Any],
    existing_order: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Action Engine:
    - Executes decision نتيجة decision_service
    - Handles create / hold / update / merge (future-ready)
    """

    action = decision_result.get("action")
    needs_review = decision_result.get("needs_review", False)

    result: Dict[str, Any] = {
        "status": None,        # success | hold | updated | merged
        "order": None,
        "changes": [],
        "explain": [],
    }

    # =====================================
    # 🛑 HOLD (NO EXECUTION)
    # =====================================
    if action == "hold":
        result["status"] = "hold"
        result["explain"].append("Decision = HOLD → no execution")
        return _finalize(result)

    # =====================================
    # 🆕 CREATE NEW ORDER
    # =====================================
    if action == "create" and not existing_order:

        new_order = _build_new_order(parsed)

        result["status"] = "success"
        result["order"] = new_order
        result["explain"].append("New order created")

        if needs_review:
            result["explain"].append("لكن يحتاج مراجعة")

        return _finalize(result)

    # =====================================
    # 🔄 UPDATE EXISTING ORDER
    # =====================================
    if action == "create" and existing_order:

        updated_order, changes = _update_order(existing_order, parsed)

        result["status"] = "updated"
        result["order"] = updated_order
        result["changes"] = changes
        result["explain"].append("Existing order updated")

        if not changes:
            result["explain"].append("لم يتم العثور على تغييرات")

        return _finalize(result)

    # =====================================
    # 🔀 MERGE (FUTURE - READY)
    # =====================================
    if action == "merge":
        merged_order, changes = _merge_orders(existing_order, parsed)

        result["status"] = "merged"
        result["order"] = merged_order
        result["changes"] = changes
        result["explain"].append("Orders merged")

        return _finalize(result)

    # =====================================
    # ❓ UNKNOWN ACTION
    # =====================================
    result["status"] = "hold"
    result["explain"].append("Unknown action → fallback HOLD")

    return _finalize(result)


# =====================================
# 🧱 BUILD NEW ORDER
# =====================================
def _build_new_order(parsed: Dict[str, Any]) -> Dict[str, Any]:

    return {
        "conversation_id": parsed.get("conversation_id"),
        "customer": parsed.get("customer"),
        "items": parsed.get("items", []),
        "address": parsed.get("address"),
        "phone": parsed.get("phone"),
        "status": "new",
        "meta": parsed.get("meta", {}),
    }


# =====================================
# 🔄 UPDATE ORDER (SMART PATCH)
# =====================================
def _update_order(
    existing: Dict[str, Any],
    parsed: Dict[str, Any]
) -> (Dict[str, Any], List[str]):

    updated = deepcopy(existing)
    changes: List[str] = []

    # =========================
    # 🧍 CUSTOMER UPDATE
    # =========================
    if parsed.get("customer") and parsed["customer"] != existing.get("customer"):
        updated["customer"] = parsed["customer"]
        changes.append("customer_updated")

    # =========================
    # 📞 PHONE UPDATE
    # =========================
    if parsed.get("phone") and parsed["phone"] != existing.get("phone"):
        updated["phone"] = parsed["phone"]
        changes.append("phone_updated")

    # =========================
    # 📍 ADDRESS UPDATE
    # =========================
    if parsed.get("address") and parsed["address"] != existing.get("address"):
        updated["address"] = parsed["address"]
        changes.append("address_updated")

    # =========================
    # 🛒 ITEMS UPDATE (SMART)
    # =========================
    parsed_items = parsed.get("items") or []
    existing_items = existing.get("items") or []

    if parsed_items:
        merged_items, item_changes = _merge_items(existing_items, parsed_items)
        updated["items"] = merged_items
        changes.extend(item_changes)

    return updated, changes


# =====================================
# 🛒 MERGE ITEMS (SMART LOGIC)
# =====================================
def _merge_items(
    existing_items: List[Dict],
    new_items: List[Dict]
) -> (List[Dict], List[str]):

    merged = deepcopy(existing_items)
    changes: List[str] = []

    for new_item in new_items:
        found = False

        for item in merged:
            # match by name (simple version)
            if item.get("name") == new_item.get("name"):
                found = True

                # update quantity
                if new_item.get("quantity"):
                    item["quantity"] = new_item["quantity"]
                    changes.append(f"item_quantity_updated:{item.get('name')}")

                # update variant (color/size...)
                for key in ["color", "size"]:
                    if new_item.get(key):
                        item[key] = new_item[key]
                        changes.append(f"{key}_updated:{item.get('name')}")

        if not found:
            merged.append(new_item)
            changes.append(f"item_added:{new_item.get('name')}")

    return merged, changes


# =====================================
# 🔀 MERGE ORDERS (ADVANCED - FUTURE)
# =====================================
def _merge_orders(
    existing: Dict[str, Any],
    parsed: Dict[str, Any]
) -> (Dict[str, Any], List[str]):

    merged = deepcopy(existing)
    changes: List[str] = []

    # reuse update logic
    merged, update_changes = _update_order(existing, parsed)
    changes.extend(update_changes)

    changes.append("orders_merged")

    return merged, changes


# =====================================
# 🧠 FINALIZER
# =====================================
def _finalize(result: Dict[str, Any]) -> Dict[str, Any]:

    if "order" in result and result["order"]:
        result["meta"] = {
            "items_count": len(result["order"].get("items", [])),
        }

    return result