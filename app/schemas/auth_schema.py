# app/schemas/auth_schema.py

from pydantic import BaseModel, EmailStr
from typing import Optional


# =========================
# 🔐 REGISTER SCHEMA
# =========================

class RegisterSchema(BaseModel):
    email: EmailStr
    password: str
    name: str
    fingerprint: Optional[str] = None


# =========================
# 🔐 LOGIN SCHEMA
# =========================

class LoginSchema(BaseModel):
    email: EmailStr
    password: str
    fingerprint: Optional[str] = None


# =========================
# 👤 TOKEN RESPONSE
# =========================

class TokenSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"


# =========================
# 👤 AUTH RESPONSE
# =========================

class AuthResponseSchema(BaseModel):
    success: bool
    message: Optional[str] = None
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    user: Optional[dict] = None


# =========================
# 👤 USER OUTPUT
# =========================

class UserSchema(BaseModel):
    id: Optional[str] = None
    email: EmailStr
    name: str
    role: Optional[str] = "trader"
    fingerprint: Optional[str] = None
    created_at: Optional[str] = None
    last_login: Optional[str] = None