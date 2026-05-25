#!/bin/bash
# ================================================================
# Nytia Health GCP Setup Script
# Run once to provision all required GCP resources.
# Usage: bash scripts/gcp_setup.sh <PROJECT_ID> <REGION>
# Example: bash scripts/gcp_setup.sh nytia-dev northamerica-northeast1
# ================================================================

set -euo pipefail

PROJECT_ID=${1:-"nytia-dev"}
REGION=${2:-"northamerica-northeast1"}
DATASET="wellness_data"
BUCKET="${PROJECT_ID}-ml-artifacts"
AR_REPO="nytia"

echo "============================================"
echo "Nytia Health GCP Setup"
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "============================================"

# Set project
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo ""
echo ">> Enabling APIs..."
gcloud services enable \
  bigquery.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com

# Create BigQuery dataset with medallion tables
echo ""
echo ">> Creating BigQuery dataset: ${DATASET}"
bq mk --dataset --location=${REGION} ${PROJECT_ID}:${DATASET} 2>/dev/null || echo "  Dataset already exists"

echo ">> BigQuery tables will be created automatically by the pipeline"

# Create Cloud Storage bucket
echo ""
echo ">> Creating Cloud Storage bucket: ${BUCKET}"
gsutil mb -l ${REGION} gs://${BUCKET} 2>/dev/null || echo "  Bucket already exists"

# Create bucket folders
gsutil cp /dev/null gs://${BUCKET}/models/.keep 2>/dev/null
gsutil cp /dev/null gs://${BUCKET}/features/.keep 2>/dev/null
gsutil cp /dev/null gs://${BUCKET}/shap/.keep 2>/dev/null

# Create Artifact Registry repository
echo ""
echo ">> Creating Artifact Registry: ${AR_REPO}"
gcloud artifacts repositories create ${AR_REPO} \
  --repository-format=docker \
  --location=${REGION} \
  --description="Nytia Health Docker images" 2>/dev/null || echo "  Repository already exists"

# Configure Docker auth for Artifact Registry
echo ""
echo ">> Configuring Docker authentication..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Create service account for Cloud Run
echo ""
echo ">> Creating service account..."
SA_NAME="nytia-pipeline-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create ${SA_NAME} \
  --display-name="Nytia Health Pipeline Service Account" 2>/dev/null || echo "  SA already exists"

# Grant required roles
for ROLE in \
  "roles/bigquery.dataEditor" \
  "roles/bigquery.jobUser" \
  "roles/storage.objectAdmin" \
  "roles/run.invoker"; do
  gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" --quiet
done

echo ""
echo "============================================"
echo "GCP Setup Complete!"
echo ""
echo "Next steps:"
echo "  1. Load your data into BigQuery:"
echo "     bq load --autodetect ${PROJECT_ID}:${DATASET}.bronze_assessments your_data.csv"
echo ""
echo "  2. Build and push Docker images:"
echo "     bash scripts/build_and_push.sh ${PROJECT_ID} ${REGION}"
echo ""
echo "  3. Deploy to Cloud Run:"
echo "     bash scripts/deploy_cloud_run.sh ${PROJECT_ID} ${REGION}"
echo "============================================"
