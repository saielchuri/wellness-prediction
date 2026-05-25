#!/bin/bash
# ================================================================
# Execute the full pipeline on Cloud Run
# Usage: bash scripts/run_pipeline.sh [REGION]
# ================================================================

set -euo pipefail

REGION=${1:-"northamerica-northeast1"}

echo "============================================"
echo "Running Nytia Health Pipeline"
echo "============================================"

echo ""
echo ">> Step 1/3: Ingestion (Bronze → Silver)..."
gcloud run jobs execute nytia-ingestion --region=${REGION} --wait

echo ""
echo ">> Step 2/3: Feature Engineering (Silver → Gold)..."
gcloud run jobs execute nytia-features --region=${REGION} --wait

echo ""
echo ">> Step 3/3: Model Training (Gold → Model)..."
gcloud run jobs execute nytia-training --region=${REGION} --wait

echo ""
echo "============================================"
echo "Pipeline Complete!"
echo ""
echo "Test the API:"
API_URL=$(gcloud run services describe nytia-api --region=${REGION} --format="value(status.url)")
echo "  curl ${API_URL}/health"
echo ""
echo "  curl ${API_URL}/predict -X POST -H 'Content-Type: application/json' -d '{"
echo '    "dif_nutri":"(-1000)-(-250)","c_val_nut":"600-1000",'
echo '    "dif_obesic":"250-1000","c_val_obe":"0-400",'
echo '    "dif_sleep":"250-1000","c_val_sle":"600-1000",'
echo '    "dif_depre":"(-250)-0","c_val_dep":"600-1000",'
echo '    "dif_wellr":"0-250","c_val_wel":"0-400",'
echo '    "dif_anti_stress":"(-250)-0","c_val_anti_stress":"400-600",'
echo '    "dif_anti_smoke":"(-250)-0","c_val_anti_smoke":"0-400",'
echo '    "dif_move":"(-1000)-(-250)","c_val_movement":"400-600"'
echo "  }'"
echo "============================================"
