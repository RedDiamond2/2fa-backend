# app/services/geo_service.py

import os
from typing import Dict, Any

# حاول استيراد geoip2 إذا كان موجودًا
try:
    import geoip2.database

    GEOIP_AVAILABLE = True
except ImportError:
    GEOIP_AVAILABLE = False

# حاول استيراد IP2Proxy (اختياري)
try:
    import ip2proxy

    IP2PROXY_AVAILABLE = True
except ImportError:
    IP2PROXY_AVAILABLE = False

# المسارات إلى قواعد البيانات (ضع ملفات الـ .mmdb أو .bin في المجلد المناسب)
GEO_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "geo", "GeoLite2-City.mmdb")
PROXY_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "geo", "IP2Proxy-LITE-PX11.BIN"
)

geo_reader = None
proxy_reader = None


def init_geo_reader():
    global geo_reader
    if geo_reader is None and GEOIP_AVAILABLE:
        try:
            geo_reader = geoip2.database.Reader(GEO_DB_PATH)
        except Exception:
            geo_reader = None


def init_proxy_reader():
    global proxy_reader
    if proxy_reader is None and IP2PROXY_AVAILABLE and os.path.exists(PROXY_DB_PATH):
        try:
            proxy_reader = ip2proxy.IP2Proxy()
            proxy_reader.open(PROXY_DB_PATH)
        except Exception:
            proxy_reader = None


async def get_geo_enterprise(ip: str) -> Dict[str, Any]:
    """
    إرجاع معلومات جغرافية وأمان عن الـ IP
    المخرجات:
        country, region, city, loc (lat,lng), timezone, org,
        is_vpn, is_proxy, is_hosting
    """
    init_geo_reader()
    init_proxy_reader()

    # الحالات الخاصة (local)
    if (
        ip.startswith("127.")
        or ip == "::1"
        or ip.startswith("192.168.")
        or ip.startswith("10.")
    ):
        return {
            "country": "Local",
            "region": "Local",
            "city": "Local",
            "loc": "0,0",
            "timezone": "UTC",
            "org": "Local Network",
            "is_vpn": False,
            "is_proxy": False,
            "is_hosting": False,
        }

    # بيانات الموقع من GeoIP2 (إن وجدت)
    geo_data = {
        "country": None,
        "region": None,
        "city": None,
        "loc": None,
        "timezone": None,
        "org": None,
    }

    if geo_reader:
        try:
            response = geo_reader.city(ip)
            geo_data["country"] = response.country.name
            geo_data["region"] = response.subdivisions.most_specific.name
            geo_data["city"] = response.city.name
            if response.location.latitude and response.location.longitude:
                geo_data["loc"] = (
                    f"{response.location.latitude},{response.location.longitude}"
                )
            geo_data["timezone"] = response.location.time_zone
            # ISP / Organization (قد لا يكون موجودًا في GeoLite2-City، نتركه None ثم نملأه لاحقًا)
        except Exception:
            pass

    # بيانات الأمان من IP2Proxy (إن وجدت)
    proxy_data = {
        "is_vpn": False,
        "is_proxy": False,
        "is_hosting": False,
    }
    if proxy_reader:
        try:
            result = proxy_reader.get_all(ip)
            # حسب وثائق ip2proxy: result['is_proxy'] = 0/1
            if result:
                proxy_data["is_proxy"] = bool(result.get("is_proxy", 0))
                proxy_data["is_vpn"] = bool(result.get("is_vpn", 0))
                proxy_data["is_hosting"] = bool(result.get("is_hosting", 0))
                # يمكن استخراج الـ ISP من same file
                if not geo_data.get("org") and result.get("isp"):
                    geo_data["org"] = result.get("isp")
        except Exception:
            pass

    # تعبئة القيم المفقودة بقيم افتراضية
    return {
        "country": geo_data["country"] or "Unknown",
        "region": geo_data["region"] or "Unknown",
        "city": geo_data["city"] or "Unknown",
        "loc": geo_data["loc"] or "0,0",
        "timezone": geo_data["timezone"] or "UTC",
        "org": geo_data["org"] or "Unknown ISP",
        **proxy_data,
    }
