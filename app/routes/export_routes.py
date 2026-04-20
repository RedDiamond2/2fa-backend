from fastapi import APIRouter
from fastapi.responses import StreamingResponse, Response
from app.services.export_service import export_json, export_excel
from app.core.database import db

router = APIRouter()


def format_order(o):
    items_text = ", ".join([
        f"{i.get('product')} x{i.get('quantity')}"
        for i in o.get("items", [])
    ])

    total = o.get("total_amount", 0)
    paid = o.get("paid_amount", 0)
    shipping = o.get("shipping_fee", 0)

    return {
        "name": o.get("customer_name"),
        "phone": o.get("phone"),
        "status": o.get("order_stage"),
        "items": items_text,
        "items_total": o.get("items_total", 0),
        "shipping": shipping,
        "total": total,
        "paid": paid,
        "remaining": max(total - paid, 0),
        "date": o.get("timestamp", "")[:10]
    }


@router.get("/export")
async def export_data(format: str = "json"):

    # ✅ الصحيح
    orders = list(db["orders"].find({}))

    # ✅ تحويل ObjectId
    for o in orders:
        o["_id"] = str(o["_id"])

    formatted = [format_order(o) for o in orders]

    # ✅ JSON
    if format == "json":
        return Response(
            content=export_json(formatted),
            media_type="application/json"
        )

    # ✅ Excel
    if format == "excel":
        file = export_excel(formatted)
        return StreamingResponse(
            file,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    return {"error": "Invalid format"}