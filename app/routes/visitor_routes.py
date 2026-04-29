# app/routes/visitor_routes.py

from fastapi import APIRouter, Request
from typing import Dict, Any
import hashlib
import json

from app.services.visitor_service import create_or_get_visitor
from app.services.geo_service import get_geo_enterprise

router = APIRouter()


def get_real_ip(request: Request) -> str:
    """استخراج IP الحقيقي من الـ headers"""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client_host = request.client.host if request.client else None
    return client_host or "0.0.0.0"


def parse_client_hints(request: Request) -> Dict[str, str]:
    return {
        "mobile": request.headers.get("sec-ch-ua-mobile", "?"),
        "platform": request.headers.get("sec-ch-ua-platform", "Unknown"),
        "brands": request.headers.get("sec-ch-ua", "Unknown"),
    }


def generate_enterprise_fingerprint(
    body: Dict[str, Any], request: Request, hints: Dict[str, str]
) -> str:
    """توليد بصمة قوية باستخدام كل العوامل الممكنة"""
    hardware_factors = {
        "screen": body.get("screen"),
        "availScreen": body.get("availScreen"),
        "devicePixelRatio": body.get("devicePixelRatio"),
        "colorDepth": body.get("colorDepth"),
        "hardwareConcurrency": body.get("hardwareConcurrency"),
        "deviceMemory": body.get("deviceMemory"),
        "platform": body.get("platform") or hints.get("platform"),
        "timezone": body.get("timezone"),
        "webgl_vendor": body.get("webgl_vendor"),
        "webgl_renderer": body.get("webgl_renderer"),
        "fonts": sorted(body.get("fonts", [])),
        "canvas_hash": body.get("canvas_hash"),
    }
    browser_factors = {
        "ua": request.headers.get("user-agent"),
        "lang": request.headers.get("accept-language"),
        "brands": hints.get("brands"),
    }
    combined = {**hardware_factors, **browser_factors}
    fingerprint_str = json.dumps(combined, sort_keys=True, default=str)
    return hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()


@router.post("/visitor/init")
async def init_visitor(request: Request, body: Dict[str, Any]):
    # 1. معلومات IP والموقع
    ip = get_real_ip(request)
    geo = await get_geo_enterprise(ip)
    hints = parse_client_hints(request)

    # 2. البصمة
    client_fingerprint = body.get("fingerprint")
    if not client_fingerprint or len(client_fingerprint) < 40:
        client_fingerprint = generate_enterprise_fingerprint(body, request, hints)

    # 3. بناء الكائن الكامل للزائر (بالشكل الذي تنتظره create_or_get_visitor)
    visitor_payload = {
        "fingerprint": client_fingerprint,
        "ip": ip,
        "user_agent": request.headers.get("user-agent"),
        "isp_org": geo.get("org"),
        "is_vpn": geo.get("is_vpn", False),
        "is_proxy": geo.get("is_proxy", False),
        "is_hosting": geo.get("is_hosting", False),
        "incognito_mode": body.get("incognito", False),
        "location": {
            "country": geo.get("country"),
            "region": geo.get("region"),
            "city": geo.get("city"),
            "lat_lon": geo.get("loc"),
            "timezone": geo.get("timezone"),
        },
        "hardware": {
            "cores": body.get("hardwareConcurrency"),
            "memory": body.get("deviceMemory"),
            "gpu": body.get("webgl_renderer"),
            "platform": body.get("platform"),
            "screen": body.get("screen"),
            "pixel_ratio": body.get("devicePixelRatio"),
            "color_depth": body.get("colorDepth"),
        },
        "raw_fp": body,  # حفظ كل البيانات الخام التي أرسلها العميل
    }

    # 4. استدعاء الخدمة الموحدة (تتعامل مع الإدراج أو التحديث)
    result = await create_or_get_visitor(visitor_payload)

    # 5. إعادة النتيجة مع بيانات الزائر كاملة
    if result.get("status") == "invalid":
        return {"success": False, "reason": result.get("reason")}

    # تأكد من وجود _id كسلسلة نصية
    visitor_data = result.copy()
    if "_id" in visitor_data and not isinstance(visitor_data["_id"], str):
        visitor_data["_id"] = str(visitor_data["_id"])

    return {
        "success": True,
        "visitor": visitor_data,
        "meta": {
            "ip": ip,
            "geo_mode": "internal",
        },
    }
