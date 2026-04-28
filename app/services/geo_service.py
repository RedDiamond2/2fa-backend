# app/services/geo_service.py

import geoip2.database
import os

GEO_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "geo", "GeoLite2-City.mmdb")

reader = None


def init_geo_reader():
    global reader
    if reader is None:
        reader = geoip2.database.Reader(GEO_DB_PATH)


# =========================================
# 🌍 GEO ENTERPRISE FUNCTION
# =========================================


async def get_geo_enterprise(ip: str):
    init_geo_reader()

    # =========================
    # LOCAL IP
    # =========================
    if ip.startswith("127.") or ip == "::1":
        return {
            "country": "Local",
            "region": "Local",
            "city": "Local",
            "loc": "0,0",
            "timezone": "UTC",
            "org": "Local",
            "is_vpn": False,
            "is_proxy": False,
            "is_hosting": False,
        }

    # =========================
    # REAL GEO LOOKUP
    # =========================
    try:
        response = reader.city(ip)

        return {
            "country": response.country.name or "Unknown",
            "region": response.subdivisions.most_specific.name or "Unknown",
            "city": response.city.name or "Unknown",
            "loc": f"{response.location.latitude},{response.location.longitude}",
            "timezone": response.location.time_zone or "UTC",
            "org": "Detected ISP",
            "is_vpn": False,
            "is_proxy": False,
            "is_hosting": False,
        }

    except Exception:
        return {
            "country": "Unknown",
            "region": "Unknown",
            "city": "Unknown",
            "loc": "0,0",
            "timezone": "UTC",
            "org": "Unknown ISP",
            "is_vpn": False,
            "is_proxy": False,
            "is_hosting": False,
        }
