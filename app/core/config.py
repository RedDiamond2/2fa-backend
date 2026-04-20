# app/core/config.py

import os
import logging
from dotenv import load_dotenv

# =========================================
# 🔹 LOAD ENV
# =========================================
load_dotenv()

# =========================================
# 🔹 LOGGING CONFIG (CLEAN + CONTROLLED)
# =========================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        # logging.FileHandler("logs/app.log") if os.path.exists("logs") else logging.StreamHandler()
    ]
)

# 🔥 IMPORTANT: Kill pymongo spam completely
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pymongo.topology").setLevel(logging.ERROR)
logging.getLogger("pymongo.connection").setLevel(logging.ERROR)
logging.getLogger("pymongo.serverSelection").setLevel(logging.ERROR)

# =========================================
# 🔹 SETTINGS CLASS
# =========================================

class Settings:
    # ================================
    # APP
    # ================================
    APP_NAME: str = os.getenv("APP_NAME", "CRM MVP")
    VERSION: str = os.getenv("VERSION", "1.0.0")
    ENV: str = os.getenv("ENV", "dev")
    DEBUG: bool = ENV == "dev"

    # ================================
    # DATABASE
    # ================================
    MONGO_URL: str = os.getenv("MONGO_URI", "")
    DB_NAME: str = os.getenv("DB_NAME", "crm_db")

    # ================================
    # REDIS (مستقبلاً)
    # ================================
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))

    # ================================
    # SYSTEM LIMITS
    # ================================
    MAX_HISTORY: int = int(os.getenv("MAX_HISTORY", 20))

    # ================================
    # SECURITY (admin tools)
    # ================================
    ADMIN_SECRET: str = os.getenv("ADMIN_SECRET", "1234")

    # ================================
    # VALIDATION
    # ================================
    def validate(self):
        if not self.MONGO_URL:
            raise ValueError("❌ MONGO_URI is missing in .env")

# =========================================
# 🔹 INSTANCE
# =========================================

settings = Settings()

# 🔥 Validate at startup (fail fast)
try:
    settings.validate()
except Exception as e:
    logging.error(str(e))