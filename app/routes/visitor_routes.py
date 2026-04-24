# app/routes/visitor_routes.py

from fastapi import APIRouter, Request
from app.services.visitor_service import create_or_get_visitor
import httpx


router = APIRouter()


def get_client_ip(request: Request):
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0]
    return request.client.host


async def get_geo(ip):
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:  # ✅ stability
            res = await client.get(f"http://ip-api.com/json/{ip}")
            return res.json()
    except:
        return {}


@router.post("/visitor/init")
async def init_visitor(request: Request, body: dict):
    ip = get_client_ip(request)
    geo = await get_geo(ip)

    visitor_data = {
        "fingerprint": body.get("fingerprint"),
        "user_agent": request.headers.get("user-agent"),
        "ip": ip,
        "screen": body.get("screen"),
        "platform": body.get("platform"),
        "language": body.get("language"),
        "country": geo.get("country") or "Unknown",
        "region": geo.get("regionName") or "Unknown",
        "city": geo.get("city") or "Unknown",
    }

    visitor = await create_or_get_visitor(visitor_data)

    # ✅ SAFE _id handling
    if visitor and "_id" in visitor:
        visitor["_id"] = str(visitor["_id"])

    return {"success": True, "visitor": visitor}
