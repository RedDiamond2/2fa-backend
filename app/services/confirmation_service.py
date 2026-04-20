# app/services/confirmation_service.py

from typing import Any, List

# =====================================
# 🧾 GENERATE CONFIRMATION MESSAGE
# =====================================
def generate_confirmation(order: Any) -> str:
    if not order:
        return ""

    items_text = format_items(order.items)
    customer_block = format_customer_info(order)
    warnings_block = format_warnings(order)

    message = f"""
🧾 *تأكيد الطلب*

{items_text}

{customer_block}

{warnings_block}

🚚 سيتم الاتصال بك لتأكيد الطلب قبل الشحن
شكراً لثقتك ❤️
""".strip()

    return message


# =====================================
# 🛒 FORMAT ITEMS
# =====================================
def format_items(items: List[Any]) -> str:
    if not items:
        return "⚠️ لا يوجد منتجات واضحة في الطلب"

    lines = []
    for item in items:
        line = f"- {safe(item.product)} × {safe(item.quantity)}"

        if getattr(item, "color", None):
            line += f" | 🎨 {item.color}"

        if getattr(item, "size", None):
            line += f" | 📏 {item.size}"

        lines.append(line)

    return "🛒 *المنتجات:*\n" + "\n".join(lines)


# =====================================
# 👤 CUSTOMER INFO
# =====================================
def format_customer_info(order: Any) -> str:
    name = safe(order.customer_name)
    phone = safe(order.phone)
    address = format_address(order)

    return f"""
👤 الاسم: {name}
📞 الهاتف: {phone}
📍 العنوان: {address}
""".strip()


# =====================================
# 📍 FORMAT ADDRESS
# =====================================
def format_address(order: Any) -> str:
    address = getattr(order, "address", None)

    if not address:
        return "⚠️ غير محدد"

    if isinstance(address, dict):
        return address.get("full") or "⚠️ ناقص"

    return str(address)


# =====================================
# ⚠️ WARNINGS BLOCK
# =====================================
def format_warnings(order: Any) -> str:
    warnings = getattr(order, "warnings", None)

    if not warnings:
        return "✅ الطلب واضح وجاهز"

    if isinstance(warnings, list):
        lines = [f"⚠️ {w}" for w in warnings]
        return "\n".join(lines)

    return f"⚠️ {warnings}"


# =====================================
# 🧼 SAFE VALUE
# =====================================
def safe(value: Any) -> str:
    if value is None:
        return "—"

    text = str(value).strip()

    if not text:
        return "—"

    return text
