import secrets
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.shared.core import clean_document, create_session, decode_token, http_error, initialize_database, install_service_auth, menu_items, orders, partners, password_digest, password_matches, request_token, require_role, restaurants_collection, users
from backend.shared.models import AuthRequest, MenuItemRequest, MenuItemUpdate, OrderStatusRequest, PartnerProfileUpdate, RestaurantOnboardingRequest, RestaurantStatusRequest

app = FastAPI(title="TasteKart Partner Service")
app.add_middleware(CORSMiddleware, allow_origins=[
                   "*"], allow_methods=["*"], allow_headers=["*"])
install_service_auth(app)


@app.on_event("startup")
def startup():
    initialize_database()


def identifier(payload: AuthRequest) -> str:
    value = (payload.username or payload.email or "").strip().lower()
    if not value:
        raise http_error("Email is required")
    return value


@app.post("/auth/register", status_code=201)
def register(payload: AuthRequest):
    email = identifier(payload)
    if len(payload.password) < 6 or not payload.name:
        raise http_error(
            "Name, email, and a password of at least 6 characters are required")
    if partners.find_one({"email": email}):
        raise http_error(
            "A partner account with this email already exists", 409)
    partner = {"id": str(uuid4()), "name": payload.name.strip(), "email": email,
               "password_hash": password_digest(payload.password), "created_at": time.time()}
    partners.insert_one(partner)
    return {"token": create_session(partner["id"], "partner"), "partner": clean_document(partner)}


@app.post("/auth/login")
def login(payload: AuthRequest):
    account = partners.find_one({"email": identifier(payload)})
    if not account or not password_matches(payload.password, account["password_hash"]):
        raise http_error("Invalid partner email or password", 401)
    return {"token": create_session(account["id"], "partner"), "partner": clean_document(account)}


@app.get("/auth/me")
def current_account(request: Request):
    claims = decode_token(request_token(request))
    if claims.get("role") != "partner":
        raise http_error("Partner login required", 401)
    account = clean_document(partners.find_one(
        {"id": claims["sub"]}, {"_id": 0}))
    if not account:
        raise http_error("Partner account not found", 401)
    return {"role": "partner", "account": account}


@app.patch("/profile")
def update_profile(payload: PartnerProfileUpdate, request: Request):
    partner = require_role(request, "partner")
    name, email = payload.name.strip(), payload.email.strip().lower()
    if not name or not email:
        raise http_error("Name and email are required")
    if partners.find_one({"email": email, "id": {"$ne": partner["id"]}}):
        raise http_error("That email is already used by another partner", 409)
    changes = {"name": name, "email": email,
               "logo_url": payload.logoUrl.strip()}
    if payload.password and payload.password.strip():
        if len(payload.password) < 6:
            raise http_error("Password must be at least 6 characters")
        changes["password_hash"] = password_digest(payload.password)
    partners.update_one({"id": partner["id"]}, {"$set": changes})
    return {"partner": clean_document(partners.find_one({"id": partner["id"]}, {"_id": 0}))}


@app.delete("/profile")
def delete_profile(request: Request):
    partner = require_role(request, "partner")
    ids = [row["id"] for row in restaurants_collection.find(
        {"partner_id": partner["id"]}, {"_id": 0, "id": 1})]
    if ids:
        menu_items.delete_many({"restaurant_id": {"$in": ids}})
        orders.delete_many({"restaurant_id": {"$in": ids}})
        restaurants_collection.delete_many({"id": {"$in": ids}})
    partners.delete_one({"id": partner["id"]})
    return {"ok": True}


@app.get("/restaurants")
def list_restaurants(request: Request):
    partner = require_role(request, "partner")
    return {"restaurants": [clean_document(row) for row in restaurants_collection.find({"partner_id": partner["id"]}, {"_id": 0}).sort("name", 1)]}


@app.post("/restaurants", status_code=201)
def onboard(payload: RestaurantOnboardingRequest, request: Request):
    partner = require_role(request, "partner")
    if not payload.name.strip() or not payload.cuisine.strip():
        raise http_error("Restaurant name and cuisine are required")
    restaurant = {"id": f"{payload.name.strip().lower().replace(' ', '-')}-{secrets.token_hex(2)}", "partner_id": partner["id"], "name": payload.name.strip(), "cuisine": payload.cuisine.strip(
    ), "rating": 0, "delivery_minutes": payload.deliveryMinutes, "image_url": payload.imageUrl, "description": payload.description.strip(), "is_open": False}
    restaurants_collection.insert_one(restaurant)
    if payload.imageUrl.strip() and not partner.get("logo_url", "").strip():
        partners.update_one({"id": partner["id"]}, {
                            "$set": {"logo_url": payload.imageUrl.strip()}})
    return {"restaurant": clean_document(restaurant)}


