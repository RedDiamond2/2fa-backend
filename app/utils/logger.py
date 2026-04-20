# app/utils/logger.py
import json
import datetime
import logging
from typing import Any

logger = logging.getLogger("utils_logger")


def _safe_serialize(data: Any):
    """
    تحويل أي data إلى JSON بشكل آمن (بدون crash)
    """
    try:
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return str(data)


def _timestamp():
    """
    إرجاع توقيت واضح
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_step(title: str, data: Any):
    """
    🔥 Logging أساسي لعرض البيانات بشكل واضح في Terminal
    """
    print("\n" + "=" * 60)
    print(f"🔥 [{_timestamp()}] {title}")
    print("-" * 60)
    print(_safe_serialize(data))
    print("=" * 60 + "\n")


def log_info(message: str):
    """
    ℹ️ معلومات عامة
    """
    print(f"ℹ️  [{_timestamp()}] {message}")


def log_warning(message: str):
    """
    ⚠️ تحذير
    """
    print(f"⚠️  [{_timestamp()}] {message}")


def log_error(message: str, error: Any = None):
    """
    ❌ أخطاء
    """
    print("\n" + "❌" * 20)
    print(f"❌ [{_timestamp()}] ERROR: {message}")
    if error:
        print(f"DETAILS: {error}")
    print("❌" * 20 + "\n")


def log_success(message: str, data: Any = None):
    """
    ✅ نجاح العمليات
    """
    print("\n" + "✅" * 20)
    print(f"✅ [{_timestamp()}] SUCCESS: {message}")
    if data is not None:
        print(_safe_serialize(data))
    print("✅" * 20 + "\n")