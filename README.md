# TasteKart

TasteKart is a local food-delivery demo. Customers can browse restaurants, manage a cart, save delivery addresses, place orders, and simulate UPI payment. Partners can manage restaurants, menus, and order status. An admin view lists partner restaurants.

The frontend is built with vanilla HTML, CSS, and JavaScript. The backend is built with FastAPI and MongoDB, with an API gateway serving the frontend and forwarding browser requests to the internal services.

## Features

- Customer registration and login
- Restaurant and menu browsing
- Single-restaurant cart and checkout flow
- Simulated UPI payment confirmation
- Customer order history
- Saved delivery addresses with optional Mappls autocomplete
- Partner registration and login
- Restaurant onboarding and open/closed status
- Partner menu availability management
- Partner order workflow: placed → preparing → ready → delivered
- Admin restaurant overview

## Architecture

```text
Browser
   │
   ▼
app / API gateway (:3001)
   ├── user-service    (:3002)  auth, profiles, addresses, sessions
   ├── order-service   (:3003)  orders, payments, order status
   ├── partner-service (:3004)  partner accounts, restaurants, menus
   └── catalog-service (:3005)  restaurant catalog and checkout preview
                                  │
                                  ▼
                              MongoDB (:27017)
```

All browser API calls use the `/api/...` gateway contract. Internal services require the shared `SERVICE_TOKEN` header. For this local demo, the services use the same MongoDB database and shared JWT configuration.

## Requirements

- Docker Desktop with Docker Compose
- Git
- Optional: a Mappls access token for address autocomplete

## Run with Docker

From the repository root:

```bash
docker compose up --build -d
```

Then open:

- Customer app: <http://localhost:3001>
- Customer login: <http://localhost:3001/login>
- Customer profile: <http://localhost:3001/profile>
- Customer orders: <http://localhost:3001/orders>
- Partner workspace: <http://localhost:3001/partner>
- Admin workspace: <http://localhost:3001/admin>
- Health status: <http://localhost:3001/api/health>

To stop the stack without deleting data:

```bash
docker compose stop
```

To stop and remove containers while keeping the MongoDB volume:

```bash
docker compose down
```

Do not use `docker compose down -v` unless you intentionally want to delete the local MongoDB data.

## Environment configuration

Docker Compose supplies development defaults. For local configuration, create an ignored `.env` file in the repository root:

```dotenv
MAPPLS_ACCESS_TOKEN=
JWT_SECRET=replace-with-a-long-random-secret
SERVICE_TOKEN=replace-with-a-long-random-service-token
TASTEKART_ADMIN_EMAIL=admin@tastekart.local
TASTEKART_ADMIN_PASSWORD=change-this-password
```

`MAPPLS_ACCESS_TOKEN` is optional. Without it, the profile page still supports manual address entry.

The default credentials and tokens in `docker-compose.yml` are for local development only. Replace them before exposing the application outside a trusted local environment.

## Data persistence

MongoDB stores its files in the named Docker volume `tastekart_mongo_data`, mounted at `/data/db`. Stopping or recreating the application containers does not remove this volume.

The data is deleted only when the volume is explicitly removed, for example:

```bash
docker compose down -v
```

For a backup, use `mongodump` against the MongoDB container or configure a regular MongoDB backup process before testing destructive changes.

## Cloud Deployment (AWS, Terraform & Kubernetes)

TasteKart includes full Infrastructure as Code (Terraform) and Kubernetes manifests to take the entire microservice stack live on AWS.

### Architecture Overview
- **Cloud Provider**: AWS (`ap-south-1`)
- **Infrastructure as Code**: Terraform in `terraform/`
- **Container Registry**: AWS ECR (`tastekart-backend`)
- **Compute**: Single EC2 instance (`t3.medium`) running **K3s** (lightweight Kubernetes)
- **Database**: In-cluster MongoDB (`mongo:7.0`) with persistent EBS disk volume (`10Gi`)
- **Networking**: VPC, Public Subnet, Security Groups (Ports 80, 443, 3001, 30001, 22), Elastic IP

### 🚀 1-Click Launch (Recommended)
From the repository root:
```powershell
python scripts/launch.py
```
This script automatically:
1. Provisions AWS infrastructure using `terraform apply`
2. Authenticates with AWS ECR, builds, and pushes the unified Docker image
3. Waits for the EC2 instance and K3s node to report `Ready`
4. Bundles and applies all Kubernetes manifests in `k8s/` via AWS SSM
5. Verifies `/api/health` and displays your live URL (`http://<ELASTIC_IP>:30001`)

