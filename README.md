# TasteKart

An India-focused food delivery demo for local development. The frontend is a vanilla HTML/CSS/JS experience; the backend is a FastAPI service backed by MongoDB.

## Product flow

- Discover nearby restaurants and cuisines
- Add a restaurant's menu to the cart
- Preview totals through the checkout service
- Create an order through the order service
- Confirm a UPI payment through the payment service
- Persist users, restaurants, menu items, and orders in MongoDB

## Services

The service boundaries live in `backend/app/main.py` for this compact demo:

- `userService` — creates or updates a local customer profile
- `checkout` — previews subtotal, delivery fee, and total
- `orderService` — validates menu items and creates an order transaction
- `paymentService` — confirms payment and advances the order to `CONFIRMED`

## Run locally

```bash
MAPPLS_ACCESS_TOKEN=your-mappls-static-key docker compose up --build
```

The customer profile uses Mappls Autosuggest for delivery addresses when `MAPPLS_ACCESS_TOKEN` is configured. The token stays in Docker/backend environment configuration; the browser calls the protected application proxy. Without a token, the profile keeps a manual complete-address fallback. See Mappls [Autosuggest API](https://mapplsapi.com/api-reference/core-location-get-api-places-search-json-autosuggest-api) and [Web Maps access documentation](https://developer.mappls.com/documentation/sdk/Web/Web%20JS/).

Open [http://localhost:3001](http://localhost:3001). To run the API outside Docker, start MongoDB first, then:

```bash
pip install -r backend/requirements.txt
MONGO_URL=mongodb://localhost:27017 MONGO_DB_NAME=tastekart JWT_SECRET=change-this-secret uvicorn backend.app.main:app --host 0.0.0.0 --port 3001
```

MongoDB collections and indexes are initialized automatically on first startup, and the six demo restaurants and menus are seeded when the database is empty.

MongoDB uses the named Docker volume `tastekart_mongo_data`, so users, partner accounts, restaurants, menus, sessions, and orders survive container restarts and recreations. Remove that volume only when intentionally resetting local data.

## Restaurant partner workspace

Open [http://localhost:3001/partner](http://localhost:3001/partner) to use the partner dashboard. In this demo, partners select one of the seeded restaurants and can:

- Open or close the restaurant for new customer orders
- Add menu items with a name, price, and emoji
- Hide or remove menu items without deleting historical order data
- Review incoming orders and move them through preparation, pickup, delivery, or cancellation

Partner endpoints are grouped under `/api/partner`. The demo uses the selected restaurant ID as the partner identity; production authentication and role-based access should be added before deployment.

## Frontend structure

```text
frontend/
├── pages/customer/       # Customer ordering page
├── pages/partner/        # Restaurant partner dashboard
├── scripts/customer/     # Customer interactions
├── scripts/partner/      # Partner interactions
├── styles/customer/      # Customer styles
├── styles/partner/       # Partner styles
└── assets/               # Shared brand assets
```
