#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-2}"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_TAG="${IMAGE_TAG:-latest}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SERVICES=(
  app
  user-service
  catalog-service
  order-service
  partner-service
)

dockerfile_for_service() {
  case "$1" in
    app) printf '%s\n' 'deploy/docker/Dockerfile.app' ;;
    user-service) printf '%s\n' 'deploy/docker/Dockerfile.user-service' ;;
    catalog-service) printf '%s\n' 'deploy/docker/Dockerfile.catalog-service' ;;
    order-service) printf '%s\n' 'deploy/docker/Dockerfile.order-service' ;;
    partner-service) printf '%s\n' 'deploy/docker/Dockerfile.partner-service' ;;
    *)
      echo "Unknown service: $1" >&2
      return 1
      ;;
  esac
}

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

for service in "${SERVICES[@]}"; do
  repository="tastekart-${service}"
  image="${ECR_REGISTRY}/${repository}:${IMAGE_TAG}"
  dockerfile="$(dockerfile_for_service "$service")"

  aws ecr describe-repositories \
    --repository-names "$repository" \
    --region "$AWS_REGION" >/dev/null 2>&1 || \
    aws ecr create-repository \
      --repository-name "$repository" \
      --region "$AWS_REGION" >/dev/null

  echo "Building ${image}"
  docker buildx build \
    --platform "$PLATFORMS" \
    --file "$PROJECT_ROOT/$dockerfile" \
    --tag "$image" \
    --push "$PROJECT_ROOT" \
    --provenance=false \
    --sbom=false
done

echo "Pushed separate TasteKart images to ${ECR_REGISTRY}"