### 🛑 1-Click Teardown (Stop Paying)
When you want to destroy all cloud infrastructure to prevent ongoing charges:
```powershell
python scripts/destroy.py
```
This cleanly purges the ECR repository and runs `terraform destroy -auto-approve`.

### Manual Step-by-Step Deployment
If you prefer running commands manually:
1. **Provision Infrastructure**:
   ```powershell
   cd terraform
   terraform apply
   ```
2. **Push Docker Image to ECR**:
   ```powershell
   (aws ecr get-login-password --region ap-south-1).Trim() | docker login --username AWS --password-stdin 305042756398.dkr.ecr.ap-south-1.amazonaws.com
   docker build -t 305042756398.dkr.ecr.ap-south-1.amazonaws.com/tastekart-backend:latest .
   docker push 305042756398.dkr.ecr.ap-south-1.amazonaws.com/tastekart-backend:latest
   ```
3. **Deploy to K3s**:
   ```powershell
   python scripts/deploy_k8s.py
   ```
4. **Access the Application**:
   ```text
   http://<ELASTIC_IP>:30001
   ```

### CI/CD Pipeline (Jenkins)
The repository includes a complete [`Jenkinsfile`](Jenkinsfile) that automates:
- Syntax checking for Python and JavaScript
- AWS ECR login, Docker build, and image tagging
- Rolling deployment to Kubernetes (`kubectl apply -f k8s/...`)
- Post-deployment health verification on `/api/health`

## API overview

The gateway exposes these main route groups:

| Route | Purpose |
| --- | --- |
| `/api/auth/*` | Customer authentication, profile, addresses, logout |
| `/api/admin/auth/login` | Admin login |
| `/api/restaurants` | Public restaurant catalog |
| `/api/checkout/preview` | Checkout total preview |
| `/api/orders` | Create and list customer orders |
| `/api/payments/{order_id}` | Simulated payment confirmation |
| `/api/partner/auth/*` | Partner registration and login |
| `/api/partner/profile` | Partner profile management |
| `/api/partner/restaurants` | Partner restaurant and menu management |
| `/api/partner/orders/{order_id}/status` | Partner order status updates |
| `/api/admin/restaurants` | Admin restaurant overview |

The internal services are not intended to be called directly from the browser.

## Repository layout

```text
backend/
├── app/                         # API gateway and static frontend host
├── database/                    # MongoDB client and collection handles
├── services/
│   ├── catalog_service/         # Public catalog and checkout preview
│   ├── order_service/           # Orders and payments
│   ├── partner_service/         # Partner workspace APIs
│   └── user_service/            # Customer/admin identity APIs
└── shared/                      # Auth, models, password helpers, DB startup

frontend/
├── pages/customer/              # Customer pages
├── pages/partner/               # Partner dashboard
├── pages/admin/                 # Admin dashboard
├── scripts/                     # Page behavior and API calls
├── styles/                      # Page stylesheets
└── assets/                      # Images and branding

k8s/                             # Kubernetes manifests (deployments, services, pvc, secret)
terraform/                       # Terraform AWS IaaC (VPC, ECR, EC2, K3s, IAM, EIP)
scripts/
├── launch.py                    # 1-Click AWS deploy & K8s rollout
├── destroy.py                   # 1-Click AWS teardown
├── deploy_k8s.py                # K3s manifest bundle & SSM deployer
└── test_health.py               # Health validation test
```

## Development checks

Compile the Python backend:

```bash
python3 -m compileall -q backend
```

Check JavaScript syntax:

```bash
for file in $(rg --files frontend/scripts -g '*.js'); do
  node --check "$file" || exit 1
done
```

Check whitespace and patch formatting:

```bash
git diff --check
```

## Notes

- This is a local demo, not a production payment system. The UPI flow marks an order as paid without contacting a payment provider.
- The default CORS policy is permissive for local development.
- Authentication tokens are stored in browser `localStorage` for simplicity.
- There is currently no automated test suite; use the health endpoint and manually exercise customer, partner, and admin flows after changes.
- The root `.env` and macOS `.DS_Store` files are ignored local artifacts and are not part of the application build.

## License

See [LICENSE](LICENSE).
