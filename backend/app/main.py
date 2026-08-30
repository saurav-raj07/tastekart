import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_PATH = ROOT / "frontend"
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:3002")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:3003")
PARTNER_SERVICE_URL = os.getenv("PARTNER_SERVICE_URL", "http://partner-service:3004")
CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://catalog-service:3005")

app = FastAPI(title="TasteKart API Gateway", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def service_for(path: str, request: Request) -> str:
    if path.startswith("auth/register") or path.startswith("auth/login") or path.startswith("auth/addresses") or path.startswith("auth/logout") or path in {"auth/me", "config"} or path.startswith("locations/") or path.startswith("admin/auth/"):
        if path == "auth/me":
            token = request.headers.get("authorization", "")
            if "." in token:
                import jwt
                try:
                    role = jwt.decode(token.removeprefix("Bearer ").strip(), options={"verify_signature": False}).get("role")
                    if role == "partner": return PARTNER_SERVICE_URL
                except jwt.PyJWTError:
                    pass
        return USER_SERVICE_URL
    if path.startswith("partner/") or path.startswith("admin/"):
        return ORDER_SERVICE_URL if path.startswith("partner/orders/") else PARTNER_SERVICE_URL
    if path.startswith("restaurants") or path.startswith("checkout/"):
        return CATALOG_SERVICE_URL
    if path.startswith("orders") or path.startswith("payments/"):
        return ORDER_SERVICE_URL
    return USER_SERVICE_URL


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"])
async def api_proxy(path: str, request: Request):
    if path == "health":
        return await health()
    service = service_for(path, request)
    upstream_path = path.removeprefix("partner/") if service == PARTNER_SERVICE_URL and path.startswith("partner/") and not path.startswith("partner/orders/") else path
    url = f"{service}/{upstream_path}"
    body = await request.body()
    headers = {key: value for key, value in request.headers.items() if key.lower() not in {"host", "content-length"}}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            upstream = await client.request(request.method, url, params=request.query_params, content=body, headers=headers)
    except httpx.HTTPError:
        return Response('{"error":"Service unavailable"}', status_code=503, media_type="application/json")
    response_headers = {key: value for key, value in upstream.headers.items() if key.lower() not in {"content-encoding", "transfer-encoding", "connection"}}
    return Response(upstream.content, status_code=upstream.status_code, headers=response_headers, media_type=upstream.headers.get("content-type"))


@app.get("/api/health")
async def health():
    services = {"user-service": USER_SERVICE_URL, "catalog-service": CATALOG_SERVICE_URL, "order-service": ORDER_SERVICE_URL, "partner-service": PARTNER_SERVICE_URL}
    result = {}
    async with httpx.AsyncClient(timeout=3) as client:
        for name, url in services.items():
            try:
                response = await client.get(f"{url}/health")
                result[name] = response.status_code == 200
            except httpx.HTTPError:
                result[name] = False
    ok = all(result.values())
    return Response(__import__("json").dumps({"ok": ok, "services": result, "database": "mongodb"}), status_code=200 if ok else 503, media_type="application/json")


@app.get("/")
def customer_page(): return FileResponse(FRONTEND_PATH / "pages/customer/index.html")
@app.get("/profile")
def profile_page(): return FileResponse(FRONTEND_PATH / "pages/customer/profile.html")
@app.get("/cart")
def cart_page(): return FileResponse(FRONTEND_PATH / "pages/customer/cart.html")
@app.get("/orders")
def orders_page(): return FileResponse(FRONTEND_PATH / "pages/customer/orders.html")
@app.get("/login")
def login_page(): return FileResponse(FRONTEND_PATH / "pages/customer/login.html")
@app.get("/congratulations")
def congratulations_page(): return FileResponse(FRONTEND_PATH / "pages/customer/congratulations.html")
@app.get("/restaurant/{restaurant_id}/menu")
def restaurant_menu_page(restaurant_id: str): return FileResponse(FRONTEND_PATH / "pages/customer/restaurant-menu.html")
@app.get("/partner")
@app.get("/partner/{path:path}")
def partner_page(path: str = ""): return FileResponse(FRONTEND_PATH / "pages/partner/index.html")
@app.get("/admin")
def admin_page(): return FileResponse(FRONTEND_PATH / "pages/admin/index.html")

app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="frontend")
