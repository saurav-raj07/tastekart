#!/bin/bash
set -euo pipefail

# Log all outputs to /var/log/user-data.log
exec > >(tee -a /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1
echo "=== Starting TasteKart K3s Initialization ==="

# 1. Update and install prerequisites
apt-get update -y
apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release jq unzip

# 2. Install AWS CLI v2 if not already present
if ! command -v aws &> /dev/null; then
    echo "Installing AWS CLI v2..."
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    ./aws/install
    rm -rf aws awscliv2.zip
fi

# 3. Retrieve Public IP (Elastic IP) for K3s SAN
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" || true)
if [ -n "$TOKEN" ]; then
    PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4 || true)
else
    PUBLIC_IP=""
fi

# 4. Install K3s (lightweight Kubernetes)
echo "Installing K3s with SAN $PUBLIC_IP..."
curl -sfL https://get.k3s.io | sh -s - \
    --write-kubeconfig-mode 644 \
    --tls-san "$PUBLIC_IP"

# Wait for K3s node to be ready
echo "Waiting for K3s node to report Ready..."
until /usr/local/bin/kubectl get nodes | grep -q "Ready"; do
    sleep 3
done

# 5. Create tastekart namespace
/usr/local/bin/kubectl create namespace tastekart --dry-run=client -o yaml | /usr/local/bin/kubectl apply -f -

# 6. Setup automatic ECR Token Refresh Script & Cron
# AWS ECR credentials expire every 12 hours. This script runs every 6 hours to ensure zero pull failures.
cat << 'EOF' > /usr/local/bin/refresh-ecr-token.sh
#!/bin/bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

AWS_REGION="${aws_region}"
AWS_ACCOUNT_ID="${aws_account_id}"
REGISTRY="$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com"

echo "[$(date)] Refreshing AWS ECR pull secret for namespace: tastekart..."
ECR_TOKEN=$(aws ecr get-login-password --region "$AWS_REGION")

kubectl create namespace tastekart --dry-run=client -o yaml | kubectl apply -f -

kubectl delete secret ecr-secret -n tastekart --ignore-not-found
kubectl create secret docker-registry ecr-secret \
    --docker-server="$REGISTRY" \
    --docker-username=AWS \
    --docker-password="$ECR_TOKEN" \
    --namespace=tastekart

# Patch default serviceaccount so all pods automatically inherit imagePullSecrets
kubectl patch serviceaccount default -n tastekart -p '{"imagePullSecrets": [{"name": "ecr-secret"}]}'
echo "[$(date)] ECR secret refreshed and default serviceaccount patched."
EOF

chmod +x /usr/local/bin/refresh-ecr-token.sh

# Run once immediately
/usr/local/bin/refresh-ecr-token.sh || true

# Add to root crontab (runs every 6 hours)
(crontab -l 2>/dev/null || true; echo "0 */6 * * * /usr/local/bin/refresh-ecr-token.sh >> /var/log/ecr-token-refresh.log 2>&1") | crontab -

# Add convenience aliases for ubuntu user
cat << 'EOF' >> /home/ubuntu/.bashrc
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
alias k=kubectl
alias kgp="kubectl get pods -n tastekart"
alias kgs="kubectl get svc -n tastekart"
EOF

echo "=== TasteKart K3s Initialization Finished Successfully ==="
