# app/services/auth_service.py

from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from passlib.context import CryptContext
from jose import jwt, JWTError

from fastapi import HTTPException

from app.core.config import settings
from app.repositories.customer_repository import CustomerRepository
from app.repositories.user_repository import UserRepository


ALLOWED_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "protonmail.com", "icloud.com", "zoho.com"
}


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7


def extract_name_from_email(email: str) -> str:
    return email.split("@")[0]


def validate_email_domain(email: str):
    domain = email.split("@")[-1].lower()
    if domain not in ALLOWED_DOMAINS:
        raise HTTPException(status_code=400, detail="Email domain not allowed")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(p: str, h: str) -> bool:
    return pwd_context.verify(p, h)


def create_access_token(data: Dict[str, Any]):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow()
    })

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


class AuthService:

    def __init__(self):
        self.user_repo = UserRepository()
        self.customer_repo = CustomerRepository()

    async def register_user(self, email: str, password: str, name: str = None, fingerprint: str = None):

        validate_email_domain(email)

        if not name:
            name = extract_name_from_email(email)

        existing = await self.user_repo.find_by_email(email)
        if existing:
            return {"success": False, "message": "User already exists"}

        user = {
            "email": email,
            "name": name,
            "password": hash_password(password),
            "fingerprint": fingerprint,
            "role": "trader",
            "created_at": datetime.utcnow(),
            "last_login": None
        }

        created = await self.user_repo.create(user)

        token = create_access_token({
            "sub": str(created["_id"]),
            "email": email,
            "role": "trader"
        })

        return {
            "success": True,
            "user": {
                "id": str(created["_id"]),
                "email": email,
                "name": name,
                "role": "trader"
            },
            "access_token": token,
            "token_type": "bearer"
        }

    async def login_user(self, email: str, password: str, fingerprint: str = None):

        user = await self.user_repo.find_by_email(email)

        if not user:
            return {"success": False, "message": "Invalid credentials"}

        if not verify_password(password, user["password"]):
            return {"success": False, "message": "Invalid credentials"}

        await self.user_repo.update(user["_id"], {
            "last_login": datetime.utcnow(),
            "fingerprint": fingerprint
        })

        token = create_access_token({
            "sub": str(user["_id"]),
            "email": email,
            "role": user.get("role", "trader")
        })

        return {
            "success": True,
            "user": {
                "id": str(user["_id"]),
                "email": email,
                "name": user.get("name"),
                "role": user.get("role")
            },
            "access_token": token,
            "token_type": "bearer"
        }

    def verify_token(self, token: str):
        return decode_token(token)

    async def get_current_user(self, token: str):
        payload = self.verify_token(token)

        if not payload:
            return None

        user = await self.user_repo.find_by_id(payload.get("sub"))

        if not user:
            return None

        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "name": user.get("name"),
            "role": user.get("role")
        }


def get_auth_service():
    return AuthService()