import os
import secrets
import time
import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import jwt
from pymongo import ASCENDING, DESCENDING, MongoClient

ROOT = Path(__file__).resolve().parents[2]
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "tastekart")
JWT_SECRET = os.getenv("JWT_SECRET", "tastekart-development-secret-change-me")
MAPPLS_ACCESS_TOKEN = os.getenv("MAPPLS_ACCESS_TOKEN", "fsdskoezjmibcnwuceyychchwvcarbsryyah")
ADMIN_EMAIL = os.getenv("TASTEKART_ADMIN_EMAIL", "admin@tastekart.local").strip().lower()
ADMIN_PASSWORD = os.getenv("TASTEKART_ADMIN_PASSWORD", "admin12345")
mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
database = mongo_client[MONGO_DB_NAME]
users = database.users
restaurants_collection = database.restaurants
menu_items = database.menu_items
orders = database.orders
partners = database.partners


def generate_order_id() -> str:
    """Create a customer-facing order ID with date, time, and a random suffix."""
    while True:
        order_id = f"TK-{time.strftime('%Y-%m-%d-%H%M')}-{secrets.token_hex(4).upper()}"
        if not orders.find_one({"id": order_id}, {"_id": 1}):
            return order_id
admins = database.admins
sessions = database.sessions
FRONTEND_PATH = ROOT / "frontend"

