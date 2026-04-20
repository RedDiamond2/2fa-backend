# app/routes/auth_routes.py

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional, Dict, Any

from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])

auth_service = AuthService()


# =========================
# 🔐 REGISTER
# =========================

@router.post("/register")
async def register(payload: Dict[str, Any]):
    email = payload.get("email")
    password = payload.get("password")
    name = payload.get("name")
    fingerprint = payload.get("fingerprint")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    result = await auth_service.register_user(
        email=email,
        password=password,
        name=name,
        fingerprint=fingerprint
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))

    return result


# =========================
# 🔐 LOGIN
# =========================

@router.post("/login")
async def login(payload: Dict[str, Any]):
    email = payload.get("email")
    password = payload.get("password")
    fingerprint = payload.get("fingerprint")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    result = await auth_service.login_user(
        email=email,
        password=password,
        fingerprint=fingerprint
    )

    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("message"))

    return result


# =========================
# 👤 CURRENT USER
# =========================

@router.get("/me")
async def get_me(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization.replace("Bearer ", "")

    user = await auth_service.get_current_user(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "success": True,
        "user": user
    }