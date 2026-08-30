import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.shared.core import clean_document, generate_order_id, http_error, initialize_database, menu_items, orders, restaurants_collection, require_role, users
from backend.shared.models import OrderRequest, OrderStatusRequest, PaymentRequest

app = FastAPI(title="TasteKart Order Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    initialize_database()

@app.post("/orders", status_code=201)
def create_order(payload: OrderRequest, request: Request):
    if not payload.items:
        raise http_error("Cart is empty")
    user = require_role(request, "customer")
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
    address = (payload.address or user.get("address", "")).strip()
    if not address:
        raise http_error("Please add a delivery address before placing your order")
    order_id = generate_order_id()
    orders.insert_one({"id": order_id, "user_id": user["id"], "restaurant_id": restaurant_id, "status": "PLACED", "payment_status": "PENDING", "subtotal": subtotal, "delivery_fee": fee, "total": subtotal + fee, "address": address, "items": [{"id": item["id"], "name": item["name"], "price": item["price"], "quantity": quantity} for item, quantity in clean], "created_at": time.time()})
    return {"order": {"id": order_id, "status": "PLACED", "paymentStatus": "PENDING", "subtotal": subtotal, "deliveryFee": fee, "total": subtotal + fee, "eta": "28–35 min"}}

@app.post("/payments/{order_id}")
def pay_order(order_id: str, payload: PaymentRequest):
    result = orders.update_one({"id": order_id}, {"$set": {"payment_status": "PAID", "status": "CONFIRMED"}})
    if not result.matched_count:
        raise http_error("Order not found", 404)
    return {"payment": {"orderId": order_id, "status": "CONFIRMED", "paymentStatus": "PAID", "method": payload.method}}

@app.get("/orders")
def customer_orders(request: Request):
    user = require_role(request, "customer")
    return {"orders": [clean_document(row) for row in orders.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)]}

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = clean_document(orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise http_error("Order not found", 404)
    return {"order": order}

@app.patch("/partner/orders/{order_id}/status")
def update_partner_order(order_id: str, payload: OrderStatusRequest, request: Request):
    partner = require_role(request, "partner")
    allowed = {"PLACED", "CONFIRMED", "PREPARING", "READY", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"}
    if payload.status not in allowed or not restaurants_collection.find_one({"id": payload.restaurantId, "partner_id": partner["id"]}):
        raise http_error("Order not found for this restaurant", 404)
    result = orders.update_one({"id": order_id, "restaurant_id": payload.restaurantId}, {"$set": {"status": payload.status}})
    if not result.matched_count: raise http_error("Order not found for this restaurant", 404)
    return {"order": {"id": order_id, "status": payload.status}}

@app.get("/health")
def health():
    return {"ok": True, "service": "order-service"}