app = FastAPI(title="TasteKart API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def http_error(message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=message)


@app.exception_handler(HTTPException)
def api_error(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


def restaurant_seed() -> None:
    if restaurants_collection.count_documents({}):
        return


def remove_demo_restaurants() -> None:
    demo_ids = ["bluru-bowl", "pizza-4p", "bao-house", "burger-singh", "green-spoon", "chai-point"]
    restaurants_collection.delete_many({"id": {"$in": demo_ids}, "partner_id": {"$exists": False}})
    menu_items.delete_many({"restaurant_id": {"$in": demo_ids}})


@app.on_event("startup")
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
            remove_demo_restaurants()
            restaurant_seed()
            for item in menu_items.find({"food_type": {"$exists": False}}, {"_id": 1, "name": 1}):
                menu_items.update_one({"_id": item["_id"]}, {"$set": {"food_type": classify_food_type(item.get("name", ""))}})
            if not admins.find_one({"email": ADMIN_EMAIL}):
                admins.insert_one({"id": str(uuid4()), "name": "TasteKart Admin", "email": ADMIN_EMAIL, "password_hash": password_digest(ADMIN_PASSWORD), "created_at": time.time()})
            for partner in partners.find({"logo_url": {"$exists": False}}, {"_id": 0, "id": 1}):
                restaurant = restaurants_collection.find_one({"partner_id": partner["id"], "image_url": {"$nin": [None, ""]}}, {"_id": 0, "image_url": 1})
                partners.update_one({"id": partner["id"]}, {"$set": {"logo_url": (restaurant or {}).get("image_url", "")}})
            return
        except Exception as error:
            last_error = error
            time.sleep(2)
    raise last_error or RuntimeError("MongoDB initialization failed")


class UserRequest(BaseModel):
    id: Optional[UUID] = None
    name: str = "Ananya"


class OrderItemRequest(BaseModel):
    id: int
    quantity: int = Field(default=1, ge=1)


class OrderRequest(BaseModel):
    userId: Optional[UUID] = None
    userName: str = "Ananya"
    address: Optional[str] = None
    items: list[OrderItemRequest] = Field(default_factory=list)


class PaymentRequest(BaseModel):
    method: str = "upi"


class AuthRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str
    name: Optional[str] = None
    address: Optional[str] = None


class PartnerProfileUpdate(BaseModel):
    name: str
    email: str
    logoUrl: str = ""
    password: Optional[str] = None


class AddressRequest(BaseModel):
    label: str = "Home"
    fullAddress: str
    house: str = ""
    landmark: str = ""
    city: str = ""
    pincode: str = ""
    placeId: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RestaurantOnboardingRequest(BaseModel):
    name: str
    cuisine: str
    deliveryMinutes: str = "25–35 min"
    imageUrl: str = ""
    description: str = ""


class MenuItemRequest(BaseModel):
    name: str
    price: int = Field(ge=1)
    emoji: str = "🍽️"
    imageUrl: str = ""
    foodType: Optional[str] = None


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = Field(default=None, ge=1)
    emoji: Optional[str] = None
    imageUrl: Optional[str] = None
    available: Optional[bool] = None


def classify_food_type(name: str) -> str:
    non_veg_terms = ("chicken", "murg", "egg", "fish", "prawn", "mutton", "meat", "bacon", "ham", "pork", "beef", "seafood", "nugget", "wings")
    return "non-veg" if any(term in name.lower() for term in non_veg_terms) else "veg"


class RestaurantStatusRequest(BaseModel):
    isOpen: bool


class OrderStatusRequest(BaseModel):
    status: str
    restaurantId: str


def get_or_create_user(user_id: Optional[UUID], name: str) -> dict[str, Any]:
    uid = str(user_id or uuid4())
    users.update_one({"id": uid}, {"$set": {"name": name}, "$setOnInsert": {"id": uid, "created_at": time.time()}}, upsert=True)
    return users.find_one({"id": uid}, {"_id": 0})


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


def account_identifier(payload: AuthRequest) -> str:
    identifier = (payload.username or payload.email or "").strip().lower()
    if not identifier:
        raise http_error("Username or email is required")
    return identifier


def create_session(user_id: str, role: str) -> str:
    token = jwt.encode({"sub": user_id, "role": role, "iat": int(time.time()), "exp": int(time.time()) + 60 * 60 * 24 * 7}, JWT_SECRET, algorithm="HS256")
    sessions.insert_one({"token": token, "user_id": user_id, "role": role, "created_at": time.time()})
    return token


def decode_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise http_error("Login required", 401)
    if not sessions.find_one({"token": token}):
        raise http_error("Login required", 401)
    return claims


def require_partner(request: Request) -> dict[str, Any]:
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip()
    if not token:
        raise http_error("Partner login required", 401)
    claims = decode_token(token)
    if claims.get("role") != "partner":
        raise http_error("Partner login required", 401)
    partner = partners.find_one({"id": claims["sub"]}, {"_id": 0})
    if not partner:
        raise http_error("Partner account not found", 401)
    return partner


def require_admin(request: Request) -> dict[str, Any]:
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip()
    if not token:
        raise http_error("Admin login required", 401)
    claims = decode_token(token)
    if claims.get("role") != "admin":
        raise http_error("Admin login required", 401)
    admin = admins.find_one({"id": claims["sub"]}, {"_id": 0})
    if not admin:
        raise http_error("Admin account not found", 401)
    return admin


def require_customer(request: Request) -> dict[str, Any]:
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip()
    if not token:
        raise http_error("Customer login required", 401)
    claims = decode_token(token)
    if claims.get("role") != "customer":
        raise http_error("Customer login required", 401)
    user = users.find_one({"id": claims["sub"]}, {"_id": 0})
    if not user:
        raise http_error("Customer account not found", 401)
    return user


@app.post("/api/auth/register", status_code=201)
def register_customer(payload: AuthRequest) -> dict[str, Any]:
    username = account_identifier(payload)
    if len(payload.password) < 6 or not payload.name:
        raise http_error("Name, username, and a password of at least 6 characters are required")
    if users.find_one({"$or": [{"username": username}, {"email": username}]}):
        raise http_error("An account with this username already exists", 409)
    user_id = str(uuid4())
    users.insert_one({"id": user_id, "name": payload.name.strip(), "username": username, "email": username, "password_hash": password_digest(payload.password), "address": payload.address.strip() if payload.address else "", "addresses": [], "created_at": time.time()})
    return {"message": "Account created. Please log in to continue.", "user": {"id": user_id, "name": payload.name.strip(), "username": username, "address": payload.address.strip() if payload.address else "", "addresses": []}}


@app.post("/api/partner/auth/register", status_code=201)
def register_partner(payload: AuthRequest) -> dict[str, Any]:
    email = account_identifier(payload)
    if len(payload.password) < 6 or not payload.name:
        raise http_error("Name, email, and a password of at least 6 characters are required")
    if partners.find_one({"email": email}):
        raise http_error("A partner account with this email already exists", 409)
    partner_id = str(uuid4())
    partners.insert_one({"id": partner_id, "name": payload.name.strip(), "email": email, "password_hash": password_digest(payload.password), "created_at": time.time()})
    token = create_session(partner_id, "partner")
    return {"token": token, "partner": {"id": partner_id, "name": payload.name.strip(), "email": email}}


@app.post("/api/auth/login")
def login_customer(payload: AuthRequest) -> dict[str, Any]:
    account = users.find_one({"$or": [{"username": account_identifier(payload)}, {"email": account_identifier(payload)}]})
    if not account or not account.get("password_hash") or not password_matches(payload.password, account["password_hash"]):
        raise http_error("Invalid username or password", 401)
    token = create_session(account["id"], "customer")
    return {"token": token, "user": clean_document(account)}


@app.post("/api/partner/auth/login")
def login_partner(payload: AuthRequest) -> dict[str, Any]:
    account = partners.find_one({"$or": [{"username": account_identifier(payload)}, {"email": account_identifier(payload)}]})
    if not account or not password_matches(payload.password, account["password_hash"]):
        raise http_error("Invalid partner email or password", 401)
    token = create_session(account["id"], "partner")
    return {"token": token, "partner": clean_document(account)}


@app.post("/api/admin/auth/login")
def login_admin(payload: AuthRequest) -> dict[str, Any]:
    email = account_identifier(payload)
    account = admins.find_one({"email": email})
    if not account or not password_matches(payload.password, account["password_hash"]):
        raise http_error("Invalid admin email or password", 401)
    token = create_session(account["id"], "admin")
    return {"token": token, "admin": clean_document(account)}


@app.get("/api/auth/me")
def current_account(request: Request) -> dict[str, Any]:
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not token:
        raise http_error("Login required", 401)
    claims = decode_token(token)
    collection = admins if claims["role"] == "admin" else partners if claims["role"] == "partner" else users
    account = clean_document(collection.find_one({"id": claims["sub"]}, {"_id": 0}))
    if not account:
        raise http_error("Account not found", 404)
    account.pop("password_hash", None)
    return {"role": claims["role"], "account": account}


@app.patch("/api/partner/profile")
def update_partner_profile(payload: PartnerProfileUpdate, request: Request) -> dict[str, Any]:
    partner = require_partner(request)
    name = payload.name.strip()
    email = payload.email.strip().lower()
    if not name or not email:
        raise http_error("Name and email are required")
    if partners.find_one({"email": email, "id": {"$ne": partner["id"]}}):
        raise http_error("That email is already used by another partner", 409)
    changes: dict[str, Any] = {"name": name, "email": email, "logo_url": payload.logoUrl.strip()}
    if payload.password is not None and payload.password.strip():
        if len(payload.password) < 6:
            raise http_error("Password must be at least 6 characters")
        changes["password_hash"] = password_digest(payload.password)
    partners.update_one({"id": partner["id"]}, {"$set": changes})
    updated = clean_document(partners.find_one({"id": partner["id"]}, {"_id": 0}))
    return {"partner": updated}


@app.delete("/api/partner/profile")
def delete_partner_profile(request: Request) -> dict[str, bool]:
    partner = require_partner(request)
    restaurant_ids = [row["id"] for row in restaurants_collection.find({"partner_id": partner["id"]}, {"_id": 0, "id": 1})]
    if restaurant_ids:
        menu_items.delete_many({"restaurant_id": {"$in": restaurant_ids}})
        orders.delete_many({"restaurant_id": {"$in": restaurant_ids}})
        restaurants_collection.delete_many({"id": {"$in": restaurant_ids}})
    partners.delete_one({"id": partner["id"]})
    sessions.delete_many({"user_id": partner["id"], "role": "partner"})
    return {"ok": True}


@app.post("/api/auth/addresses", status_code=201)
def add_customer_address(payload: AddressRequest, request: Request) -> dict[str, Any]:
    user = require_customer(request)
    full_address = payload.fullAddress.strip()
    if not full_address:
        raise http_error("Please select or enter an address")
    address = {"id": str(uuid4()), "label": payload.label.strip() or "Home", "full_address": full_address, "house": payload.house.strip(), "landmark": payload.landmark.strip(), "city": payload.city.strip(), "pincode": payload.pincode.strip(), "place_id": payload.placeId.strip(), "latitude": payload.latitude, "longitude": payload.longitude, "created_at": time.time()}
    existing = user.get("addresses", [])
    users.update_one({"id": user["id"]}, {"$set": {"address": full_address, "addresses": [*existing, address]}})
    return {"address": address, "addresses": [*existing, address]}


@app.get("/api/config")
def public_config() -> dict[str, str]:
    return {"mapplsEnabled": "true" if MAPPLS_ACCESS_TOKEN else "false"}


@app.get("/api/locations/autosuggest")
def mappls_autosuggest(q: str) -> dict[str, Any]:
    query = q.strip()
    if len(query) < 2:
        return {"suggestions": []}
    if not MAPPLS_ACCESS_TOKEN:
        raise http_error("Mappls is not configured", 503)
    params = urllib.parse.urlencode({"query": query, "region": "IND", "access_token": MAPPLS_ACCESS_TOKEN})
    request = urllib.request.Request(f"https://atlas.mapmyindia.com/api/places/search/json?{params}", headers={"Authorization": f"Bearer {MAPPLS_ACCESS_TOKEN}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise http_error("Mappls rejected the configured token (401 Unauthorized)", 502)
        raise http_error(f"Mappls address search unavailable (HTTP {error.code})", 502)
    except (urllib.error.URLError, TimeoutError) as error:
        raise http_error(f"Mappls address search unavailable: {error}", 502)
    rows = result.get("suggestedLocations", result.get("suggestions", [])) if isinstance(result, dict) else []
    suggestions = [{"label": row.get("placeAddress") or row.get("placeName") or row.get("address", ""), "placeId": row.get("eLoc") or row.get("placeId", ""), "latitude": row.get("latitude"), "longitude": row.get("longitude"), "city": row.get("city", ""), "pincode": row.get("pincode") or row.get("postalCode", "")} for row in rows if isinstance(row, dict)]
    return {"suggestions": suggestions[:8]}


@app.post("/api/auth/logout")
def logout(request: Request) -> dict[str, bool]:
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    sessions.delete_one({"token": token})
    return {"ok": True}


@app.get("/api/health")
def health() -> dict[str, Any]:
    try:
        mongo_client.admin.command("ping")
        return {"ok": True, "services": ["user-service", "checkout-service", "order-service", "payment-service", "partner-service"], "database": "mongodb"}
    except Exception:
        return JSONResponse(status_code=503, content={"ok": False, "database": "mongodb"})


@app.get("/api/restaurants")
def restaurants() -> dict[str, Any]:
    restaurant_rows = [clean_document(row) for row in restaurants_collection.find({}, {"_id": 0}).sort("rating", DESCENDING)]
    menu_rows = [clean_document(row) for row in menu_items.find({"available": True}, {"_id": 0})]
    return {"restaurants": [{**restaurant, "menu": [item for item in menu_rows if item["restaurant_id"] == restaurant["id"]]} for restaurant in restaurant_rows]}


@app.post("/api/users", status_code=201)
def create_user(payload: UserRequest) -> dict[str, Any]:
    return {"user": get_or_create_user(payload.id, payload.name)}


@app.post("/api/checkout/preview")
def checkout_preview(payload: OrderRequest) -> dict[str, int]:
    prices = {item["id"]: item["price"] for item in menu_items.find({"id": {"$in": [item.id for item in payload.items]}}, {"_id": 0, "id": 1, "price": 1})}
    subtotal = sum(prices.get(item.id, 0) * item.quantity for item in payload.items)
    fee = 29 if subtotal else 0
    return {"subtotal": subtotal, "deliveryFee": fee, "total": subtotal + fee}


@app.post("/api/orders", status_code=201)
def create_order(payload: OrderRequest, request: Request) -> dict[str, Any]:
    if not payload.items:
        raise http_error("Cart is empty")
    user = require_customer(request)
    item_ids = [item.id for item in payload.items]
    available = {item["id"]: item for item in menu_items.find({"id": {"$in": item_ids}, "available": True}, {"_id": 0})}
    clean = [(available[item.id], item.quantity) for item in payload.items if item.id in available]
    if not clean:
        raise http_error("No valid menu items")
    restaurant_ids = {item["restaurant_id"] for item, _ in clean}
    if len(restaurant_ids) != 1:
        raise http_error("Please order from one restaurant at a time")
    restaurant_id = next(iter(restaurant_ids))
    if not restaurants_collection.find_one({"id": restaurant_id, "is_open": True}):
        raise http_error("This restaurant is currently closed")
    subtotal = sum(item["price"] * quantity for item, quantity in clean)
    fee = 29 if subtotal else 0
    order_id = generate_order_id()
    delivery_address = (payload.address or user.get("address", "")).strip()
    if not delivery_address:
        raise http_error("Please add a delivery address before placing your order")
    orders.insert_one({"id": order_id, "user_id": user["id"], "restaurant_id": restaurant_id, "status": "PLACED", "payment_status": "PENDING", "subtotal": subtotal, "delivery_fee": fee, "total": subtotal + fee, "address": delivery_address, "items": [{"id": item["id"], "name": item["name"], "price": item["price"], "quantity": quantity} for item, quantity in clean], "created_at": time.time()})
    return {"order": {"id": order_id, "status": "PLACED", "paymentStatus": "PENDING", "subtotal": subtotal, "deliveryFee": fee, "total": subtotal + fee, "eta": "28–35 min"}}


@app.post("/api/payments/{order_id}")
def pay_order(order_id: str, payload: PaymentRequest) -> dict[str, Any]:
    result = orders.update_one({"id": order_id}, {"$set": {"payment_status": "PAID", "status": "CONFIRMED"}})
    if not result.matched_count:
        raise http_error("Order not found", 404)
    return {"payment": {"orderId": order_id, "status": "CONFIRMED", "paymentStatus": "PAID", "method": payload.method}}


@app.get("/api/orders")
def customer_orders(request: Request) -> dict[str, Any]:
    user = require_customer(request)
    rows = [clean_document(row) for row in orders.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", DESCENDING)]
    return {"orders": rows}


@app.get("/api/orders/{order_id}")
def get_order(order_id: str) -> dict[str, Any]:
    order = clean_document(orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise http_error("Order not found", 404)
    return {"order": order}


@app.get("/api/admin/restaurants")
def admin_restaurants(request: Request) -> dict[str, Any]:
    require_admin(request)
    rows = []
    for restaurant in restaurants_collection.find({"partner_id": {"$exists": True}}, {"_id": 0}).sort("name", ASCENDING):
        partner = partners.find_one({"id": restaurant.get("partner_id")}, {"_id": 0, "name": 1, "email": 1})
        row = clean_document(restaurant)
        row["partner"] = partner or {"name": "Deleted partner", "email": ""}
        rows.append(row)
    return {"restaurants": rows}


@app.get("/api/partner/restaurants")
def partner_restaurants(request: Request) -> dict[str, Any]:
    partner = require_partner(request)
    return {"restaurants": [clean_document(row) for row in restaurants_collection.find({"partner_id": partner["id"]}, {"_id": 0}).sort("name", ASCENDING)]}


@app.post("/api/partner/restaurants", status_code=201)
def onboard_restaurant(request: Request, payload: RestaurantOnboardingRequest) -> dict[str, Any]:
    partner = require_partner(request)
    if not payload.name.strip() or not payload.cuisine.strip():
        raise http_error("Restaurant name and cuisine are required")
    restaurant_id = f"{payload.name.strip().lower().replace(' ', '-')}-{secrets.token_hex(2)}"
    restaurant = {"id": restaurant_id, "partner_id": partner["id"], "name": payload.name.strip(), "cuisine": payload.cuisine.strip(), "rating": 0, "delivery_minutes": payload.deliveryMinutes, "image_url": payload.imageUrl, "description": payload.description.strip(), "is_open": False}
    restaurants_collection.insert_one(restaurant)
    if payload.imageUrl.strip() and not partner.get("logo_url", "").strip():
        partners.update_one({"id": partner["id"]}, {"$set": {"logo_url": payload.imageUrl.strip()}})
    return {"restaurant": clean_document(restaurant)}


@app.delete("/api/partner/restaurants/{restaurant_id}")
def delete_partner_restaurant(restaurant_id: str, request: Request) -> dict[str, bool]:
    partner = require_partner(request)
    result = restaurants_collection.delete_one({"id": restaurant_id, "partner_id": partner["id"]})
    if not result.deleted_count:
        raise http_error("Restaurant not found", 404)
    menu_items.delete_many({"restaurant_id": restaurant_id})
    orders.delete_many({"restaurant_id": restaurant_id})
    return {"ok": True}


@app.get("/api/partner/restaurants/{restaurant_id}")
def partner_dashboard(restaurant_id: str, request: Request) -> dict[str, Any]:
    partner = require_partner(request)
    restaurant = clean_document(restaurants_collection.find_one({"id": restaurant_id, "partner_id": partner["id"]}, {"_id": 0}))
    if not restaurant:
        raise http_error("Restaurant not found", 404)
    menu = [clean_document(row) for row in menu_items.find({"restaurant_id": restaurant_id}, {"_id": 0}).sort("id", ASCENDING)]
    order_rows = []
    for row in orders.find({"restaurant_id": restaurant_id}, {"_id": 0}).sort("created_at", DESCENDING).limit(50):
        order = clean_document(row)
        customer = users.find_one({"id": order.get("user_id")}, {"_id": 0, "name": 1, "address": 1})
        order["customer_name"] = (customer or {}).get("name", "Customer")
        order["customer_address"] = (customer or {}).get("address", order.get("address", ""))
        order_rows.append(order)
    return {"restaurant": restaurant, "menu": menu, "orders": order_rows}


@app.post("/api/partner/restaurants/{restaurant_id}/menu", status_code=201)
def add_menu_item(restaurant_id: str, payload: MenuItemRequest, request: Request) -> dict[str, Any]:
    partner = require_partner(request)
    if not restaurants_collection.find_one({"id": restaurant_id, "partner_id": partner["id"]}):
        raise http_error("Restaurant not found", 404)
    next_id = (menu_items.find_one(sort=[("id", DESCENDING)]) or {}).get("id", 0) + 1
    food_type = payload.foodType if payload.foodType in {"veg", "non-veg"} else classify_food_type(payload.name)
    item = {"id": next_id, "restaurant_id": restaurant_id, "name": payload.name.strip(), "price": payload.price, "emoji": payload.emoji, "image_url": payload.imageUrl, "food_type": food_type, "available": True}
    menu_items.insert_one(item)
    return {"item": clean_document(item)}


@app.patch("/api/partner/menu/{item_id}")
def update_menu_item(item_id: int, payload: MenuItemUpdate, request: Request) -> dict[str, Any]:
    partner = require_partner(request)
    changes = payload.model_dump(exclude_none=True)
    if "imageUrl" in changes:
        changes["image_url"] = changes.pop("imageUrl")
    if not changes:
        raise http_error("No changes supplied")
    owned_restaurant_ids = [row["id"] for row in restaurants_collection.find({"partner_id": partner["id"]}, {"_id": 0, "id": 1})]
    result = menu_items.update_one({"id": item_id, "restaurant_id": {"$in": owned_restaurant_ids}}, {"$set": changes})
    if not result.matched_count:
        raise http_error("Menu item not found", 404)
    return {"item": clean_document(menu_items.find_one({"id": item_id}, {"_id": 0}))}


@app.delete("/api/partner/menu/{item_id}")
def remove_menu_item(item_id: int, request: Request) -> dict[str, bool]:
    partner = require_partner(request)
    owned_restaurant_ids = [row["id"] for row in restaurants_collection.find({"partner_id": partner["id"]}, {"_id": 0, "id": 1})]
    result = menu_items.update_one({"id": item_id, "restaurant_id": {"$in": owned_restaurant_ids}}, {"$set": {"available": False}})
    if not result.matched_count:
        raise http_error("Menu item not found", 404)
    return {"ok": True}


@app.patch("/api/partner/restaurants/{restaurant_id}/status")
def update_restaurant_status(restaurant_id: str, payload: RestaurantStatusRequest, request: Request) -> dict[str, Any]:
    partner = require_partner(request)
    result = restaurants_collection.update_one({"id": restaurant_id, "partner_id": partner["id"]}, {"$set": {"is_open": payload.isOpen}})
    if not result.matched_count:
        raise http_error("Restaurant not found", 404)
    return {"restaurant": {"id": restaurant_id, "is_open": payload.isOpen}}


@app.patch("/api/partner/orders/{order_id}/status")
def update_order_status(order_id: str, payload: OrderStatusRequest, request: Request) -> dict[str, Any]:
    partner = require_partner(request)
    allowed = {"PLACED", "CONFIRMED", "PREPARING", "READY", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"}
    if payload.status not in allowed:
        raise http_error("Invalid order status")
    if not restaurants_collection.find_one({"id": payload.restaurantId, "partner_id": partner["id"]}):
        raise http_error("Order not found for this restaurant", 404)
    result = orders.update_one({"id": order_id, "restaurant_id": payload.restaurantId}, {"$set": {"status": payload.status}})
    if not result.matched_count:
        raise http_error("Order not found for this restaurant", 404)
    return {"order": {"id": order_id, "status": payload.status}}


@app.get("/partner")
def partner_page() -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "partner" / "index.html")


@app.get("/partner/{partner_slug}/menu")
def partner_menu_page(partner_slug: str) -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "partner" / "index.html")


@app.get("/partner/{restaurant_slug}/orders")
def partner_orders_page(restaurant_slug: str) -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "partner" / "index.html")


@app.get("/partner/{restaurant_slug}/restaurant")
def partner_restaurant_page(restaurant_slug: str) -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "partner" / "index.html")


@app.get("/partner/{partner_slug}")
def partner_named_page(partner_slug: str) -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "partner" / "index.html")


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "admin" / "index.html")


@app.get("/")
def customer_page() -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "customer" / "index.html")


@app.get("/profile")
def customer_profile_page() -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "customer" / "profile.html")


@app.get("/cart")
def customer_cart_page() -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "customer" / "cart.html")


@app.get("/restaurant/{restaurant_id}/menu")
def customer_restaurant_menu_page(restaurant_id: str) -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "customer" / "restaurant-menu.html")


@app.get("/orders")
def customer_orders_page() -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "customer" / "orders.html")


@app.get("/congratulations")
def customer_congratulations_page() -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "customer" / "congratulations.html")


@app.get("/login")
def customer_login_page() -> FileResponse:
    return FileResponse(FRONTEND_PATH / "pages" / "customer" / "login.html")


app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="frontend")
