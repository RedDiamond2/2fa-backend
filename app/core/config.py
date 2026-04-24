# app/core/config.py

import os
import logging
from dotenv import load_dotenv

# =========================================
# LOAD ENV
# =========================================

load_dotenv()

# =========================================
# LOGGING SETUP (CLEAN + CONTROLLED)
# =========================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

# silence noisy drivers
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pymongo.topology").setLevel(logging.ERROR)
logging.getLogger("pymongo.connection").setLevel(logging.ERROR)
logging.getLogger("pymongo.serverSelection").setLevel(logging.ERROR)


# =========================================
# SETTINGS CLASS
# =========================================


class Settings:
    # -------------------------
    # APP
    # -------------------------
    APP_NAME: str = os.getenv("APP_NAME", "CRM MVP")
    VERSION: str = os.getenv("VERSION", "1.0.0")
    ENV: str = os.getenv("ENV", "dev")
    DEBUG: bool = ENV == "dev"

    # -------------------------
    # DATABASE
    # -------------------------
    MONGO_URL: str = os.getenv("MONGO_URI", "")
    DB_NAME: str = os.getenv("DB_NAME", "crm_db")

    # -------------------------
    # REDIS (optional future)
    # -------------------------
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # -------------------------
    # SYSTEM
    # -------------------------
    MAX_HISTORY: int = int(os.getenv("MAX_HISTORY", 20))

    # -------------------------
    # SECURITY
    # -------------------------
    ADMIN_SECRET: str = os.getenv("ADMIN_SECRET", "1234")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev_secret_change_me_very_important")

    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

    # -------------------------
    # CORS
    # -------------------------
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")

    # -------------------------
    # VALIDATION (NO CRASH MODE)
    # -------------------------
    def validate(self) -> bool:
        issues = []

        if not self.MONGO_URL:
            issues.append("MONGO_URI missing")

        if not self.DB_NAME:
            issues.append("DB_NAME missing")

        for i in issues:
            logging.warning(f"[CONFIG] {i}")

        return True


# =========================================
# INSTANCE
# =========================================

settings = Settings()

# safe validate (never crash runtime)
settings.validate()
