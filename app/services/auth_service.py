# app/services/auth_service.py

from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from passlib.context import CryptContext
from jose import jwt, JWTError

from app.core.config import settings
from app.repositories.customer_repository import CustomerRepository
from app.repositories.user_model import UserRepository

# =========================
# 🔐 SECURITY CONFIG
# =========================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = settings.SECRET_KEY if hasattr(settings, "SECRET_KEY") else "dev_secret"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


# =========================
# 🔐 PASSWORD UTILS
# =========================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# =========================
# 🔐 TOKEN SERVICE
# =========================

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return {}


# =========================
# 👤 AUTH SERVICE CORE
# =========================

class AuthService:

    def __init__(self):
        self.user_repo = UserRepository()
        self.customer_repo = CustomerRepository()

    # -------------------------
    # REGISTER
    # -------------------------
    async def register_user(self, email: str, password: str, name: str, fingerprint: Optional[str] = None):
        existing = await self.user_repo.find_by_email(email)
        if existing:
            return {"success": False, "message": "User already exists"}

        hashed = hash_password(password)

        user = {
            "email": email,
            "name": name,
            "password": hashed,
            "fingerprint": fingerprint,
            "role": "trader",
            "created_at": datetime.utcnow(),
            "last_login": None,
        }

        created = await self.user_repo.create(user)

        token = create_access_token({"sub": str(created["_id"]), "email": email, "role": "trader"})

        return {
            "success": True,
            "user": created,
            "access_token": token,
            "token_type": "bearer",
        }

    # -------------------------
    # LOGIN
    # -------------------------
    async def login_user(self, email: str, password: str, fingerprint: Optional[str] = None):
        user = await self.user_repo.find_by_email(email)

        if not user:
            return {"success": False, "message": "Invalid credentials"}

        if not verify_password(password, user["password"]):
            return {"success": False, "message": "Invalid credentials"}

        await self.user_repo.update(user["_id"], {
            "last_login": datetime.utcnow(),
            "fingerprint": fingerprint or user.get("fingerprint")
        })

        token = create_access_token({
            "sub": str(user["_id"]),
            "email": user["email"],
            "role": user.get("role", "trader")
        })

        return {
            "success": True,
            "user": user,
            "access_token": token,
            "token_type": "bearer",
        }

    # -------------------------
    # VERIFY TOKEN
    # -------------------------
    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        payload = decode_token(token)

        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        return payload

    # -------------------------
    # GET CURRENT USER
    # -------------------------
    async def get_current_user(self, token: str):
        payload = self.verify_access_token(token)
        if not payload:
            return None

        user_id = payload.get("sub")
        return await self.user_repo.find_by_id(user_id)