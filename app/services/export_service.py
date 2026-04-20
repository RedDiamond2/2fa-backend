# backend/services/export_service.py

from io import BytesIO
import json
from openpyxl import Workbook

def normalize_orders(orders):
    normalized = []

    for o in orders:
        normalized.append({
            "id": o.get("id"),
            "customer_name": o.get("customer_name"),
            "phone": o.get("phone"),
            "status": o.get("status"),
            "total": (
                o.get("total_amount")
                or o.get("payment_value")
                or o.get("items_total")
                or 0
            ),
            "paid": o.get("paid_amount", 0),
            "shipping": o.get("shipping_fee", 0),
            "created_at": o.get("timestamp"),
            "items_total": o.get("items_total", 0),
        })

    return normalized


# =========================
# JSON
# =========================
def export_json(orders):
    return json.dumps(normalize_orders(orders), ensure_ascii=False)


# =========================
# EXCEL
# =========================
from openpyxl import Workbook

def export_excel(orders):
    wb = Workbook()
    ws = wb.active
    ws.title = "Orders"

    # Header
    ws.append([
        "ID",
        "Name",
        "Phone",
        "Status",
        "Total",
        "Paid",
        "Shipping",
        "Date"
    ])

    # Data
    for o in normalize_orders(orders):
        ws.append([
            o["id"],
            o["customer_name"],
            o["phone"],
            o["status"],
            o["total"],
            o["paid"],
            o["shipping"],
            o["created_at"]
        ])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

