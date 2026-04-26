# app/main.py
import sys
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_mongo_client, init_mongo_indexes

from app.services.usage_service import ensure_usage_indexes

from app.routes import (
    order_routes,
    customer_routes,
    admin_routes,
    auth_routes,
    visitor_routes,
    suggestions,
    comment_routes,
)

from app.routes.export_routes import router as export_router

print("Python:", sys.version)

logging.getLogger("pymongo").setLevel(logging.WARNING)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 backend starting...")

    try:
        init_mongo_client()
        await init_mongo_indexes()
        ensure_usage_indexes()
        logger.info("✅ startup complete")
    except Exception as e:
        logger.warning(f"startup partial: {e}")

    yield

    logger.info("shutdown")


app = FastAPI(title=settings.APP_NAME, version=settings.VERSION, lifespan=lifespan)


allow_origins = settings.CORS_ORIGINS.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://twofa-backend-hbkp.onrender.com",
        "http://localhost:5173",
        "https://reddiamond2.github.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(order_routes.router)
app.include_router(customer_routes.router)
app.include_router(admin_routes.router)
app.include_router(auth_routes.router)
app.include_router(export_router)
app.include_router(visitor_routes.router)
app.include_router(suggestions.router)
app.include_router(comment_routes.router)


@app.get("/")
def root():
    return {"message": "CRM API running", "status": "ok"}
