# app/core/database.py

import uuid
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from app.core.config import settings

logger = logging.getLogger("database")

client: AsyncIOMotorClient | None = None
db = None

orders_collection = None
customers_collection = None
learning_collection = None
memory_collection = None
conversations_collection = None
suggestions_collection = None


# =========================================
# 🟢 ID GENERATOR
# =========================================


def generate_id() -> str:
    return str(uuid.uuid4())


# =========================================
# 🟢 INIT MONGO CLIENT
# =========================================


def init_mongo_client():
    global client, db
    global orders_collection, customers_collection
    global learning_collection, memory_collection
    global conversations_collection, suggestions_collection

    if not settings.MONGO_URL:
        logger.error("❌ MONGO_URL missing")
        return

    if client is not None:
        return

    client = AsyncIOMotorClient(
        settings.MONGO_URL,
        serverSelectionTimeoutMS=5000,
        maxPoolSize=50,
        retryWrites=True,
    )

    db = client[settings.DB_NAME]

    orders_collection = db["orders"]
    customers_collection = db["customers"]
    learning_collection = db["learning"]
    memory_collection = db["memory"]
    conversations_collection = db["conversations"]
    suggestions_collection = db["suggestions"]

    logger.info("✅ Mongo initialized")


# =========================================
# 🟢 GET DATABASE
# =========================================


def get_database():
    global db

    if db is None:
        init_mongo_client()

    if db is None:
        raise RuntimeError("Database not initialized yet")

    return db


# =========================================
# 🟢 GET COLLECTIONS SAFE
# =========================================


def get_collections():
    global db

    if db is None:
        init_mongo_client()

    if db is None:
        raise RuntimeError("Database not initialized")

    return {
        "db": db,
        "orders": db["orders"],
        "customers": db["customers"],
        "learning": db["learning"],
        "memory": db["memory"],
        "conversations": db["conversations"],
        "suggestions": db["suggestions"],
    }


# =========================================
# 🟢 INDEX INITIALIZATION
# =========================================


async def init_mongo_indexes():
    global client, db

    if client is None:
        init_mongo_client()

    if db is None:
        logger.warning("MongoDB not ready")
        return

    try:
        await client.admin.command("ping")

        # ORDERS
        await orders_collection.create_index("phone")

        # CUSTOMERS (important indexes)
        await customers_collection.create_index("phone")
        await customers_collection.create_index("fingerprint", unique=True)
        await customers_collection.create_index("email_canonical", sparse=True)
        await customers_collection.create_index("phone_normalized", sparse=True)

        # MEMORY
        await memory_collection.create_index("phone", unique=True, sparse=True)

        # CONVERSATIONS
        await conversations_collection.create_index("id", unique=True)

        # SUGGESTIONS
        await suggestions_collection.create_index("visitor_id")
        await suggestions_collection.create_index("created_at")

        # VISITORS
        await db["visitors"].create_index("fingerprint", unique=True)

        logger.info("✅ MongoDB connected + indexes ready")

    except ConnectionFailure as e:
        logger.warning(f"❌ MongoDB connection failed: {e}")
