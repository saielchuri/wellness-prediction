"""
Prediction API Service (GCP Native): FastAPI application deployed on Cloud Run.
Loads model from Cloud Storage on startup, serves complication risk predictions.
"""
import os
import logging
import random
import tempfile
from contextlib import asynccontextmanager

import numpy as np
import joblib
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("api")

model_bundle = None
config = None


def load_config(path="/app/config/config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def load_model_from_gcs(bucket_name, blob_path):
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
            blob.download_to_filename(tmp.name)
            bundle = joblib.load(tmp.name)
            os.unlink(tmp.name)

        logger.info(f"Model loaded from gs://{bucket_name}/{blob_path}")
        return bundle
    except Exception as e:
        logger.warning(f"GCS model load failed: {e}")
        return None


def load_model_local(path):
    if os.path.exists(path):
        bundle = joblib.load(path)
        logger.info(f"Model loaded from {path}")
        return bundle
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_bundle, config
    config = load_config()

    project = os.getenv("GCP_PROJECT_ID", "nytia-dev")
    gcs_bucket = os.getenv("GCS_BUCKET", f"{project}-ml-artifacts")

    # Try Cloud Storage first, then local fallback
    model_bundle = load_model_from_gcs(gcs_bucket, "models/latest_model.pkl")
    if model_bundle is None:
        local_path = os.getenv("MODEL_PATH", "/app/models/artifacts/latest_model.pkl")
        model_bundle = load_model_local(local_path)

    if model_bundle:
        logger.info(f"Features: {model_bundle['feature_cols']}")
    else:
        logger.warning("No model loaded. /predict will return 503.")

    yield
    logger.info("API shutting down")


app = FastAPI(
    title="Nytia Health Complication Risk Prediction API",
    description="Predicts secondary complication risk for chronic disease patients using multi-dimensional wellness data.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class WellnessInput(BaseModel):
    dif_nutri: str = Field(..., example="(-1000)-(-250)")
    c_val_nut: str = Field(..., example="600-1000")
    dif_obesic: str = Field(..., example="250-1000")
    c_val_obe: str = Field(..., example="0-400")
    dif_sleep: str = Field(..., example="250-1000")
    c_val_sle: str = Field(..., example="600-1000")
    dif_depre: str = Field(..., example="(-250)-0")
    c_val_dep: str = Field(..., example="600-1000")
    dif_wellr: str = Field(..., example="0-250")
    c_val_wel: str = Field(..., example="0-400")
    dif_anti_stress: str = Field(..., example="(-250)-0")
    c_val_anti_stress: str = Field(..., example="400-600")
    dif_anti_smoke: str = Field(..., example="(-250)-0")
    c_val_anti_smoke: str = Field(..., example="0-400")
    dif_move: str = Field(..., example="(-1000)-(-250)")
    c_val_movement: str = Field(..., example="400-600")


class PredictionResponse(BaseModel):
    risk_score: float
    risk_level: str
    risk_tier: int
    total_declining: int
    critical_current_values: int
    top_drivers: list[str]
    recommendations: list[str]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    version: str
    environment: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        model_loaded=model_bundle is not None,
        version="1.0.0",
        environment=os.getenv("ENVIRONMENT", "dev"),
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict(input_data: WellnessInput):
    if model_bundle is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Train the model first.")

    model = model_bundle["model"]
    feature_cols = model_bundle["feature_cols"]
    cfg = model_bundle["config"]

    traj_map = cfg["encoding"]["trajectory"]
    cval_map = cfg["encoding"]["current_value"]
    input_dict = input_data.model_dump()

    traj_cols = cfg["columns"]["trajectory"]
    cval_cols = cfg["columns"]["current_value"]

    encoded = {}
    for col in traj_cols:
        val = input_dict.get(col)
        enc = traj_map.get(val)
        if enc is None:
            raise HTTPException(status_code=400, detail=f"Invalid value for {col}: {val}")
        encoded[col + "_enc"] = enc

    for col in cval_cols:
        val = input_dict.get(col)
        enc = cval_map.get(val)
        if enc is None:
            raise HTTPException(status_code=400, detail=f"Invalid value for {col}: {val}")
        encoded[col + "_enc"] = enc

    enc_dif = [c + "_enc" for c in traj_cols]
    enc_cval = [c + "_enc" for c in cval_cols]
    encoded["total_declining_count"] = sum(1 for c in enc_dif if encoded.get(c, 5) <= 2)
    encoded["critical_cval_count"] = sum(1 for c in enc_cval if encoded.get(c, 5) == 1)

    features = np.array([[encoded.get(col, 0) for col in feature_cols]])

    proba = model.predict_proba(features)[0]
    tier = int(np.argmax(proba))
    risk_score = round(float(proba[2]), 4)
    risk_level = {0: "Low", 1: "Moderate", 2: "High"}[tier]

    dim_names = ["Nutrition", "Obesity", "Sleep", "Depression", "Wellbeing", "Anti-Stress", "Anti-Smoke", "Movement"]
    declining = [dim for col, dim in zip(traj_cols, dim_names) if encoded.get(col + "_enc", 5) <= 2]

    rec_cfg = cfg.get("recommendations", {})
    recs = []
    if "Anti-Smoke" in declining and "smoking_cessation" in rec_cfg:
        recs.extend(random.sample(rec_cfg["smoking_cessation"], min(2, len(rec_cfg["smoking_cessation"]))))
    if "Movement" in declining and "physical_activity" in rec_cfg:
        recs.extend(random.sample(rec_cfg["physical_activity"], min(2, len(rec_cfg["physical_activity"]))))
    if "Nutrition" in declining:
        recs.append("Focus on balanced meals with more vegetables and whole grains.")
    if not recs and "behavioral_planning" in rec_cfg:
        recs.extend(rec_cfg["behavioral_planning"])
    recs = recs[:4]

    return PredictionResponse(
        risk_score=risk_score,
        risk_level=risk_level,
        risk_tier=tier,
        total_declining=encoded["total_declining_count"],
        critical_current_values=encoded["critical_cval_count"],
        top_drivers=declining[:5],
        recommendations=recs,
    )
