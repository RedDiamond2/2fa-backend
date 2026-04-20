# app/services/merge_service.py

from typing import Dict, Any, Optional, List
from copy import deepcopy
from datetime import datetime


class MergeResult:
    def __init__(
        self,
        merged: Dict[str, Any],
        conflicts: Dict[str, Any],
        updated_fields: List[str],
        is_merged: bool,
    ):
        self.merged = merged
        self.conflicts = conflicts
        self.updated_fields = updated_fields
        self.is_merged = is_merged


class MergeService:

    # ==============================
    # MAIN MERGE ENTRY
    # ==============================
    def merge_orders(
        self,
        existing_order: Dict[str, Any],
        new_data: Dict[str, Any],
        strategy: str = "smart"
    ) -> MergeResult:
        """
        Merge new parsed data into an existing order.

        strategy:
            - smart (default)
            - overwrite
            - fill_missing
        """

        existing = deepcopy(existing_order)
        incoming = deepcopy(new_data)

        merged = deepcopy(existing)
        conflicts = {}
        updated_fields = []

        # --- BASIC FIELDS ---
        basic_fields = ["customer_name", "phone", "address"]

        for field in basic_fields:
            result = self._merge_field(
                existing.get(field),
                incoming.get(field),
                strategy=strategy
            )

            if result["updated"]:
                merged[field] = result["value"]
                updated_fields.append(field)

            if result["conflict"]:
                conflicts[field] = result["conflict"]

        # --- ITEMS ---
        items_result = self._merge_items(
            existing.get("items", []),
            incoming.get("items", []),
            strategy=strategy
        )

        merged["items"] = items_result["items"]

        if items_result["updated"]:
            updated_fields.append("items")

        if items_result["conflicts"]:
            conflicts["items"] = items_result["conflicts"]

        # --- META ---
        merged["updated_at"] = datetime.utcnow().isoformat()

        return MergeResult(
            merged=merged,
            conflicts=conflicts,
            updated_fields=updated_fields,
            is_merged=len(updated_fields) > 0
        )

    # ==============================
    # FIELD MERGE
    # ==============================
    def _merge_field(
        self,
        old_value: Any,
        new_value: Any,
        strategy: str
    ) -> Dict[str, Any]:

        if not new_value:
            return {"value": old_value, "updated": False, "conflict": None}

        if not old_value:
            return {"value": new_value, "updated": True, "conflict": None}

        # SAME VALUE
        if str(old_value).strip() == str(new_value).strip():
            return {"value": old_value, "updated": False, "conflict": None}

        # STRATEGIES
        if strategy == "overwrite":
            return {"value": new_value, "updated": True, "conflict": None}

        if strategy == "fill_missing":
            return {"value": old_value, "updated": False, "conflict": None}

        # SMART STRATEGY
        # detect better value
        if self._is_better_value(old_value, new_value):
            return {"value": new_value, "updated": True, "conflict": None}

        # CONFLICT
        return {
            "value": old_value,
            "updated": False,
            "conflict": {
                "old": old_value,
                "new": new_value
            }
        }

    # ==============================
    # ITEMS MERGE (CRITICAL)
    # ==============================
    def _merge_items(
        self,
        old_items: List[Dict[str, Any]],
        new_items: List[Dict[str, Any]],
        strategy: str
    ) -> Dict[str, Any]:

        if not new_items:
            return {
                "items": old_items,
                "updated": False,
                "conflicts": []
            }

        merged_items = deepcopy(old_items)
        conflicts = []
        updated = False

        for new_item in new_items:
            match = self._find_matching_item(merged_items, new_item)

            if not match:
                # NEW ITEM
                merged_items.append(new_item)
                updated = True
                continue

            # MERGE EXISTING ITEM
            merge_result = self._merge_single_item(match, new_item, strategy)

            if merge_result["updated"]:
                updated = True

            if merge_result["conflict"]:
                conflicts.append(merge_result["conflict"])

        return {
            "items": merged_items,
            "updated": updated,
            "conflicts": conflicts
        }

    # ==============================
    # SINGLE ITEM MERGE
    # ==============================
    def _merge_single_item(
        self,
        old_item: Dict[str, Any],
        new_item: Dict[str, Any],
        strategy: str
    ) -> Dict[str, Any]:

        conflict = None
        updated = False

        # QUANTITY
        old_qty = old_item.get("quantity")
        new_qty = new_item.get("quantity")

        if new_qty and old_qty != new_qty:
            if strategy == "overwrite" or new_qty > old_qty:
                old_item["quantity"] = new_qty
                updated = True
            else:
                conflict = {
                    "type": "quantity_conflict",
                    "old": old_qty,
                    "new": new_qty,
                    "product": old_item.get("name")
                }

        # VARIANTS (size, color...)
        for key in ["size", "color"]:
            old_val = old_item.get(key)
            new_val = new_item.get(key)

            if new_val and old_val != new_val:
                if strategy == "overwrite":
                    old_item[key] = new_val
                    updated = True
                else:
                    conflict = {
                        "type": f"{key}_conflict",
                        "old": old_val,
                        "new": new_val,
                        "product": old_item.get("name")
                    }

        return {
            "updated": updated,
            "conflict": conflict
        }

    # ==============================
    # MATCHING LOGIC
    # ==============================
    def _find_matching_item(
        self,
        items: List[Dict[str, Any]],
        new_item: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:

        for item in items:
            if self._is_same_product(item, new_item):
                return item

        return None

    def _is_same_product(
        self,
        item1: Dict[str, Any],
        item2: Dict[str, Any]
    ) -> bool:

        name1 = (item1.get("name") or "").lower().strip()
        name2 = (item2.get("name") or "").lower().strip()

        return name1 == name2

    # ==============================
    # SMART VALUE DETECTION
    # ==============================
    def _is_better_value(self, old: Any, new: Any) -> bool:
        """
        Decide if new value is better than old value.
        """

        if not old:
            return True

        if not new:
            return False

        # LONGER = better (addresses, names)
        if isinstance(old, str) and isinstance(new, str):
            return len(new) > len(old)

        return False


# Singleton
merge_service = MergeService()