#!/bin/bash
# ================================================================
# Build and push all Docker images to Artifact Registry
# Usage: bash scripts/build_and_push.sh <PROJECT_ID> <REGION> [VERSION]
# Example: bash scripts/build_and_push.sh nytia-dev northamerica-northeast1 v1.0.0
# ================================================================

set -euo pipefail

PROJECT_ID=${1:-"nytia-dev"}
REGION=${2:-"northamerica-northeast1"}
VERSION=${3:-"v1.0.0"}
AR_HOST="${REGION}-docker.pkg.dev"
AR_REPO="${AR_HOST}/${PROJECT_ID}/nytia"

echo "============================================"
echo "Building and pushing images"
echo "Registry: ${AR_REPO}"
echo "Version:  ${VERSION}"
echo "============================================"

SERVICES=("ingestion" "features" "model" "api")

for SERVICE in "${SERVICES[@]}"; do
  echo ""
  echo ">> Building ${SERVICE}:${VERSION}..."
  docker build \
    -t ${AR_REPO}/${SERVICE}:${VERSION} \
    -t ${AR_REPO}/${SERVICE}:latest \
    -f services/${SERVICE}/Dockerfile \
    services/${SERVICE}/

  echo ">> Pushing ${SERVICE}:${VERSION}..."
  docker push ${AR_REPO}/${SERVICE}:${VERSION}
  docker push ${AR_REPO}/${SERVICE}:latest
done

echo ""
echo "============================================"
echo "All images pushed to ${AR_REPO}"
echo "  Tags: ${VERSION}, latest"
echo "============================================"
