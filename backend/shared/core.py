import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

import jwt
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pymongo import ASCENDING, DESCENDING, MongoClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "tastekart")
JWT_SECRET = os.getenv("JWT_SECRET", "tastekart-development-secret-change-me")
ADMIN_EMAIL = os.getenv("TASTEKART_ADMIN_EMAIL", "admin@tastekart.local").strip().lower()
ADMIN_PASSWORD = os.getenv("TASTEKART_ADMIN_PASSWORD", "admin12345")
MAPPLS_ACCESS_TOKEN = os.getenv("MAPPLS_ACCESS_TOKEN", "")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "tastekart-internal-development-token")

mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
database = mongo_client[MONGO_DB_NAME]
users = database.users
restaurants_collection = database.restaurants
menu_items = database.menu_items
orders = database.orders
partners = database.partners
admins = database.admins
sessions = database.sessions


def http_error(message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=message)


def clean_document(document: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if document is None:
        return None
    document.pop("_id", None)
    document.pop("password_hash", None)
    return document


def password_digest(password: str, salt: Optional[bytes] = None) -> str:
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), actual_salt, 120_000)
    return f"{actual_salt.hex()}${digest.hex()}"


def password_matches(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", 1)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 120_000).hex()
    return hmac.compare_digest(candidate, digest_hex)


def create_session(account_id: str, role: str) -> str:
    token = jwt.encode({"sub": account_id, "role": role, "iat": int(time.time()), "exp": int(time.time()) + 60 * 60 * 24 * 7}, JWT_SECRET, algorithm="HS256")
    sessions.insert_one({"token": token, "user_id": account_id, "role": role, "created_at": time.time()})
    return token


def decode_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise http_error("Login required", 401)
    if not sessions.find_one({"token": token}):
        raise http_error("Login required", 401)
    return claims


def request_token(request: Request) -> str:
    return request.headers.get("authorization", "").removeprefix("Bearer ").strip()


def install_service_auth(app) -> None:
    """Require the gateway's private token on non-health service requests."""
    @app.middleware("http")
    async def service_auth(request: Request, call_next):
        if request.url.path != "/health" and request.headers.get("x-service-token") != SERVICE_TOKEN:
            return JSONResponse(status_code=401, content={"error": "Internal service authentication required"})
        return await call_next(request)


def require_role(request: Request, role: str) -> dict[str, Any]:
    token = request_token(request)
    if not token:
        raise http_error(f"{role.title()} login required", 401)
    claims = decode_token(token)
    if claims.get("role") != role:
        raise http_error(f"{role.title()} login required", 401)
    collection = {"customer": users, "partner": partners, "admin": admins}[role]
    account = collection.find_one({"id": claims["sub"]}, {"_id": 0})
    if not account:
        raise http_error(f"{role.title()} account not found", 401)
    return account


def classify_food_type(name: str) -> str:
    non_veg_terms = ("chicken", "murg", "egg", "fish", "prawn", "mutton", "meat", "bacon", "ham", "pork", "beef", "seafood", "nugget", "wings")
    return "non-veg" if any(term in name.lower() for term in non_veg_terms) else "veg"


def generate_order_id() -> str:
    while True:
        order_id = f"TK-{time.strftime('%Y-%m-%d-%H%M')}-{secrets.token_hex(4).upper()}"
        if not orders.find_one({"id": order_id}, {"_id": 1}):
            return order_id


def initialize_database() -> None:
    last_error: Optional[Exception] = None
    for _ in range(30):
        try:
            mongo_client.admin.command("ping")
            restaurants_collection.create_index([("rating", DESCENDING)])
            menu_items.create_index([("restaurant_id", ASCENDING)])
            orders.create_index([("restaurant_id", ASCENDING), ("created_at", DESCENDING)])
            partners.create_index("email", unique=True)
            admins.create_index("email", unique=True)
            sessions.create_index("token", unique=True)
            if not admins.find_one({"email": ADMIN_EMAIL}):
                admins.insert_one({"id": str(uuid4()), "name": "TasteKart Admin", "email": ADMIN_EMAIL, "password_hash": password_digest(ADMIN_PASSWORD), "created_at": time.time()})
            return
        except Exception as error:
            last_error = error
            time.sleep(2)
    raise last_error or RuntimeError("MongoDB initialization failed")
