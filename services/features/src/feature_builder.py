"""
Feature Engineering Service (GCP Native): Reads Silver layer from BigQuery,
applies ordinal encoding, text parsing, derived features, risk tier classification.
Writes ML-ready Gold features to BigQuery and backs up to Cloud Storage.
"""
import os
import re
import sys
import logging
import pandas as pd
import numpy as np
import yaml

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("features")

DIMENSION_NAMES = ["Nutrition", "Obesity", "Sleep", "Depression", "Wellbeing", "Anti-Stress", "Anti-Smoke", "Movement"]


def load_config(path="/app/config/config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def load_from_bigquery(project, dataset, table):
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=project)
        query = f"SELECT * FROM `{project}.{dataset}.{table}`"
        logger.info(f"Query: {query}")
        df = client.query(query).to_dataframe()
        logger.info(f"Loaded {len(df):,} records")
        return df
    except Exception as e:
        logger.warning(f"BigQuery unavailable: {e}")
        return None


def write_to_bigquery(df, project, dataset, table):
    from google.cloud import bigquery
    client = bigquery.Client(project=project)
    table_ref = f"{project}.{dataset}.{table}"
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )
    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()
    logger.info(f"Wrote {len(df):,} records to {table_ref}")


def backup_to_gcs(df, bucket_name, blob_path):
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_string(df.to_csv(index=False), content_type="text/csv")
        logger.info(f"Backed up to gs://{bucket_name}/{blob_path}")
    except Exception as e:
        logger.warning(f"GCS backup failed: {e}")


def ordinal_encode(df, config):
    traj_map = config["encoding"]["trajectory"]
    cval_map = config["encoding"]["current_value"]

    for col in config["columns"]["trajectory"]:
        df[col + "_enc"] = df[col].map(traj_map)
    for col in config["columns"]["current_value"]:
        df[col + "_enc"] = df[col].map(cval_map)

    logger.info("Ordinal encoding complete")
    return df


def parse_status_assessment(df):
    for dim in DIMENSION_NAMES:
        col_name = f"declining_{dim.lower().replace('-', '_')}"
        df[col_name] = df["status_assessment"].apply(
            lambda x: 1 if re.search(rf"improving.*{re.escape(dim)}", str(x), re.IGNORECASE) else 0
        )
    logger.info("Status assessment parsing complete")
    return df


def derive_features(df, config):
    enc_dif = [c + "_enc" for c in config["columns"]["trajectory"]]
    enc_cval = [c + "_enc" for c in config["columns"]["current_value"]]

    df["total_declining_count"] = (df[enc_dif] <= 2).sum(axis=1)
    df["critical_cval_count"] = (df[enc_cval] == 1).sum(axis=1)

    tier_cfg = config["risk_tiers"]
    conditions = [
        (df["total_declining_count"] <= tier_cfg["low"]["max_declining"]) &
        (df["critical_cval_count"] <= tier_cfg["low"]["max_critical_cval"]),
        (df["total_declining_count"] <= tier_cfg["moderate"]["max_declining"]) &
        (df["critical_cval_count"] <= tier_cfg["moderate"]["max_critical_cval"]),
    ]
    df["risk_tier"] = np.select(conditions, [0, 1], default=2)
    df["risk_label"] = df["risk_tier"].map({0: "Low", 1: "Moderate", 2: "High"})
    df["high_risk"] = (df["risk_tier"] == 2).astype(int)

    logger.info(f"Risk tiers: {df['risk_label'].value_counts().to_dict()}")
    return df


def categorize_recommendations(df):
    categories = {
        "rec_smoking_cessation": ["smoke", "smoking", "gum", "mints"],
        "rec_physical_activity": ["walk", "sport", "exercise", "physical activity", "stretch"],
        "rec_behavioral_planning": ["anticipate", "plan", "challenges"],
        "rec_health_education": ["read about", "harmful effects"],
        "rec_social_support": ["family and friends", "accountable"],
    }
    for col_name, keywords in categories.items():
        df[col_name] = df["recommendations"].apply(
            lambda x: 1 if any(k in str(x).lower() for k in keywords) else 0
        )
    logger.info("Recommendation categorization complete")
    return df


def select_feature_columns(df, config):
    enc_dif = [c + "_enc" for c in config["columns"]["trajectory"]]
    enc_cval = [c + "_enc" for c in config["columns"]["current_value"]]
    decline_flags = [f"declining_{d.lower().replace('-', '_')}" for d in DIMENSION_NAMES]
    rec_flags = [c for c in df.columns if c.startswith("rec_")]
    derived = ["total_declining_count", "critical_cval_count", "risk_tier", "risk_label", "high_risk"]

    feature_cols = enc_dif + enc_cval + decline_flags + rec_flags + derived

    # Exclude zero-variance columns
    zero_var = [c for c in feature_cols if c in df.columns and df[c].nunique() <= 1 and c not in derived]
    if zero_var:
        logger.warning(f"Zero-variance columns (kept but flagged): {zero_var}")

    return df[feature_cols].copy()


def main():
    config = load_config()
    project = os.getenv("GCP_PROJECT_ID", "nytia-dev")
    dataset = os.getenv("BQ_DATASET", "wellness_data")
    silver_table = os.getenv("BQ_SILVER_TABLE", "silver_validated")
    gold_table = os.getenv("BQ_GOLD_TABLE", "gold_features")
    gcs_bucket = os.getenv("GCS_BUCKET", f"{project}-ml-artifacts")

    logger.info("=" * 60)
    logger.info("FEATURE ENGINEERING PIPELINE START")
    logger.info("=" * 60)

    # Load from BigQuery Silver (or local fallback)
    df = load_from_bigquery(project, dataset, silver_table)
    if df is None:
        local_path = os.getenv("RAW_DATA_PATH", "/app/data/raw/") + "validated_raw.csv"
        if os.path.exists(local_path):
            df = pd.read_csv(local_path)
            logger.info(f"Fallback: {len(df):,} records from {local_path}")
        else:
            logger.error("No data source. Run ingestion first.")
            sys.exit(1)

    initial_count = len(df)

    # Pipeline
    df = ordinal_encode(df, config)
    df = parse_status_assessment(df)
    df = derive_features(df, config)
    df = categorize_recommendations(df)
    df_features = select_feature_columns(df, config)

    # Write to BigQuery Gold layer
    try:
        write_to_bigquery(df_features, project, dataset, gold_table)
    except Exception:
        local_path = os.getenv("PROCESSED_DATA_PATH", "/app/data/processed/") + "ml_features.csv"
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        df_features.to_csv(local_path, index=False)
        logger.warning(f"BQ write failed. Local: {local_path}")

    # Backup to Cloud Storage
    backup_to_gcs(df_features, gcs_bucket, "features/ml_features.csv")

    logger.info(f"COMPLETE: {initial_count:,} records -> {len(df_features.columns)} features")


if __name__ == "__main__":
    main()
