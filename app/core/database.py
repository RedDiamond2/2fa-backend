# app/core/database.py

import uuid
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from app.core.config import settings

logger = logging.getLogger("database")

# =========================================
# 🔹 MongoDB Connection
# =========================================

client = None
db = None

orders_collection = None
customers_collection = None
learning_collection = None
memory_collection = None
conversations_collection = None
suggestions_collection = None  # ✅ NEW


# =========================================
# 🔹 Helpers
# =========================================

def generate_id() -> str:
    return str(uuid.uuid4())


def get_orders_collection():
    if orders_collection is None:
        raise Exception("DB not initialized")
    return orders_collection


def get_database():
    """
    Returns the active MongoDB database instance.
    """
    global db

    if db is None:
        logger.error("Database accessed before initialization")
        raise RuntimeError("Database not initialized yet")

    return db

# =========================================
# 🔹 INIT MONGO
# =========================================

def init_mongo():
    global client, db
    global orders_collection, customers_collection, learning_collection
    global memory_collection, conversations_collection
    global suggestions_collection  # ✅ NEW

    if not settings.MONGO_URL:
        logger.error("MONGO_URI is not set")
        return

    try:
        client = MongoClient(
            settings.MONGO_URL,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=50
        )

        client.admin.command("ping")

        db = client[settings.DB_NAME]

        # 🔹 Collections
        orders_collection = db["orders"]
        customers_collection = db["customers"]
        learning_collection = db["learning"]
        memory_collection = db["memory"]
        conversations_collection = db["conversations"]
        suggestions_collection = db["suggestions"]  # ✅ NEW

        # 🔥 Indexes (Production)
        orders_collection.create_index("phone")
        customers_collection.create_index("phone", unique=True)
        memory_collection.create_index("phone", unique=True)
        conversations_collection.create_index("id", unique=True)

        # ✅ NEW: suggestions indexes
        suggestions_collection.create_index("visitor_id")
        suggestions_collection.create_index("created_at")

        logger.info("MongoDB connected successfully to Atlas")

    except ConnectionFailure as e:
        logger.error(f"MongoDB connection failed: {e}")


# 🚀 init
init_mongo()