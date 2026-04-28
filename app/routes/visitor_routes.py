# app/routes/visitor_routes.py

from fastapi import APIRouter, Request
from typing import Dict
from datetime import datetime
import hashlib
import json

from app.services.visitor_service import create_or_get_visitor
from app.core.database import db
from app.services.geo_service import get_geo_enterprise

router = APIRouter()


# ==========================================
# 🔐 IP REAL DETECTION (بديل ipinfo.io)
# ==========================================


def get_real_ip(request: Request) -> str:
    """استخراج IP الحقيقي بدون أي API خارجي"""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.client.host


# ==========================================
# 🧠 CLIENT HINTS
# ==========================================


def parse_client_hints(request: Request) -> Dict[str, str]:
    return {
        "mobile": request.headers.get("sec-ch-ua-mobile", "?"),
        "platform": request.headers.get("sec-ch-ua-platform", "Unknown"),
        "brands": request.headers.get("sec-ch-ua", "Unknown"),
    }


# ==========================================
# 🧬 FINGERPRINT ENGINE
# ==========================================


def generate_enterprise_fingerprint(body: dict, request: Request, hints: dict) -> str:
    hardware_factors = {
        "screen": body.get("screen"),
        "availScreen": body.get("availScreen"),
        "devicePixelRatio": body.get("devicePixelRatio"),
        "colorDepth": body.get("colorDepth"),
        "hardwareConcurrency": body.get("hardwareConcurrency"),
        "deviceMemory": body.get("deviceMemory"),
        "cpuClass": body.get("cpuClass"),
        "platform": body.get("platform") or hints.get("platform"),
        "timezone": body.get("timezone"),
        "webgl_vendor": body.get("webgl_vendor"),
        "webgl_renderer": body.get("webgl_renderer"),
        "audio_hash": body.get("audio_hash"),
        "fonts": sorted(body.get("fonts", [])),
    }

    browser_factors = {
        "ua": request.headers.get("user-agent"),
        "lang": request.headers.get("accept-language"),
        "brands": hints.get("brands"),
    }

    combined = {**hardware_factors, **browser_factors}

    fingerprint_str = json.dumps(combined, sort_keys=True, default=str)
    return hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()


# ==========================================
# 🚀 MAIN ROUTE
# ==========================================


@router.post("/visitor/init")
async def init_visitor(request: Request, body: dict):
    ip = get_real_ip(request)
    geo = await get_geo_enterprise(ip)
    hints = parse_client_hints(request)

    # ================================
    # fingerprint generation
    # ================================
    fingerprint = body.get("fingerprint")
    if not fingerprint or len(fingerprint) < 40:
        fingerprint = generate_enterprise_fingerprint(body, request, hints)

    # ================================
    # visitor record
    # ================================
    visitor_data = {
        "fingerprint": fingerprint,
        "user_agent": request.headers.get("user-agent"),
        "ip": ip,
        # security signals
        "is_vpn": geo["is_vpn"],
        "is_proxy": geo["is_proxy"],
        "is_hosting": geo["is_hosting"],
        "isp_org": geo["org"],
        # hardware
        "hardware": {
            "cores": body.get("hardwareConcurrency"),
            "memory": body.get("deviceMemory"),
            "gpu": body.get("webgl_renderer"),
            "platform": body.get("platform"),
            "screen": body.get("screen"),
            "pixel_ratio": body.get("devicePixelRatio"),
            "color_depth": body.get("colorDepth"),
        },
        # location
        "location": {
            "country": geo["country"],
            "region": geo["region"],
            "city": geo["city"],
            "lat_lon": geo["loc"],
            "timezone": geo["timezone"],
        },
        "raw_fp": body,
        "first_seen": datetime.utcnow(),
        "last_seen": datetime.utcnow(),
        "visit_count": 1,
        "incognito_mode": body.get("incognito", False),
    }

    # ================================
    # existing visitor
    # ================================
    existing = await db["visitors"].find_one({"fingerprint": fingerprint})

    if existing:
        await db["visitors"].update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "last_seen": datetime.utcnow(),
                    "ip": ip,
                    "location": visitor_data["location"],
                },
                "$inc": {"visit_count": 1},
            },
        )

        visitor_data = existing
        visitor_data["_id"] = str(visitor_data["_id"])

    else:
        visitor = await create_or_get_visitor(visitor_data)
        visitor_data = visitor
        if visitor_data and "_id" in visitor_data:
            visitor_data["_id"] = str(visitor_data["_id"])

    return {
        "success": True,
        "visitor": visitor_data,
        "meta": {
            "ip": ip,
            "geo_mode": "internal",
        },
    }