@app.delete("/restaurants/{restaurant_id}")
def delete_restaurant(restaurant_id: str, request: Request):
    partner = require_role(request, "partner")
    result = restaurants_collection.delete_one(
        {"id": restaurant_id, "partner_id": partner["id"]})
    if not result.deleted_count:
        raise http_error("Restaurant not found", 404)
    menu_items.delete_many({"restaurant_id": restaurant_id})
    orders.delete_many({"restaurant_id": restaurant_id})
    return {"ok": True}


@app.get("/restaurants/{restaurant_id}")
def dashboard(restaurant_id: str, request: Request):
    partner = require_role(request, "partner")
    restaurant = clean_document(restaurants_collection.find_one(
        {"id": restaurant_id, "partner_id": partner["id"]}, {"_id": 0}))
    if not restaurant:
        raise http_error("Restaurant not found", 404)
    menu = [clean_document(row) for row in menu_items.find(
        {"restaurant_id": restaurant_id}, {"_id": 0}).sort("id", 1)]
    rows = []
    for raw in orders.find({"restaurant_id": restaurant_id}, {"_id": 0}).sort("created_at", -1).limit(50):
        order = clean_document(raw)
        customer = users.find_one({"id": order.get("user_id")}, {
                                  "_id": 0, "name": 1, "address": 1}) or {}
        order["customer_name"], order["customer_address"] = customer.get(
            "name", "Customer"), customer.get("address", order.get("address", ""))
        rows.append(order)
    return {"restaurant": restaurant, "menu": menu, "orders": rows}


@app.post("/restaurants/{restaurant_id}/menu", status_code=201)
def add_item(restaurant_id: str, payload: MenuItemRequest, request: Request):
    partner = require_role(request, "partner")
    if not restaurants_collection.find_one({"id": restaurant_id, "partner_id": partner["id"]}):
        raise http_error("Restaurant not found", 404)
    next_id = (menu_items.find_one(sort=[("id", -1)]) or {}).get("id", 0) + 1
    food_type = payload.foodType if payload.foodType in {"veg", "non-veg"} else ("non-veg" if any(
        term in payload.name.lower() for term in ("chicken", "mutton", "egg", "fish", "prawn")) else "veg")
    item = {"id": next_id, "restaurant_id": restaurant_id, "name": payload.name.strip(), "price": payload.price,
            "emoji": payload.emoji, "image_url": payload.imageUrl, "food_type": food_type, "available": True}
    menu_items.insert_one(item)
    return {"item": clean_document(item)}


@app.patch("/menu/{item_id}")
def update_item(item_id: int, payload: MenuItemUpdate, request: Request):
    partner = require_role(request, "partner")
    changes = payload.model_dump(exclude_none=True)
    if "imageUrl" in changes:
        changes["image_url"] = changes.pop("imageUrl")
    if not changes:
        raise http_error("No changes supplied")
    ids = [row["id"] for row in restaurants_collection.find(
        {"partner_id": partner["id"]}, {"_id": 0, "id": 1})]
    result = menu_items.update_one(
        {"id": item_id, "restaurant_id": {"$in": ids}}, {"$set": changes})
    if not result.matched_count:
        raise http_error("Menu item not found", 404)
    return {"item": clean_document(menu_items.find_one({"id": item_id}, {"_id": 0}))}


@app.delete("/menu/{item_id}")
def remove_item(item_id: int, request: Request):
    partner = require_role(request, "partner")
    ids = [row["id"] for row in restaurants_collection.find(
        {"partner_id": partner["id"]}, {"_id": 0, "id": 1})]
    if not menu_items.update_one({"id": item_id, "restaurant_id": {"$in": ids}}, {"$set": {"available": False}}).matched_count:
        raise http_error("Menu item not found", 404)
    return {"ok": True}


@app.patch("/restaurants/{restaurant_id}/status")
def status(restaurant_id: str, payload: RestaurantStatusRequest, request: Request):
    partner = require_role(request, "partner")
    if not restaurants_collection.update_one({"id": restaurant_id, "partner_id": partner["id"]}, {"$set": {"is_open": payload.isOpen}}).matched_count:
        raise http_error("Restaurant not found", 404)
    return {"restaurant": {"id": restaurant_id, "is_open": payload.isOpen}}


@app.get("/admin/restaurants")
def admin_restaurants(request: Request):
    require_role(request, "admin")
    rows = []
    for restaurant in restaurants_collection.find({"partner_id": {"$exists": True}}, {"_id": 0}).sort("name", 1):
        row = clean_document(restaurant)
        row["partner"] = partners.find_one({"id": restaurant.get("partner_id")}, {
                                           "_id": 0, "name": 1, "email": 1}) or {"name": "Deleted partner", "email": ""}
        rows.append(row)
    return {"restaurants": rows}


@app.get("/health")
def health(): return {"ok": True, "service": "partner-service"}
