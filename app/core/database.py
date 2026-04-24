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


def generate_id():
    return str(uuid.uuid4())


def init_mongo_client():
    global client, db
    global orders_collection, customers_collection
    global learning_collection, memory_collection
    global conversations_collection, suggestions_collection

    if not settings.MONGO_URL:
        logger.error("MONGO_URI missing")
        return

    client = AsyncIOMotorClient(
        settings.MONGO_URL,
        serverSelectionTimeoutMS=5000,
        maxPoolSize=50,
    )

    db = client[settings.DB_NAME]

    orders_collection = db["orders"]
    customers_collection = db["customers"]
    learning_collection = db["learning"]
    memory_collection = db["memory"]
    conversations_collection = db["conversations"]
    suggestions_collection = db["suggestions"]


def get_database():
    global db

    if db is None:
        init_mongo_client()

    if db is None:
        raise RuntimeError("Database not initialized yet")

    return db


async def init_mongo_indexes():
    global client

    if client is None:
        init_mongo_client()

    if db is None:
        logger.warning("MongoDB not ready")
        return

    try:
        await client.admin.command("ping")

        await orders_collection.create_index("phone")
        await customers_collection.create_index("phone", unique=True)
        await memory_collection.create_index("phone", unique=True)
        await conversations_collection.create_index("id", unique=True)
        await suggestions_collection.create_index("visitor_id")
        await db["visitors"].create_index("fingerprint", unique=True)

        logger.info("MongoDB connected")

    except ConnectionFailure as e:
        logger.warning(f"MongoDB connection failed: {e}")
