"""
Model Training Service (GCP Native): Reads Gold features from BigQuery,
trains XGBoost with stratified k-fold CV, saves model + SHAP to Cloud Storage.
"""
import os
import sys
import logging
import json
import tempfile
import pandas as pd
import numpy as np
import yaml
import joblib
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, classification_report)
from sklearn.preprocessing import label_binarize

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("model")


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


def upload_to_gcs(local_path, bucket_name, blob_path):
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(local_path)
        logger.info(f"Uploaded to gs://{bucket_name}/{blob_path}")
        return True
    except Exception as e:
        logger.warning(f"GCS upload failed: {e}")
        return False


def prepare_data(df, config):
    enc_dif = [c + "_enc" for c in config["columns"]["trajectory"]]
    enc_cval = [c + "_enc" for c in config["columns"]["current_value"]]
    derived = ["total_declining_count", "critical_cval_count"]

    feature_cols = []
    for col in enc_dif + enc_cval + derived:
        if col in df.columns and df[col].nunique() > 1:
            feature_cols.append(col)
        elif col in df.columns:
            logger.warning(f"Excluding {col}: zero variance")

    X = df[feature_cols].values
    y = df["risk_tier"].values
    logger.info(f"Features: {len(feature_cols)}, Classes: {dict(zip(*np.unique(y, return_counts=True)))}")
    return X, y, feature_cols


def train_and_evaluate(X, y, feature_cols, config):
    hp = config["model"]["hyperparameters"]
    n_splits = config["model"]["cross_validation"]["n_splits"]
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=hp["random_state"])

    fold_metrics = []
    best_model, best_auc = None, 0

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y), 1):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        model = xgb.XGBClassifier(
            max_depth=hp["max_depth"], learning_rate=hp["learning_rate"],
            n_estimators=hp["n_estimators"], subsample=hp["subsample"],
            colsample_bytree=hp["colsample_bytree"], min_child_weight=hp["min_child_weight"],
            objective=hp["objective"], num_class=hp["num_class"],
            eval_metric=hp["eval_metric"], random_state=hp["random_state"],
            use_label_encoder=False, verbosity=0,
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        y_pred = model.predict(X_val)
        y_proba = model.predict_proba(X_val)

        acc = accuracy_score(y_val, y_pred)
        prec = precision_score(y_val, y_pred, average="weighted", zero_division=0)
        rec = recall_score(y_val, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_val, y_pred, average="weighted", zero_division=0)

        y_val_bin = label_binarize(y_val, classes=[0, 1, 2])
        try:
            auc = roc_auc_score(y_val_bin, y_proba, multi_class="ovr", average="weighted")
        except ValueError:
            auc = 0.0

        fold_metrics.append({"fold": fold, "accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "auc_roc": auc})
        logger.info(f"Fold {fold}: Acc={acc:.4f} F1={f1:.4f} AUC={auc:.4f}")

        if auc > best_auc:
            best_auc = auc
            best_model = model

    metrics_df = pd.DataFrame(fold_metrics)
    avg = metrics_df.mean(numeric_only=True)
    logger.info(f"CV Averages: Acc={avg['accuracy']:.4f} Prec={avg['precision']:.4f} Rec={avg['recall']:.4f} F1={avg['f1']:.4f} AUC={avg['auc_roc']:.4f}")

    return best_model, metrics_df


def generate_shap(model, X, feature_cols, output_dir):
    try:
        import shap
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        os.makedirs(output_dir, exist_ok=True)
        sample_size = min(5000, len(X))
        X_sample = X[np.random.choice(len(X), sample_size, replace=False)]

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)

        plt.figure(figsize=(12, 8))
        shap.summary_plot(shap_values, X_sample, feature_names=feature_cols, show=False,
                          class_names=["Low", "Moderate", "High"])
        plt.title("SHAP Feature Importance by Risk Tier")
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "shap_summary.png"), dpi=150)
        plt.close()

        if isinstance(shap_values, list):
            mean_shap = np.mean([np.abs(sv).mean(axis=0) for sv in shap_values], axis=0)
        else:
            mean_shap = np.abs(shap_values).mean(axis=0)

        importance = pd.DataFrame({"feature": feature_cols, "mean_shap": mean_shap}).sort_values("mean_shap", ascending=False)
        importance.to_csv(os.path.join(output_dir, "shap_importance.csv"), index=False)

        logger.info(f"Top 5 SHAP features:\n{importance.head().to_string(index=False)}")
        return output_dir
    except Exception as e:
        logger.error(f"SHAP failed: {e}")
        return None


def main():
    config = load_config()
    project = os.getenv("GCP_PROJECT_ID", "nytia-dev")
    dataset = os.getenv("BQ_DATASET", "wellness_data")
    gold_table = os.getenv("BQ_GOLD_TABLE", "gold_features")
    gcs_bucket = os.getenv("GCS_BUCKET", f"{project}-ml-artifacts")

    logger.info("=" * 60)
    logger.info("MODEL TRAINING PIPELINE START")
    logger.info("=" * 60)

    # Load from BigQuery Gold (or local fallback)
    df = load_from_bigquery(project, dataset, gold_table)
    if df is None:
        local = os.getenv("PROCESSED_DATA_PATH", "/app/data/processed/") + "ml_features.csv"
        if os.path.exists(local):
            df = pd.read_csv(local)
            logger.info(f"Fallback: {len(df):,} records from CSV")
        else:
            logger.error("No data. Run feature engineering first.")
            sys.exit(1)

    X, y, feature_cols = prepare_data(df, config)
    model, metrics = train_and_evaluate(X, y, feature_cols, config)

    # Save model locally first
    local_model_dir = os.getenv("MODEL_PATH", "/app/models/artifacts/")
    os.makedirs(local_model_dir, exist_ok=True)
    model_path = os.path.join(local_model_dir, "latest_model.pkl")
    bundle = {"model": model, "feature_cols": feature_cols, "config": config}
    joblib.dump(bundle, model_path)
    logger.info(f"Model saved locally: {model_path}")

    # Save metrics
    metrics_path = os.path.join(local_model_dir, "training_metrics.csv")
    metrics.to_csv(metrics_path, index=False)

    # Upload model to Cloud Storage
    upload_to_gcs(model_path, gcs_bucket, "models/latest_model.pkl")
    upload_to_gcs(metrics_path, gcs_bucket, "models/training_metrics.csv")

    # SHAP analysis
    shap_dir = os.path.join(local_model_dir, "../shap_reports")
    shap_output = generate_shap(model, X, feature_cols, shap_dir)
    if shap_output:
        for f in os.listdir(shap_output):
            upload_to_gcs(os.path.join(shap_output, f), gcs_bucket, f"shap/{f}")

    logger.info("=" * 60)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
