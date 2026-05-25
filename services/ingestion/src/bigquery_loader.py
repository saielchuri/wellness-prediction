"""
Ingestion Service (GCP Native): Reads from BigQuery Bronze layer,
validates schema, writes validated data to BigQuery Silver layer.
Falls back to local CSV for testing.
"""
import os
import sys
import logging
import pandas as pd
import yaml

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ingestion")


def load_config(path: str = "/app/config/config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def validate_schema(df: pd.DataFrame, config: dict) -> tuple:
    expected_cols = config["columns"]["trajectory"] + config["columns"]["current_value"]
    expected_cols += ["recommendations", "status_assessment"]

    drop_cols = [c for c in ["Row", "Unnamed: 0", "row_number"] if c in df.columns]
    if drop_cols:
        df = df.drop(columns=drop_cols)
        logger.info(f"Dropped serial columns: {drop_cols}")

    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        logger.error(f"Missing columns: {missing}")
        return False, df

    valid_traj = set(config["encoding"]["trajectory"].keys())
    for col in config["columns"]["trajectory"]:
        invalid = set(df[col].dropna().unique()) - valid_traj
        if invalid:
            bad_count = len(df[df[col].isin(invalid)])
            logger.warning(f"{col}: dropping {bad_count} rows with unexpected values")
            df = df[~df[col].isin(invalid)]

    valid_cval = set(config["encoding"]["current_value"].keys())
    for col in config["columns"]["current_value"]:
        invalid = set(df[col].dropna().unique()) - valid_cval
        if invalid:
            bad_count = len(df[df[col].isin(invalid)])
            logger.warning(f"{col}: dropping {bad_count} rows with unexpected values")
            df = df[~df[col].isin(invalid)]

    before = len(df)
    df = df.dropna(subset=expected_cols)
    if before - len(df) > 0:
        logger.info(f"Dropped {before - len(df)} rows with null values")

    logger.info(f"Validation passed: {len(df):,} records")
    return True, df


def load_from_bigquery(project, dataset, table):
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=project)
        query = f"SELECT * FROM `{project}.{dataset}.{table}`"
        logger.info(f"Query: {query}")
        df = client.query(query).to_dataframe()
        logger.info(f"Loaded {len(df):,} records from BigQuery")
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


def main():
    config = load_config()
    project = os.getenv("GCP_PROJECT_ID", "nytia-dev")
    dataset = os.getenv("BQ_DATASET", "wellness_data")
    raw_table = os.getenv("BQ_RAW_TABLE", "bronze_assessments")
    silver_table = os.getenv("BQ_SILVER_TABLE", "silver_validated")

    logger.info("=" * 60)
    logger.info("INGESTION PIPELINE START")
    logger.info("=" * 60)

    df = load_from_bigquery(project, dataset, raw_table)
    if df is None:
        csv_path = os.getenv("SAMPLE_DATA_PATH", "/app/data/sample/") + "sample_wellness_data.csv"
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            logger.info(f"Fallback: {len(df):,} records from CSV")
        else:
            logger.error("No data source. Exiting.")
            sys.exit(1)

    initial_count = len(df)
    valid, df = validate_schema(df, config)
    if not valid:
        sys.exit(1)

    try:
        write_to_bigquery(df, project, dataset, silver_table)
    except Exception:
        path = os.getenv("RAW_DATA_PATH", "/app/data/raw/") + "validated_raw.csv"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df.to_csv(path, index=False)
        logger.warning(f"BQ write failed. Local fallback: {path}")

    logger.info(f"COMPLETE: {initial_count:,} -> {len(df):,} records ({initial_count - len(df):,} dropped)")


if __name__ == "__main__":
    main()
