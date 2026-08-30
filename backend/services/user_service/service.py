import json
import urllib.error
import urllib.parse
import urllib.request
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.shared.core import MAPPLS_ACCESS_TOKEN, admins, clean_document, create_session, decode_token, http_error, initialize_database, install_service_auth, password_digest, password_matches, partners, request_token, require_role, sessions, users
from backend.shared.models import AddressRequest, AuthRequest

app = FastAPI(title="TasteKart User Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
install_service_auth(app)


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def identifier(payload: AuthRequest) -> str:
    value = (payload.username or payload.email or "").strip().lower()
    if not value:
        raise http_error("Username or email is required")
    return value


@app.post("/auth/register", status_code=201)
def register(payload: AuthRequest):
    username = identifier(payload)
    if len(payload.password) < 6 or not payload.name:
        raise http_error("Name, username, and a password of at least 6 characters are required")
    if users.find_one({"$or": [{"username": username}, {"email": username}]}):
        raise http_error("An account with this username already exists", 409)
    user_id = str(uuid4())
    address = payload.address.strip() if payload.address else ""
    users.insert_one({"id": user_id, "name": payload.name.strip(), "username": username, "email": username, "password_hash": password_digest(payload.password), "address": address, "addresses": [], "created_at": time.time()})
    return {"message": "Account created. Please log in to continue.", "user": {"id": user_id, "name": payload.name.strip(), "username": username, "address": address, "addresses": []}}


@app.post("/auth/login")
def login(payload: AuthRequest):
    account = users.find_one({"$or": [{"username": identifier(payload)}, {"email": identifier(payload)}]})
    if not account or not account.get("password_hash") or not password_matches(payload.password, account["password_hash"]):
        raise http_error("Invalid username or password", 401)
    return {"token": create_session(account["id"], "customer"), "user": clean_document(account)}


@app.post("/admin/auth/login")
def admin_login(payload: AuthRequest):
    account = admins.find_one({"email": identifier(payload)})
    if not account or not password_matches(payload.password, account["password_hash"]):
        raise http_error("Invalid admin email or password", 401)
    return {"token": create_session(account["id"], "admin"), "admin": clean_document(account)}


@app.get("/auth/me")
def current_account(request: Request):
    token = request_token(request)
    if not token:
        raise http_error("Login required", 401)
    claims = decode_token(token)
    collections = {"customer": users, "partner": partners, "admin": admins}
    account = clean_document(collections.get(claims.get("role"), users).find_one({"id": claims["sub"]}, {"_id": 0}))
    if not account:
        raise http_error("Account not found", 404)
    return {"role": claims["role"], "account": account}


@app.post("/auth/addresses", status_code=201)
def add_address(payload: AddressRequest, request: Request):
    user = require_role(request, "customer")
    full_address = payload.fullAddress.strip()
    if not full_address:
        raise http_error("Please select or enter an address")
    address = {"id": str(uuid4()), "label": payload.label.strip() or "Home", "full_address": full_address, "house": payload.house.strip(), "landmark": payload.landmark.strip(), "city": payload.city.strip(), "pincode": payload.pincode.strip(), "place_id": payload.placeId.strip(), "latitude": payload.latitude, "longitude": payload.longitude, "created_at": time.time()}
    addresses = [*user.get("addresses", []), address]
    users.update_one({"id": user["id"]}, {"$set": {"address": full_address, "addresses": addresses}})
    return {"address": address, "addresses": addresses}


@app.post("/auth/logout")
def logout(request: Request):
    sessions.delete_one({"token": request_token(request)})
    return {"ok": True}


@app.get("/config")
def config():
    return {"mapplsEnabled": "true" if MAPPLS_ACCESS_TOKEN else "false"}


@app.get("/locations/autosuggest")
def autosuggest(q: str):
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
        raise http_error(f"Mappls address search unavailable (HTTP {error.code})", 502)
    except (urllib.error.URLError, TimeoutError) as error:
        raise http_error(f"Mappls address search unavailable: {error}", 502)
    rows = result.get("suggestedLocations", result.get("suggestions", [])) if isinstance(result, dict) else []
    return {"suggestions": [{"label": row.get("placeAddress") or row.get("placeName") or row.get("address", ""), "placeId": row.get("eLoc") or row.get("placeId", ""), "latitude": row.get("latitude"), "longitude": row.get("longitude"), "city": row.get("city", ""), "pincode": row.get("pincode") or row.get("postalCode", "")} for row in rows if isinstance(row, dict)][:8]}


@app.get("/health")
def health():
    return {"ok": True, "service": "user-service"}
