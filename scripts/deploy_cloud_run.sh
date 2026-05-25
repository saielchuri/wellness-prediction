#!/bin/bash
# ================================================================
# Deploy to Cloud Run: Jobs for pipeline steps, Service for API
# Usage: bash scripts/deploy_cloud_run.sh <PROJECT_ID> <REGION> [VERSION]
# Example: bash scripts/deploy_cloud_run.sh nytia-dev northamerica-northeast1 v1.0.0
# ================================================================

set -euo pipefail

PROJECT_ID=${1:-"nytia-dev"}
REGION=${2:-"northamerica-northeast1"}
VERSION=${3:-"v1.0.0"}
AR_HOST="${REGION}-docker.pkg.dev"
AR_REPO="${AR_HOST}/${PROJECT_ID}/nytia"
SA_EMAIL="nytia-pipeline-sa@${PROJECT_ID}.iam.gserviceaccount.com"
GCS_BUCKET="${PROJECT_ID}-ml-artifacts"

ENV_VARS="GCP_PROJECT_ID=${PROJECT_ID},BQ_DATASET=wellness_data,BQ_RAW_TABLE=bronze_assessments,BQ_SILVER_TABLE=silver_validated,BQ_GOLD_TABLE=gold_features,GCS_BUCKET=${GCS_BUCKET},LOG_LEVEL=INFO,ENVIRONMENT=dev"

echo "============================================"
echo "Deploying to Cloud Run"
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Version: ${VERSION}"
echo "============================================"

# ── Cloud Run Job: Ingestion ──
echo ""
echo ">> Deploying Ingestion Job..."
gcloud run jobs create nytia-ingestion \
  --image=${AR_REPO}/ingestion:${VERSION} \
  --region=${REGION} \
  --service-account=${SA_EMAIL} \
  --set-env-vars="${ENV_VARS}" \
  --memory=1Gi \
  --cpu=1 \
  --task-timeout=600 \
  --max-retries=1 \
  --quiet 2>/dev/null || \
gcloud run jobs update nytia-ingestion \
  --image=${AR_REPO}/ingestion:${VERSION} \
  --region=${REGION} \
  --set-env-vars="${ENV_VARS}" \
  --quiet

# ── Cloud Run Job: Feature Engineering ──
echo ""
echo ">> Deploying Feature Engineering Job..."
gcloud run jobs create nytia-features \
  --image=${AR_REPO}/features:${VERSION} \
  --region=${REGION} \
  --service-account=${SA_EMAIL} \
  --set-env-vars="${ENV_VARS}" \
  --memory=2Gi \
  --cpu=2 \
  --task-timeout=1200 \
  --max-retries=1 \
  --quiet 2>/dev/null || \
gcloud run jobs update nytia-features \
  --image=${AR_REPO}/features:${VERSION} \
  --region=${REGION} \
  --set-env-vars="${ENV_VARS}" \
  --quiet

# ── Cloud Run Job: Model Training ──
echo ""
echo ">> Deploying Model Training Job..."
gcloud run jobs create nytia-training \
  --image=${AR_REPO}/model:${VERSION} \
  --region=${REGION} \
  --service-account=${SA_EMAIL} \
  --set-env-vars="${ENV_VARS}" \
  --memory=4Gi \
  --cpu=2 \
  --task-timeout=3600 \
  --max-retries=1 \
  --quiet 2>/dev/null || \
gcloud run jobs update nytia-training \
  --image=${AR_REPO}/model:${VERSION} \
  --region=${REGION} \
  --set-env-vars="${ENV_VARS}" \
  --quiet

# ── Cloud Run Service: Prediction API ──
echo ""
echo ">> Deploying Prediction API..."
gcloud run deploy nytia-api \
  --image=${AR_REPO}/api:${VERSION} \
  --region=${REGION} \
  --service-account=${SA_EMAIL} \
  --set-env-vars="${ENV_VARS}" \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --port=8000 \
  --allow-unauthenticated \
  --quiet

# Get API URL
API_URL=$(gcloud run services describe nytia-api --region=${REGION} --format="value(status.url)")

echo ""
echo "============================================"
echo "Deployment Complete!"
echo ""
echo "API endpoint: ${API_URL}"
echo "Health check: ${API_URL}/health"
echo "Swagger docs: ${API_URL}/docs"
echo ""
echo "Run pipeline:"
echo "  gcloud run jobs execute nytia-ingestion --region=${REGION}"
echo "  gcloud run jobs execute nytia-features --region=${REGION}"
echo "  gcloud run jobs execute nytia-training --region=${REGION}"
echo ""
echo "Schedule daily pipeline (optional):"
echo "  gcloud scheduler jobs create http nytia-daily-ingestion \\"
echo "    --schedule='0 2 * * *' --uri='https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/nytia-ingestion:run' \\"
echo "    --http-method=POST --oauth-service-account-email=${SA_EMAIL}"
echo "============================================"
