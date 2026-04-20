# app/main.py
import logging
from fastapi import FastAPI
from app.routes import order_routes, customer_routes
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.services.usage_service import ensure_usage_indexes
from app.routes import admin_routes # ⬅️ هنا
from app.routes.export_routes import router as export_router
from app.routes import visitor_routes
from app.routes import suggestions
from app.routes import comment_routes

# 🔴 حل فوضى MongoDB (pymongo spam)
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("pymongo.topology").setLevel(logging.WARNING)
logging.getLogger("pymongo.connection").setLevel(logging.WARNING)
logging.getLogger("pymongo.serverSelection").setLevel(logging.WARNING)


# ✅ مستوى logging العام
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION
)

app.include_router(order_routes.router)
app.include_router(customer_routes.router)
app.include_router(admin_routes.router) # ⬅️ هنا
app.include_router(export_router)
app.include_router(visitor_routes.router)
app.include_router(suggestions.router)
app.include_router(comment_routes.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "CRM API is running "}
    
@app.on_event("startup")
def startup():
    logger.info("Async Queue System READY")
    ensure_usage_indexes()