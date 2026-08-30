from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.shared.core import clean_document, initialize_database, menu_items, restaurants_collection
from backend.shared.models import OrderRequest

app = FastAPI(title="TasteKart Catalog Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    initialize_database()

@app.get("/restaurants")
def restaurants():
    restaurant_rows = [clean_document(row) for row in restaurants_collection.find({}, {"_id": 0}).sort("rating", -1)]
    menu_rows = [clean_document(row) for row in menu_items.find({"available": True}, {"_id": 0})]
    return {"restaurants": [{**restaurant, "menu": [item for item in menu_rows if item["restaurant_id"] == restaurant["id"]]} for restaurant in restaurant_rows]}

@app.post("/checkout/preview")
def checkout_preview(payload: OrderRequest):
    prices = {item["id"]: item["price"] for item in menu_items.find({"id": {"$in": [item.id for item in payload.items]}}, {"_id": 0, "id": 1, "price": 1})}
    subtotal = sum(prices.get(item.id, 0) * item.quantity for item in payload.items)
    fee = 29 if subtotal else 0
    return {"subtotal": subtotal, "deliveryFee": fee, "total": subtotal + fee}

@app.get("/health")
def health():
    return {"ok": True, "service": "catalog-service"}
