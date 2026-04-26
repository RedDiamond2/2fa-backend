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
        strategy: str = "smart",
    ) -> MergeResult:
        """
        Merge new parsed data into an existing order.

        strategy:
            - smart (default)
            - overwrite
            - fill_missing
        """

        existing = deepcopy(existing_order or {})
        incoming = deepcopy(new_data or {})

        merged = deepcopy(existing)
        conflicts: Dict[str, Any] = {}
        updated_fields: List[str] = []

        # --- BASIC FIELDS ---
        basic_fields = ["customer_name", "phone", "address", "location"]

        for field in basic_fields:
            result = self._merge_field(
                existing.get(field),
                incoming.get(field),
                strategy=strategy,
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
            strategy=strategy,
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
            is_merged=len(updated_fields) > 0,
        )

    # ==============================
    # FIELD MERGE
    # ==============================
    def _merge_field(
        self,
        old_value: Any,
        new_value: Any,
        strategy: str,
    ) -> Dict[str, Any]:
        if new_value in [None, "", [], {}]:
            return {"value": old_value, "updated": False, "conflict": None}

        if old_value in [None, "", [], {}]:
            return {"value": new_value, "updated": True, "conflict": None}

        if str(old_value).strip() == str(new_value).strip():
            return {"value": old_value, "updated": False, "conflict": None}

        if strategy == "overwrite":
            return {"value": new_value, "updated": True, "conflict": None}

        if strategy == "fill_missing":
            return {"value": old_value, "updated": False, "conflict": None}

        if self._is_better_value(old_value, new_value):
            return {"value": new_value, "updated": True, "conflict": None}

        return {
            "value": old_value,
            "updated": False,
            "conflict": {
                "old": old_value,
                "new": new_value,
            },
        }

    # ==============================
    # ITEMS MERGE (DEDUP SAFE)
    # ==============================
    def _merge_items(
        self,
        old_items: List[Dict[str, Any]],
        new_items: List[Dict[str, Any]],
        strategy: str,
    ) -> Dict[str, Any]:
        old_items = [i for i in (old_items or []) if isinstance(i, dict)]
        new_items = [i for i in (new_items or []) if isinstance(i, dict)]

        if not new_items:
            return {
                "items": self._dedupe_items(old_items),
                "updated": False,
                "conflicts": [],
            }

        merged_items = deepcopy(old_items)
        conflicts: List[Any] = []
        updated = False

        for new_item in new_items:
            if not new_item.get("product") and not new_item.get("name"):
                continue

            match = self._find_matching_item(merged_items, new_item)

            if not match:
                merged_items.append(deepcopy(new_item))
                updated = True
                continue

            merge_result = self._merge_single_item(match, new_item, strategy)

            if merge_result["updated"]:
                updated = True

            if merge_result["conflict"]:
                conflicts.append(merge_result["conflict"])

        merged_items = self._dedupe_items(merged_items)

        return {
            "items": merged_items,
            "updated": updated,
            "conflicts": conflicts,
        }

    # ==============================
    # SINGLE ITEM MERGE
    # ==============================
    def _merge_single_item(
        self,
        old_item: Dict[str, Any],
        new_item: Dict[str, Any],
        strategy: str,
    ) -> Dict[str, Any]:
        conflict = None
        updated = False

        # QUANTITY
        old_qty = old_item.get("quantity")
        new_qty = new_item.get("quantity")

        if new_qty not in [None, ""]:
            try:
                new_qty = int(new_qty)
            except (TypeError, ValueError):
                new_qty = old_qty

            if old_qty != new_qty:
                if strategy == "overwrite" or (
                    isinstance(new_qty, int)
                    and isinstance(old_qty, int)
                    and new_qty > old_qty
                ):
                    old_item["quantity"] = new_qty
                    updated = True
                else:
                    conflict = {
                        "type": "quantity_conflict",
                        "old": old_qty,
                        "new": new_qty,
                        "product": old_item.get("name") or old_item.get("product"),
                    }

        # VARIANTS (size, color)
        for key in ["size", "color"]:
            old_val = old_item.get(key)
            new_val = new_item.get(key)

            if new_val not in [None, ""] and old_val != new_val:
                if strategy == "overwrite":
                    old_item[key] = new_val
                    updated = True
                else:
                    if conflict is None:
                        conflict = {
                            "type": f"{key}_conflict",
                            "old": old_val,
                            "new": new_val,
                            "product": old_item.get("name") or old_item.get("product"),
                        }

        return {
            "updated": updated,
            "conflict": conflict,
        }

    # ==============================
    # MATCHING LOGIC
    # ==============================
    def _find_matching_item(
        self,
        items: List[Dict[str, Any]],
        new_item: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        for item in items:
            if self._is_same_product(item, new_item):
                return item

        return None

    def _is_same_product(
        self,
        item1: Dict[str, Any],
        item2: Dict[str, Any],
    ) -> bool:
        product1 = self._safe_text(item1.get("product") or item1.get("name"))
        product2 = self._safe_text(item2.get("product") or item2.get("name"))

        if not product1 or not product2:
            return False

        if product1 != product2:
            return False

        color1 = self._safe_text(item1.get("color"))
        color2 = self._safe_text(item2.get("color"))
        size1 = self._safe_text(item1.get("size"))
        size2 = self._safe_text(item2.get("size"))

        return color1 == color2 and size1 == size2

    # ==============================
    # SMART VALUE DETECTION
    # ==============================
    def _is_better_value(self, old: Any, new: Any) -> bool:
        """
        Decide if new value is better than old value.
        """

        if old in [None, "", [], {}]:
            return True

        if new in [None, "", [], {}]:
            return False

        if isinstance(old, str) and isinstance(new, str):
            return len(new.strip()) > len(old.strip())

        return False

    # ==============================
    # DEDUP
    # ==============================
    def _dedupe_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        result = []

        for item in items:
            if not isinstance(item, dict):
                continue

            key = (
                self._safe_text(item.get("product") or item.get("name")),
                self._safe_text(item.get("color")),
                self._safe_text(item.get("size")),
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(item)

        return result

    def _safe_text(self, value: Any) -> str:
        return str(value).strip().lower() if value is not None else ""


# Singleton
merge_service = MergeService()
