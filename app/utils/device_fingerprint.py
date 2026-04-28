# app/utils/device_fingerprint.py

import hashlib
import json


def build_device_hash(data: dict) -> str:
    base = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(base.encode()).hexdigest()
